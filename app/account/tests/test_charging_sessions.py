import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from account.consumers import OCPPConsumer  # noqa: F401  (routing import side effect)
from account.models import (
    ChargePoint,
    ChargePointCSMS,
    ChargingSession,
    ChargingSessionMeterValue,
    CSMSService,
)
from account.ocpp_routing import websocket_urlpatterns
from account.tests.test_consumers import (
    TEST_CHANNEL_LAYERS,
    FakeWebsocketsFactory,
)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _meter_frame(msg_id: str, tx_id: int, energy_wh, soc=None, power_w=None):
    sampled = [
        {
            "measurand": "Energy.Active.Import.Register",
            "value": str(energy_wh),
            "unit": "Wh",
        }
    ]
    if soc is not None:
        sampled.append({"measurand": "SoC", "value": str(soc), "unit": "Percent"})
    if power_w is not None:
        sampled.append(
            {"measurand": "Power.Active.Import", "value": str(power_w), "unit": "W"}
        )
    return [
        2,
        msg_id,
        "MeterValues",
        {
            "connectorId": 1,
            "transactionId": tx_id,
            "meterValue": [{"timestamp": _ts(), "sampledValue": sampled}],
        },
    ]


class MeterValueParsingTests(SimpleTestCase):
    """Разбор sampledValue из OCPP MeterValues."""

    def test_units_are_normalized(self):
        parsed = ChargingSessionMeterValue.parse_sampled_values(
            [
                {
                    "measurand": "Energy.Active.Import.Register",
                    "value": "3.5",
                    "unit": "kWh",
                },
                {"measurand": "Power.Active.Import", "value": "22000", "unit": "W"},
                {"measurand": "SoC", "value": "41", "unit": "Percent"},
                {"measurand": "Voltage", "value": "398.2"},
                {"measurand": "Current.Import", "value": "55.1"},
                {"measurand": "Temperature", "value": "34"},
            ]
        )
        self.assertEqual(parsed["energy_wh"], Decimal("3500.0"))
        self.assertEqual(parsed["power_kw"], Decimal("22"))
        self.assertEqual(parsed["soc"], Decimal("41"))
        self.assertEqual(parsed["voltage"], Decimal("398.2"))
        self.assertEqual(parsed["current"], Decimal("55.1"))
        self.assertEqual(parsed["temperature"], Decimal("34"))

    def test_missing_measurand_defaults_to_energy(self):
        parsed = ChargingSessionMeterValue.parse_sampled_values(
            [{"value": "12500", "unit": "Wh"}]
        )
        self.assertEqual(parsed, {"energy_wh": Decimal("12500")})

    def test_unknown_and_broken_values_are_skipped(self):
        parsed = ChargingSessionMeterValue.parse_sampled_values(
            [
                {"measurand": "RPM", "value": "900"},
                {"measurand": "SoC", "value": "n/a"},
                "not-a-dict",
            ]
        )
        self.assertEqual(parsed, {})


class ChargingSessionAggregateTests(SimpleTestCase):
    """Агрегаты сессии, считаемые из замеров."""

    def test_apply_meter_sample_tracks_soc_and_peak_power(self):
        session = ChargingSession(
            start_meter_value=Decimal("10000"),
            cost_per_kwh=Decimal("0"),
        )
        session.apply_meter_sample(
            {
                "energy_wh": Decimal("12500"),
                "soc": Decimal("41"),
                "power_kw": Decimal("22"),
            }
        )
        session.apply_meter_sample(
            {
                "energy_wh": Decimal("15000"),
                "soc": Decimal("55"),
                "power_kw": Decimal("11"),
            }
        )

        self.assertEqual(session.consumed_kwh, Decimal("5"))
        self.assertEqual(session.start_soc, Decimal("41"))
        self.assertEqual(session.last_soc, Decimal("55"))
        self.assertEqual(session.soc_gain, 14.0)
        self.assertEqual(session.max_power_kw, Decimal("22"))
        self.assertEqual(session.last_power_kw, Decimal("11"))

    def test_duration_display(self):
        session = ChargingSession(
            started_at=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            stopped_at=datetime(2026, 1, 1, 11, 5, 30, tzinfo=timezone.utc),
        )
        self.assertEqual(session.duration_seconds, 3930)
        self.assertEqual(session.duration_display, "1:05:30")


