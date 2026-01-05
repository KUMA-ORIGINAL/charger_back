# import json
# import uuid
# import logging
# from datetime import datetime, timezone
#
# from channels.db import database_sync_to_async
# from channels.generic.websocket import AsyncWebsocketConsumer
#
# from account.models import ChargePoint
#
# logger = logging.getLogger("ocpp")
#
#
# class OCPPConsumer(AsyncWebsocketConsumer):
#     """
#     OCPP 1.6 JSON – working CSMS
#     """
#
#     # ============================================================
#     # CONNECTION
#     # ============================================================
#     async def connect(self):
#         self.cp_id = self.scope["url_route"]["kwargs"]["cp_id"]
#
#         # connectorId -> transactionId
#         self.active_transactions = {}
#
#         await self.channel_layer.group_add(self.cp_id, self.channel_name)
#         logger.info(f"[CONNECT] CP={self.cp_id}")
#
#         await self.accept()
#
#     async def disconnect(self, close_code):
#         await self.channel_layer.group_discard(self.cp_id, self.channel_name)
#         logger.info(f"[DISCONNECT] CP={self.cp_id}")
#
#     # ============================================================
#     # RECEIVE FROM CP
#     # ============================================================
#     async def receive(self, text_data=None, bytes_data=None):
#         logger.info(f"[RECV] CP={self.cp_id} RAW={text_data}")
#
#         try:
#             frame = json.loads(text_data)
#         except Exception as e:
#             logger.error(f"[ERROR] CP={self.cp_id} JSON error: {e}")
#             return
#
#         if not isinstance(frame, list) or len(frame) < 3:
#             logger.warning(f"[WARN] CP={self.cp_id} Invalid frame")
#             return
#
#         msg_type = frame[0]
#
#         if msg_type == 2:
#             await self._handle_call(frame)
#         elif msg_type == 3:
#             await self._handle_call_result(frame)
#         elif msg_type == 4:
#             await self._handle_call_error(frame)
#
#     # ============================================================
#     # CALL (CP → CSMS)
#     # ============================================================
#     async def _handle_call(self, frame):
#         _, message_id, action, payload = frame
#
#         logger.info(
#             f"[CALL] CP={self.cp_id} ACTION={action} PAYLOAD={payload}"
#         )
#
#         handlers = {
#             "BootNotification": self.on_boot_notification,
#             "Heartbeat": self.on_heartbeat,
#             "Authorize": self.on_authorize,
#             "StatusNotification": self.on_status_notification,
#             "StartTransaction": self.on_start_transaction,
#             "StopTransaction": self.on_stop_transaction,
#             "MeterValues": self.on_meter_values,
#         }
#
#         handler = handlers.get(action)
#         response_payload = await handler(payload) if handler else {}
#
#         response = [3, message_id, response_payload]
#
#         logger.info(f"[SEND] CP={self.cp_id} CALLRESULT={response}")
#         await self.send(text_data=json.dumps(response))
#
#     # ============================================================
#     # CALLRESULT (CP → CSMS)
#     # ============================================================
#     async def _handle_call_result(self, frame):
#         _, message_id, payload = frame
#         logger.info(
#             f"[CALLRESULT] CP={self.cp_id} MSG_ID={message_id} PAYLOAD={payload}"
#         )
#
#     # ============================================================
#     # CALLERROR
#     # ============================================================
#     async def _handle_call_error(self, frame):
#         _, message_id, error_code, error_desc, details = frame
#         logger.error(
#             f"[CALLERROR] CP={self.cp_id} MSG_ID={message_id} "
#             f"CODE={error_code} DESC={error_desc} DETAILS={details}"
#         )
#
#     # ============================================================
#     # HANDLERS
#     # ============================================================
#     async def on_boot_notification(self, payload):
#         return {
#             "currentTime": self._now(),
#             "interval": 30,
#             "status": "Accepted",
#         }
#
#     async def on_heartbeat(self, payload):
#         return {
#             "currentTime": self._now(),
#         }
#
#     async def on_authorize(self, payload):
#         id_tag = payload.get("idTag")
#         logger.info(f"[AUTHORIZE] CP={self.cp_id} idTag={id_tag}")
#
#         return {
#             "idTagInfo": {
#                 "status": "Accepted"
#             }
#         }
#
#     async def on_status_notification(self, payload):
#         connector_id = payload.get("connectorId")
#         status = payload.get("status")
#
#         logger.info(
#             f"[STATUS] CP={self.cp_id} connector={connector_id} status={status}"
#         )
#         return {}
#
#     async def on_start_transaction(self, payload):
#         connector_id = payload.get("connectorId")
#
#         transaction_id = int(uuid.uuid4().int % 1_000_000)
#
#         logger.info(
#             f"[START] CP={self.cp_id} connector={connector_id} tx={transaction_id}"
#         )
#
#         # 🔥 СОХРАНЯЕМ В БД
#         await database_sync_to_async(
#             ChargePoint.objects.filter(cp_id=self.cp_id).update
#         )(active_transaction_id=transaction_id)
#
#         return {
#             "transactionId": transaction_id,
#             "idTagInfo": {
#                 "status": "Accepted"
#             },
#         }
#
#     async def on_stop_transaction(self, payload):
#         transaction_id = payload.get("transactionId")
#
#         logger.info(f"[STOP] CP={self.cp_id} tx={transaction_id}")
#
#         await database_sync_to_async(
#             ChargePoint.objects.filter(cp_id=self.cp_id).update
#         )(active_transaction_id=None)
#
#         return {}
#
#     async def on_meter_values(self, payload):
#         transaction_id = payload.get("transactionId")
#         meter_values = payload.get("meterValue", [])
#
#         for entry in meter_values:
#             ts = entry.get("timestamp")
#             for sv in entry.get("sampledValue", []):
#                 logger.info(
#                     f"[METER] CP={self.cp_id} TX={transaction_id} "
#                     f"{sv.get('measurand')}={sv.get('value')} {sv.get('unit')} "
#                     f"context={sv.get('context')}"
#                 )
#         return {}
#
#     # ============================================================
#     # SEND CSMS → CP
#     # ============================================================
#     async def send_ocpp(self, event):
#         frame = [
#             2,
#             event["message_id"],
#             event["action"],
#             event.get("payload", {}),
#         ]
#
#         logger.info(f"[SEND] CP={self.cp_id} CALL={frame}")
#         await self.send(text_data=json.dumps(frame))
#
#     # ============================================================
#     # UTILS
#     # ============================================================
#     @staticmethod
#     def _now():
#         return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


