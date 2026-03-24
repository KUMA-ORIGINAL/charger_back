import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import patch

from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from asgiref.sync import sync_to_async

from account.models import (
    ChargePoint,
    ChargePointCSMS,
    CSMSService,
    CSMSTransactionMapping,
)
from account.consumers import OCPPConsumer
from account.ocpp_routing import websocket_urlpatterns


TEST_CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}


class FakeCSMSWebSocket:
    def __init__(self, name: str):
        self.name = name
        self.sent = []
        self._incoming = asyncio.Queue()
        self._closed = False

    async def send(self, data: str):
        self.sent.append(json.loads(data))

    async def close(self):
        if self._closed:
            return
        self._closed = True
        self._incoming.put_nowait(None)

    def push_incoming(self, frame: list):
        self._incoming.put_nowait(json.dumps(frame))

    def __aiter__(self):
        return self

    async def __anext__(self):
        raw = await self._incoming.get()
        if raw is None:
            raise StopAsyncIteration
        return raw


class FakeWebsocketsFactory:
    def __init__(self):
        self.by_url = {}

    async def connect(self, url, **kwargs):
        ws = FakeCSMSWebSocket(name=url)
        self.by_url[url] = ws
        return ws


@override_settings(
    CHANNEL_LAYERS=TEST_CHANNEL_LAYERS,
    DEBUG_TOOLBAR_CONFIG={"IS_RUNNING_TESTS": False},
)
class OCPPConsumerTests(TransactionTestCase):
    def setUp(self):
        self.app = URLRouter(websocket_urlpatterns)

        self.cp, _ = ChargePoint.objects.get_or_create(
            cp_id="301",
            name="Test CP 301",
        )
        self.csms_a, _ = CSMSService.objects.get_or_create(
            name="MockA",
            defaults={
                "service_type": CSMSService.ServiceType.OTHER,
                "is_active": True,
                "ws_url_template": "ws://mock-a/{cp_id}",
            },
        )
        self.csms_b, _ = CSMSService.objects.get_or_create(
            name="MockB",
            defaults={
                "service_type": CSMSService.ServiceType.OTHER,
                "is_active": True,
                "ws_url_template": "ws://mock-b/{cp_id}",
            },
        )
        ChargePointCSMS.objects.get_or_create(
            charge_point=self.cp,
            csms_service=self.csms_a,
            defaults={"remote_cp_id": "CP301A"},
        )
        ChargePointCSMS.objects.get_or_create(
            charge_point=self.cp,
            csms_service=self.csms_b,
            defaults={"remote_cp_id": "CP301B"},
        )

    async def _wait_for(self, predicate, timeout=2.0):
        start = asyncio.get_running_loop().time()
        while True:
            if predicate():
                return
            if asyncio.get_running_loop().time() - start > timeout:
                self.fail("Timed out waiting for condition")
            await asyncio.sleep(0.01)

    async def test_forwards_heartbeat_and_status_to_both_csms(self):
        factory = FakeWebsocketsFactory()

        with patch("account.consumers.websockets.connect", new=factory.connect):
            communicator = WebsocketCommunicator(self.app, "/ws/ocpp/301")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            ws_a = factory.by_url["ws://mock-a/CP301A"]
            ws_b = factory.by_url["ws://mock-b/CP301B"]

            await communicator.send_json_to([2, "hb-1", "Heartbeat", {}])
            hb_result = await communicator.receive_json_from()
            self.assertEqual(hb_result[0], 3)
            self.assertEqual(hb_result[1], "hb-1")
            self.assertIn("currentTime", hb_result[2])

            await self._wait_for(
                lambda: any(f[1] == "hb-1" and f[2] == "Heartbeat" for f in ws_a.sent)
                and any(f[1] == "hb-1" and f[2] == "Heartbeat" for f in ws_b.sent)
            )

            await communicator.send_json_to(
                [
                    2,
                    "status-1",
                    "StatusNotification",
                    {
                        "connectorId": 1,
                        "errorCode": "NoError",
                        "status": "Available",
                        "timestamp": datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                    },
                ]
            )
            status_result = await communicator.receive_json_from()
            self.assertEqual(status_result, [3, "status-1", {}])

            await self._wait_for(
                lambda: any(
                    f[1] == "status-1" and f[2] == "StatusNotification"
                    for f in ws_a.sent
                )
                and any(
                    f[1] == "status-1" and f[2] == "StatusNotification"
                    for f in ws_b.sent
                )
            )

            await communicator.disconnect()

    async def test_authorize_only_to_initiator_and_blocks_other_start(self):
        factory = FakeWebsocketsFactory()

        with patch("account.consumers.websockets.connect", new=factory.connect):
            communicator = WebsocketCommunicator(self.app, "/ws/ocpp/301")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            ws_a = factory.by_url["ws://mock-a/CP301A"]
            ws_b = factory.by_url["ws://mock-b/CP301B"]

            # CSMS A starts charging
            ws_a.push_incoming(
                [
                    2,
                    "remote-start-a",
                    "RemoteStartTransaction",
                    {"connectorId": 1, "idTag": "TAG-A"},
                ]
            )
            forwarded_call = await communicator.receive_json_from()
            self.assertEqual(forwarded_call[0], 2)
            self.assertEqual(forwarded_call[1], "remote-start-a")
            self.assertEqual(forwarded_call[2], "RemoteStartTransaction")

            # station accepts remote start
            await communicator.send_json_to([3, "remote-start-a", {"status": "Accepted"}])
            await self._wait_for(
                lambda: any(f[0] == 3 and f[1] == "remote-start-a" for f in ws_a.sent)
            )

            # station sends Authorize (must go only to initiator A)
            await communicator.send_json_to(
                [2, "auth-1", "Authorize", {"idTag": "TAG-A"}]
            )
            auth_result = await communicator.receive_json_from()
            self.assertEqual(auth_result[0], 3)
            self.assertEqual(auth_result[1], "auth-1")
            self.assertEqual(auth_result[2]["idTagInfo"]["status"], "Accepted")

            await self._wait_for(
                lambda: any(f[1] == "auth-1" and f[2] == "Authorize" for f in ws_a.sent)
            )
            self.assertFalse(
                any(f[1] == "auth-1" and f[2] == "Authorize" for f in ws_b.sent)
            )

            # station starts transaction with external idTag -> occupied by A
            await communicator.send_json_to(
                [
                    2,
                    "start-tx-1",
                    "StartTransaction",
                    {
                        "connectorId": 1,
                        "idTag": "TAG-A",
                        "meterStart": 0,
                        "timestamp": datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                    },
                ]
            )
            start_tx_result = await communicator.receive_json_from()
            self.assertEqual(start_tx_result[0], 3)
            self.assertEqual(start_tx_result[1], "start-tx-1")
            self.assertIn("transactionId", start_tx_result[2])

            # CSMS B tries to start while occupied -> must be blocked
            ws_b.push_incoming(
                [
                    2,
                    "remote-start-b",
                    "RemoteStartTransaction",
                    {"connectorId": 1, "idTag": "TAG-B"},
                ]
            )
            await self._wait_for(
                lambda: any(f[0] == 3 and f[1] == "remote-start-b" for f in ws_b.sent)
            )
            blocked = [f for f in ws_b.sent if f[0] == 3 and f[1] == "remote-start-b"][0]
            self.assertEqual(blocked[2], {"status": "Rejected"})

            await communicator.disconnect()

    async def test_hot_add_and_remove_csms_without_station_reconnect(self):
        # Start with one linked CSMS only.
        await sync_to_async(
            ChargePointCSMS.objects.filter(
                charge_point=self.cp, csms_service=self.csms_b
            ).delete
        )()

        factory = FakeWebsocketsFactory()
        with (
            patch("account.consumers.websockets.connect", new=factory.connect),
            patch.object(OCPPConsumer, "CSMS_SYNC_INTERVAL", 0.05),
        ):
            communicator = WebsocketCommunicator(self.app, "/ws/ocpp/301")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await self._wait_for(lambda: "ws://mock-a/CP301A" in factory.by_url)
            self.assertNotIn("ws://mock-b/CP301B", factory.by_url)
            ws_a = factory.by_url["ws://mock-a/CP301A"]

            # Hot-add MockB while station remains connected.
            await sync_to_async(ChargePointCSMS.objects.get_or_create)(
                charge_point=self.cp,
                csms_service=self.csms_b,
                defaults={"remote_cp_id": "CP301B"},
            )
            await self._wait_for(lambda: "ws://mock-b/CP301B" in factory.by_url)
            ws_b = factory.by_url["ws://mock-b/CP301B"]

            # Verify a station call is now forwarded to both A and B.
            await communicator.send_json_to([2, "hb-add-1", "Heartbeat", {}])
            _ = await communicator.receive_json_from()
            await self._wait_for(
                lambda: any(f[1] == "hb-add-1" for f in ws_a.sent)
                and any(f[1] == "hb-add-1" for f in ws_b.sent)
            )

            # Hot-remove MockA while station remains connected.
            await sync_to_async(ChargePointCSMS.objects.filter(
                charge_point=self.cp, csms_service=self.csms_a
            ).delete)()
            await self._wait_for(lambda: ws_a._closed is True)

            # Next station call should only go to MockB.
            a_count_before = len([f for f in ws_a.sent if f[1] == "hb-rm-1"])
            await communicator.send_json_to([2, "hb-rm-1", "Heartbeat", {}])
            _ = await communicator.receive_json_from()
            await self._wait_for(lambda: any(f[1] == "hb-rm-1" for f in ws_b.sent))
            a_count_after = len([f for f in ws_a.sent if f[1] == "hb-rm-1"])
            self.assertEqual(a_count_before, a_count_after)

            await communicator.disconnect()

    async def test_paid_session_hides_station_as_no_connection(self):
        factory = FakeWebsocketsFactory()

        with (
            patch("account.consumers.websockets.connect", new=factory.connect),
            patch.object(OCPPConsumer, "CSMS_SYNC_INTERVAL", 0.05),
        ):
            communicator = WebsocketCommunicator(self.app, "/ws/ocpp/301")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            ws_a = factory.by_url["ws://mock-a/CP301A"]
            ws_b = factory.by_url["ws://mock-b/CP301B"]

            # Mark as local paid session.
            await communicator.send_json_to(
                [
                    2,
                    "start-payment-1",
                    "StartTransaction",
                    {
                        "connectorId": 1,
                        "idTag": "payment_123",
                        "meterStart": 0,
                        "timestamp": datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                    },
                ]
            )
            start_res = await communicator.receive_json_from()
            self.assertEqual(start_res[0], 3)
            self.assertEqual(start_res[1], "start-payment-1")

            # Sync loop should disconnect all CSMS links.
            await self._wait_for(lambda: ws_a._closed is True and ws_b._closed is True)

            await communicator.disconnect()

    async def test_external_owner_kept_others_hidden_as_no_connection(self):
        factory = FakeWebsocketsFactory()

        with (
            patch("account.consumers.websockets.connect", new=factory.connect),
            patch.object(OCPPConsumer, "CSMS_SYNC_INTERVAL", 0.05),
        ):
            communicator = WebsocketCommunicator(self.app, "/ws/ocpp/301")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            ws_a = factory.by_url["ws://mock-a/CP301A"]
            ws_b = factory.by_url["ws://mock-b/CP301B"]

            # External flow started by MockA.
            ws_a.push_incoming(
                [
                    2,
                    "remote-start-owner-a",
                    "RemoteStartTransaction",
                    {"connectorId": 1, "idTag": "TAG-A"},
                ]
            )
            forwarded = await communicator.receive_json_from()
            self.assertEqual(forwarded[1], "remote-start-owner-a")
            await communicator.send_json_to(
                [3, "remote-start-owner-a", {"status": "Accepted"}]
            )

            await communicator.send_json_to(
                [
                    2,
                    "start-ext-1",
                    "StartTransaction",
                    {
                        "connectorId": 1,
                        "idTag": "TAG-A",
                        "meterStart": 0,
                        "timestamp": datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                    },
                ]
            )
            start_res = await communicator.receive_json_from()
            self.assertEqual(start_res[0], 3)
            self.assertEqual(start_res[1], "start-ext-1")

            # Sync loop should keep owner A, disconnect B.
            await self._wait_for(lambda: ws_b._closed is True)
            self.assertFalse(ws_a._closed)

            # New station heartbeat should be forwarded to owner only.
            await communicator.send_json_to([2, "hb-owner-only-1", "Heartbeat", {}])
            _ = await communicator.receive_json_from()
            await self._wait_for(
                lambda: any(f[1] == "hb-owner-only-1" for f in ws_a.sent)
            )
            self.assertFalse(any(f[1] == "hb-owner-only-1" for f in ws_b.sent))

            await communicator.disconnect()

    async def test_remote_stop_restores_station_tx_from_db_mapping(self):
        factory = FakeWebsocketsFactory()

        with patch("account.consumers.websockets.connect", new=factory.connect):
            communicator = WebsocketCommunicator(self.app, "/ws/ocpp/301")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            ws_a = factory.by_url["ws://mock-a/CP301A"]

            # Simulate persisted mapping from previous runtime.
            await sync_to_async(CSMSTransactionMapping.objects.create)(
                charge_point=self.cp,
                csms_name="MockA",
                csms_transaction_id=3304752,
                station_transaction_id=44314,
                id_tag="TAG-A",
                is_active=True,
            )

            # RemoteStop with CSMS tx should be rewritten to station tx.
            ws_a.push_incoming(
                [
                    2,
                    "remote-stop-restore-1",
                    "RemoteStopTransaction",
                    {"transactionId": 3304752},
                ]
            )
            forwarded = await communicator.receive_json_from()
            self.assertEqual(forwarded[0], 2)
            self.assertEqual(forwarded[1], "remote-stop-restore-1")
            self.assertEqual(forwarded[2], "RemoteStopTransaction")
            self.assertEqual(forwarded[3]["transactionId"], 44314)

            await communicator.disconnect()

    async def test_station_stop_is_forwarded_to_connected_csms_with_mapping_fallback(self):
        factory = FakeWebsocketsFactory()

        with patch("account.consumers.websockets.connect", new=factory.connect):
            communicator = WebsocketCommunicator(self.app, "/ws/ocpp/301")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            ws_a = factory.by_url["ws://mock-a/CP301A"]
            ws_b = factory.by_url["ws://mock-b/CP301B"]

            await sync_to_async(CSMSTransactionMapping.objects.create)(
                charge_point=self.cp,
                csms_name="MockA",
                csms_transaction_id=3331160,
                station_transaction_id=794279,
                id_tag="TAG-A",
                is_active=True,
            )
            await sync_to_async(CSMSTransactionMapping.objects.create)(
                charge_point=self.cp,
                csms_name="MockB",
                csms_transaction_id=8899001,
                station_transaction_id=794279,
                id_tag="TAG-B",
                is_active=True,
            )

            await communicator.send_json_to(
                [
                    2,
                    "stop-fwd-1",
                    "StopTransaction",
                    {
                        "transactionId": 794279,
                        "meterStop": 14220,
                        "timestamp": datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        "reason": "Other",
                    },
                ]
            )
            stop_res = await communicator.receive_json_from()
            self.assertEqual(stop_res, [3, "stop-fwd-1", {}])

            await self._wait_for(
                lambda: any(f[1] == "stop-fwd-1" and f[2] == "StopTransaction" for f in ws_a.sent)
                and any(f[1] == "stop-fwd-1" and f[2] == "StopTransaction" for f in ws_b.sent)
            )

            stop_a = [f for f in ws_a.sent if f[1] == "stop-fwd-1" and f[2] == "StopTransaction"][-1]
            stop_b = [f for f in ws_b.sent if f[1] == "stop-fwd-1" and f[2] == "StopTransaction"][-1]
            self.assertEqual(stop_a[3]["transactionId"], 3331160)
            self.assertEqual(stop_b[3]["transactionId"], 8899001)

            await communicator.disconnect()