@override_settings(
    CHANNEL_LAYERS=TEST_CHANNEL_LAYERS,
    DEBUG_TOOLBAR_CONFIG={"IS_RUNNING_TESTS": False},
)
class ChargingSessionRecordingTests(TransactionTestCase):
    """Сессии зарядки пишутся в БД — и наши платные, и внешние (CSMS)."""

    def setUp(self):
        self.app = URLRouter(websocket_urlpatterns)

        self.cp, _ = ChargePoint.objects.get_or_create(
            cp_id="301", name="Test CP 301"
        )
        self.csms_a, _ = CSMSService.objects.get_or_create(
            name="MockA",
            defaults={
                "service_type": CSMSService.ServiceType.OTHER,
                "is_active": True,
                "ws_url_template": "ws://mock-a/{cp_id}",
            },
        )
        ChargePointCSMS.objects.get_or_create(
            charge_point=self.cp,
            csms_service=self.csms_a,
            defaults={"remote_cp_id": "CP301A"},
        )

    # ------------------------------------------------------------------
    #  helpers
    # ------------------------------------------------------------------

    async def _poll_session(self, session, check, timeout=3.0):
        """Дождаться, пока перечитанная из БД сессия удовлетворит условию."""
        deadline = asyncio.get_running_loop().time() + timeout
        refreshed = await self._reload(session)
        while not check(refreshed):
            if asyncio.get_running_loop().time() > deadline:
                self.fail(f"Timed out waiting for session {session.id}: {refreshed}")
            await asyncio.sleep(0.02)
            refreshed = await self._reload(session)
        return refreshed

    @sync_to_async
    def _sessions(self, **filters):
        return list(ChargingSession.objects.filter(**filters))

    async def _poll_sessions(self, count, timeout=3.0, **filters):
        """
        Дождаться нужного числа сессий: станции ответ уходит до записи
        в БД, поэтому сразу после CALLRESULT строки может ещё не быть.
        """
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            sessions = await self._sessions(**filters)
            if len(sessions) == count:
                return sessions
            if asyncio.get_running_loop().time() > deadline:
                self.fail(
                    f"Timed out waiting for {count} session(s) {filters}: "
                    f"got {len(sessions)}"
                )
            await asyncio.sleep(0.02)

    @sync_to_async
    def _reload(self, session):
        return ChargingSession.objects.get(id=session.id)

    @sync_to_async
    def _meter_values(self, session):
        return list(
            ChargingSessionMeterValue.objects.filter(session=session).order_by(
                "sampled_at"
            )
        )

    async def _start_external_session(self, communicator, ws_a, meter_start=1000):
        """RemoteStart от CSMS → StartTransaction от станции."""
        ws_a.push_incoming(
            [
                2,
                "remote-start-a",
                "RemoteStartTransaction",
                {"connectorId": 1, "idTag": "TAG-A"},
            ]
        )
        await communicator.receive_json_from()
        await communicator.send_json_to([3, "remote-start-a", {"status": "Accepted"}])

        await communicator.send_json_to(
            [
                2,
                "start-tx-1",
                "StartTransaction",
                {
                    "connectorId": 1,
                    "idTag": "TAG-A",
                    "meterStart": meter_start,
                    "timestamp": _ts(),
                },
            ]
        )
        result = await communicator.receive_json_from()
        return result[2]["transactionId"]

    # ------------------------------------------------------------------
    #  внешние сессии (Charge24 / Spark)
    # ------------------------------------------------------------------

    async def test_external_session_is_recorded_end_to_end(self):
        factory = FakeWebsocketsFactory()

        with patch("account.consumers.websockets.connect", new=factory.connect):
            communicator = WebsocketCommunicator(self.app, "/ws/ocpp/301")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            ws_a = factory.by_url["ws://mock-a/CP301A"]

            station_tx = await self._start_external_session(
                communicator, ws_a, meter_start=1000
            )

            # --- сессия создана в момент StartTransaction ---
            sessions = await self._poll_sessions(
                1, source=ChargingSession.SOURCE_CSMS
            )
            session = sessions[0]
            self.assertEqual(session.status, "charging")
            self.assertEqual(session.csms_name, "MockA")
            self.assertEqual(session.id_tag, "TAG-A")
            self.assertEqual(session.transaction_id, station_tx)
            self.assertEqual(session.start_meter_value, Decimal("1000"))
            self.assertIsNotNone(session.started_at)

            # --- CSMS вернул свой transactionId ---
            ws_a.push_incoming([3, "start-tx-1", {"transactionId": 3331160}])
            await self._poll_session(
                session, lambda s: s.csms_transaction_id == 3331160
            )

            # --- телеметрия ---
            await communicator.send_json_to(
                _meter_frame("mv-1", station_tx, 3000, soc=41, power_w=22000)
            )
            await communicator.receive_json_from()
            await communicator.send_json_to(
                _meter_frame("mv-2", station_tx, 5500, soc=55, power_w=11000)
            )
            await communicator.receive_json_from()

            refreshed = await self._poll_session(
                session, lambda s: s.last_soc == Decimal("55.0")
            )

            self.assertEqual(refreshed.consumed_kwh, Decimal("4.500"))
            self.assertEqual(refreshed.start_soc, Decimal("41.0"))
            self.assertEqual(refreshed.last_soc, Decimal("55.0"))
            self.assertEqual(refreshed.soc_gain, 14.0)
            self.assertEqual(refreshed.max_power_kw, Decimal("22.000"))
            self.assertEqual(refreshed.last_power_kw, Decimal("11.000"))
            self.assertIsNotNone(refreshed.last_meter_at)

            samples = await self._meter_values(session)
            self.assertEqual(len(samples), 2)
            self.assertEqual(samples[0].soc, Decimal("41.0"))
            self.assertEqual(samples[1].consumed_kwh, Decimal("4.500"))
            self.assertEqual(samples[1].power_kw, Decimal("11.000"))
            self.assertTrue(samples[0].raw)

            # --- закрытие сессии ---
            await communicator.send_json_to(
                [
                    2,
                    "stop-tx-1",
                    "StopTransaction",
                    {
                        "transactionId": station_tx,
                        "meterStop": 7000,
                        "timestamp": _ts(),
                        "reason": "Local",
                    },
                ]
            )
            await communicator.receive_json_from()

            refreshed = await self._poll_session(
                session, lambda s: s.status == "completed"
            )

            self.assertEqual(refreshed.stop_reason, "Local")
            self.assertEqual(refreshed.stop_meter_value, Decimal("7000"))
            self.assertEqual(refreshed.consumed_kwh, Decimal("6.000"))
            self.assertIsNotNone(refreshed.stopped_at)
            self.assertEqual(refreshed.total_cost, Decimal("0.00"))
            self.assertEqual(refreshed.owner_label, "MockA")

            await communicator.disconnect()

    async def test_second_external_start_closes_dangling_session(self):
        factory = FakeWebsocketsFactory()

        dangling = await sync_to_async(ChargingSession.objects.create)(
            charge_point=self.cp,
            source=ChargingSession.SOURCE_CSMS,
            csms_name="MockA",
            status="charging",
            started_at=datetime.now(timezone.utc),
        )

        with patch("account.consumers.websockets.connect", new=factory.connect):
            communicator = WebsocketCommunicator(self.app, "/ws/ocpp/301")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            ws_a = factory.by_url["ws://mock-a/CP301A"]

            await self._start_external_session(communicator, ws_a)

            refreshed = await self._poll_session(
                dangling, lambda s: s.status == "error"
            )

            self.assertEqual(refreshed.stop_reason, "superseded")
            self.assertIsNotNone(refreshed.stopped_at)

            await self._poll_sessions(
                1, source=ChargingSession.SOURCE_CSMS, status="charging"
            )

            await communicator.disconnect()

    # ------------------------------------------------------------------
    #  наши платные сессии
    # ------------------------------------------------------------------

    async def test_payment_session_keeps_billing_and_gains_telemetry(self):
        factory = FakeWebsocketsFactory()

        session = await sync_to_async(ChargingSession.objects.create)(
            charge_point=self.cp,
            source=ChargingSession.SOURCE_PAYMENT,
            status="preparing",
            initial_balance=Decimal("500"),
            cost_per_kwh=Decimal("12.00"),
        )

        with patch("account.consumers.websockets.connect", new=factory.connect):
            communicator = WebsocketCommunicator(self.app, "/ws/ocpp/301")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # станция сообщает Preparing → прокси сам шлёт RemoteStart
            await communicator.send_json_to(
                [
                    2,
                    "status-prep",
                    "StatusNotification",
                    {
                        "connectorId": 1,
                        "errorCode": "NoError",
                        "status": "Preparing",
                        "timestamp": _ts(),
                    },
                ]
            )
            self.assertEqual(
                (await communicator.receive_json_from())[1], "status-prep"
            )

            remote_start = await communicator.receive_json_from(timeout=5)
            self.assertEqual(remote_start[2], "RemoteStartTransaction")
            self.assertEqual(remote_start[3]["idTag"], f"payment_{session.id}")
            await communicator.send_json_to(
                [3, remote_start[1], {"status": "Accepted"}]
            )

            await communicator.send_json_to(
                [
                    2,
                    "start-pay-1",
                    "StartTransaction",
                    {
                        "connectorId": 1,
                        "idTag": f"payment_{session.id}",
                        "meterStart": 0,
                        "timestamp": _ts(),
                    },
                ]
            )
            result = await communicator.receive_json_from()
            station_tx = result[2]["transactionId"]

            await communicator.send_json_to(
                _meter_frame("mv-pay-1", station_tx, 2000, soc=30, power_w=7400)
            )
            await communicator.receive_json_from()

            refreshed = await self._poll_session(
                session, lambda s: s.consumed_kwh == Decimal("2.000")
            )

            self.assertEqual(refreshed.status, "charging")
            self.assertEqual(refreshed.consumed_kwh, Decimal("2.000"))
            self.assertEqual(refreshed.total_cost, Decimal("24.00"))
            self.assertEqual(refreshed.remaining_balance, 476.0)
            self.assertEqual(refreshed.last_soc, Decimal("30.0"))
            self.assertEqual(refreshed.last_power_kw, Decimal("7.400"))

            samples = await self._meter_values(session)
            self.assertEqual(len(samples), 1)

            await communicator.send_json_to(
                [
                    2,
                    "stop-pay-1",
                    "StopTransaction",
                    {
                        "transactionId": station_tx,
                        "meterStop": 3000,
                        "timestamp": _ts(),
                        "reason": "Remote",
                    },
                ]
            )
            await communicator.receive_json_from()

            refreshed = await self._poll_session(
                session, lambda s: s.status == "completed"
            )

            self.assertEqual(refreshed.stop_reason, "Remote")
            self.assertEqual(refreshed.consumed_kwh, Decimal("3.000"))
            self.assertEqual(refreshed.total_cost, Decimal("36.00"))

            # внешних сессий при своей оплате не появляется
            external = await self._sessions(source=ChargingSession.SOURCE_CSMS)
            self.assertEqual(external, [])

            await communicator.disconnect()

    async def test_external_session_resumed_after_reconnect(self):
        """
        Прокси перезапустился посреди чужой зарядки: станция занята, в БД
        висит открытая сессия — телеметрия должна продолжить писаться в неё.
        """
        factory = FakeWebsocketsFactory()

        await sync_to_async(ChargePoint.objects.filter(cp_id="301").update)(
            is_occupied=True, occupied_by="MockA", active_transaction_id=555001
        )
        session = await sync_to_async(ChargingSession.objects.create)(
            charge_point=self.cp,
            source=ChargingSession.SOURCE_CSMS,
            csms_name="MockA",
            status="charging",
            transaction_id=555001,
            id_tag="TAG-A",
            started_at=datetime.now(timezone.utc),
            start_meter_value=Decimal("1000"),
            last_meter_value=Decimal("1000"),
            cost_per_kwh=Decimal("0"),
        )

        with patch("account.consumers.websockets.connect", new=factory.connect):
            communicator = WebsocketCommunicator(self.app, "/ws/ocpp/301")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.send_json_to(
                _meter_frame("mv-r-1", 555001, 4000, soc=62, power_w=15000)
            )
            await communicator.receive_json_from()

            refreshed = await self._poll_session(
                session, lambda s: s.last_soc == Decimal("62.0")
            )

            self.assertEqual(refreshed.consumed_kwh, Decimal("3.000"))
            self.assertEqual(refreshed.last_soc, Decimal("62.0"))
            self.assertEqual(len(await self._meter_values(session)), 1)

            # новых сессий не создалось
            all_external = await self._sessions(
                source=ChargingSession.SOURCE_CSMS
            )
            self.assertEqual(len(all_external), 1)

            await communicator.disconnect()