import json
import logging
import asyncio
from datetime import datetime, timezone

import websockets
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from account.models import ChargePoint

logger = logging.getLogger("ocpp")


class OCPPConsumer(AsyncWebsocketConsumer):
    """
    OCPP 1.6 JSON – Proxy / Relay CSMS
    """

    # ============================================================
    # CONNECTION
    # ============================================================
    async def connect(self):
        self.cp_id = self.scope["url_route"]["kwargs"]["cp_id"]

        # --- load ChargePoint ---
        try:
            self.charge_point = await database_sync_to_async(
                ChargePoint.objects.get
            )(cp_id=self.cp_id)
        except ChargePoint.DoesNotExist:
            logger.error(f"[REJECT] Unknown CP={self.cp_id}")
            await self.close(code=4001)
            return

        if not self.charge_point.charge24_cp_id:
            logger.error(f"[REJECT] CP={self.cp_id} no charge24_cp_id")
            await self.close(code=4002)
            return

        self.charge24_cp_id = self.charge_point.charge24_cp_id

        # --- connect to Charge24 ---
        try:
            self.remote_ws = await websockets.connect(
                f"wss://charge24.app/c/{self.charge24_cp_id}",
                subprotocols=["ocpp1.6"],
            )
        except Exception as e:
            logger.error(
                f"[CHARGE24 CONNECT ERROR] CP={self.cp_id} {e}"
            )
            await self.close(code=4003)
            return

        # start listener
        self.remote_task = asyncio.create_task(self._listen_charge24())

        await self.accept()
        logger.info(
            f"[CONNECTED] CP={self.cp_id} → Charge24={self.charge24_cp_id}"
        )

    async def disconnect(self, close_code):
        if hasattr(self, "remote_task"):
            self.remote_task.cancel()

        if hasattr(self, "remote_ws"):
            await self.remote_ws.close()

        logger.info(f"[DISCONNECT] CP={self.cp_id}")

    # ============================================================
    # RECEIVE FROM STATION → SEND TO CHARGE24
    # ============================================================
    async def receive(self, text_data=None, bytes_data=None):
        logger.info(
            f"[CP → PROXY] CP={self.cp_id} RAW={text_data}"
        )

        # 🔥 forward as-is
        try:
            await self.remote_ws.send(text_data)
        except Exception as e:
            logger.error(
                f"[SEND TO CHARGE24 ERROR] CP={self.cp_id} {e}"
            )

    # ============================================================
    # RECEIVE FROM CHARGE24 → SEND TO STATION
    # ============================================================
    async def _listen_charge24(self):
        try:
            async for message in self.remote_ws:
                logger.info(
                    f"[CHARGE24 → PROXY] CP={self.cp_id} RAW={message}"
                )

                await self.send(text_data=message)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(
                f"[CHARGE24 WS ERROR] CP={self.cp_id} {e}"
            )
            await self.close()

    # ============================================================
    # UTILS
    # ============================================================
    @staticmethod
    def _now():
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
