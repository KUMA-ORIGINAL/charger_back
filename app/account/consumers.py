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

#
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


# consumers.py
# import logging
# import asyncio
# import json
# from datetime import datetime, timezone
# from decimal import Decimal
#
# import websockets
# from channels.db import database_sync_to_async
# from channels.generic.websocket import AsyncWebsocketConsumer
#
# from account.models import ChargePoint, ChargePointCSMS, ChargingSession
#
# logger = logging.getLogger("ocpp")
#
#
# class OCPPConsumer(AsyncWebsocketConsumer):
#     """
#     OCPP 1.6 JSON – Multi-CSMS Proxy
#
#     Все CSMS равноправны:
#     - Любой CSMS может занять станцию
#     - Occupied = только во время charging
#     - Оплата ≠ занятость
#     """
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.remote_connections = {}      # csms_name -> websocket
#         self.remote_tasks = []
#         self.monitoring_task = None
#         self.active_session = None
#         self.processing_commands = set()  # защита от дублей
#
#     # ============================================================
#     # CONNECTION
#     # ============================================================
#
#     async def connect(self):
#         self.cp_id = self.scope["url_route"]["kwargs"]["cp_id"]
#
#         try:
#             self.charge_point = await database_sync_to_async(
#                 ChargePoint.objects.get
#             )(cp_id=self.cp_id)
#         except ChargePoint.DoesNotExist:
#             logger.error(f"[REJECT] Unknown CP={self.cp_id}")
#             await self.close(code=4001)
#             return
#
#         csms_configs = await self._get_csms_configs()
#         if not csms_configs:
#             logger.error(f"[REJECT] CP={self.cp_id} no CSMS configured")
#             await self.close(code=4002)
#             return
#
#         for config in csms_configs:
#             await self._connect_to_csms(config)
#
#         if not self.remote_connections:
#             logger.error(f"[REJECT] CP={self.cp_id} no CSMS connected")
#             await self.close(code=4003)
#             return
#
#         self.active_session = await self._get_active_session()
#         self.monitoring_task = asyncio.create_task(self._monitor_billing())
#
#         await self.accept(subprotocol="ocpp1.6")
#
#         logger.info(
#             f"[CONNECTED] CP={self.cp_id} → CSMS: {', '.join(self.remote_connections.keys())}"
#         )
#
#     async def disconnect(self, close_code):
#         if self.monitoring_task:
#             self.monitoring_task.cancel()
#
#         for task in self.remote_tasks:
#             task.cancel()
#
#         for name, ws in self.remote_connections.items():
#             try:
#                 await ws.close()
#                 logger.info(f"[CSMS CLOSED] {name}")
#             except Exception:
#                 pass
#
#         logger.info(f"[DISCONNECT] CP={self.cp_id} code={close_code}")
#
#     # ============================================================
#     # CSMS
#     # ============================================================
#
#     @database_sync_to_async
#     def _get_csms_configs(self):
#         configs = ChargePointCSMS.objects.filter(
#             charge_point=self.charge_point,
#             csms_service__is_active=True,
#         ).select_related("csms_service")
#
#         return [
#             {
#                 "name": c.csms_service.name,
#                 "url": c.csms_service.ws_url_template.format(cp_id=c.remote_cp_id),
#             }
#             for c in configs
#         ]
#
#     async def _connect_to_csms(self, config):
#         try:
#             ws = await websockets.connect(
#                 config["url"],
#                 subprotocols=["ocpp1.6"],
#                 ping_interval=30,
#                 ping_timeout=10,
#             )
#
#             self.remote_connections[config["name"]] = ws
#             task = asyncio.create_task(self._listen_csms(config["name"], ws))
#             self.remote_tasks.append(task)
#
#             logger.info(f"[CSMS CONNECTED] {config['name']}")
#
#         except Exception as e:
#             logger.error(f"[CSMS CONNECT ERROR] {config['name']}: {e}")
#
#     async def _listen_csms(self, csms_name, ws):
#         try:
#             async for raw in ws:
#                 logger.info(f"[{csms_name} → STATION] {raw}")
#
#                 try:
#                     msg = json.loads(raw)
#                 except json.JSONDecodeError:
#                     continue
#
#                 if msg[0] == 2:
#                     action = msg[2]
#
#                     if action == "RemoteStartTransaction":
#                         if await self._is_station_occupied():
#                             logger.warning(
#                                 f"[BLOCKED] {csms_name} RemoteStartTransaction – occupied"
#                             )
#                             continue
#
#                     if action == "RemoteStopTransaction":
#                         logger.info(
#                             f"[REMOTE STOP] from {csms_name}"
#                         )
#
#                 await self.send(text_data=raw)
#
#         except asyncio.CancelledError:
#             pass
#         except Exception as e:
#             logger.error(f"[CSMS WS ERROR] {csms_name}: {e}")
#
#     # ============================================================
#     # STATION → PROXY
#     # ============================================================
#
#     async def receive(self, text_data=None, bytes_data=None):
#         logger.info(f"[STATION → PROXY] {text_data}")
#
#         try:
#             msg = json.loads(text_data)
#         except json.JSONDecodeError:
#             return
#
#         if msg[0] == 2:
#             await self._handle_station_call(msg)
#
#         await self._forward_to_all_csms(text_data)
#
#     async def _handle_station_call(self, msg):
#         action = msg[2]
#         payload = msg[3]
#
#         if action == "StatusNotification":
#             await self._handle_status(payload)
#
#         elif action == "MeterValues":
#             await self._handle_meter_values(payload)
#
#         elif action == "StartTransaction":
#             await self._on_transaction_started(payload)
#
#         elif action == "StopTransaction":
#             await self._on_transaction_stopped(payload)
#
#     # ============================================================
#     # STATUS / METER
#     # ============================================================
#
#     async def _handle_status(self, payload):
#         status = payload.get("status")
#         logger.info(f"[STATUS] {status}")
#
#         if status == "Preparing":
#             self.active_session = await self._get_active_session()
#
#         elif status == "Available" and not self.active_session:
#             await self._mark_station_available()
#
#     async def _handle_meter_values(self, payload):
#         if not self.active_session or self.active_session.status != "charging":
#             return
#
#         for mv in payload.get("meterValue", []):
#             for sv in mv.get("sampledValue", []):
#                 if sv.get("measurand") == "Energy.Active.Import.Register":
#                     await self._update_session_consumption(
#                         Decimal(sv["value"])
#                     )
#
#     # ============================================================
#     # TRANSACTIONS
#     # ============================================================
#
#     @database_sync_to_async
#     def _on_transaction_started(self, payload):
#         transaction_id = payload.get("transactionId")
#         id_tag = payload.get("idTag")
#         meter_start = Decimal(str(payload.get("meterStart", 0)))
#
#         self.charge_point.is_occupied = True
#         self.charge_point.save()
#
#         if self.active_session and id_tag == f"payment_{self.active_session.id}":
#             self.active_session.transaction_id = transaction_id
#             self.active_session.status = "charging"
#             self.active_session.started_at = timezone.now()
#             self.active_session.start_meter_value = meter_start
#             self.active_session.last_meter_value = meter_start
#             self.active_session.save()
#
#             logger.info(
#                 f"[TRANSACTION STARTED] session={self.active_session.id} tx={transaction_id}"
#             )
#         else:
#             logger.info(f"[EXTERNAL TRANSACTION STARTED] tx={transaction_id}")
#
#     @database_sync_to_async
#     def _on_transaction_stopped(self, payload):
#         transaction_id = payload.get("transactionId")
#         meter_stop = payload.get("meterStop")
#
#         self.charge_point.is_occupied = False
#         self.charge_point.save()
#
#         if self.active_session and self.active_session.transaction_id == transaction_id:
#             if meter_stop:
#                 self.active_session.update_consumption(meter_stop)
#
#             self.active_session.status = "completed"
#             self.active_session.stopped_at = timezone.now()
#             self.active_session.save()
#
#             logger.info(
#                 f"[TRANSACTION STOPPED] session={self.active_session.id} tx={transaction_id}"
#             )
#             self.active_session = None
#         else:
#             logger.info(f"[EXTERNAL TRANSACTION STOPPED] tx={transaction_id}")
#
#     # ============================================================
#     # BILLING
#     # ============================================================
#
#     async def _update_session_consumption(self, meter_wh):
#         session = await database_sync_to_async(
#             ChargingSession.objects.select_for_update().get
#         )(id=self.active_session.id)
#
#         session.update_consumption(meter_wh)
#         await database_sync_to_async(session.save)()
#
#         self.active_session = session
#
#         logger.info(
#             f"[BILLING] session={session.id} "
#             f"kWh={session.consumed_kwh:.3f} "
#             f"cost={session.total_cost:.2f} "
#             f"balance={session.remaining_balance:.2f}"
#         )
#
#     async def _monitor_billing(self):
#         while True:
#             try:
#                 await asyncio.sleep(5)
#
#                 if self.active_session and self.active_session.status == "charging":
#                     self.active_session = await self._get_active_session()
#
#                     if not self.active_session.can_continue_charging:
#                         logger.warning(
#                             f"[BILLING STOP] session={self.active_session.id}"
#                         )
#                         await self._stop_charging()
#
#             except asyncio.CancelledError:
#                 break
#
#     async def _stop_charging(self):
#         if not self.active_session or not self.active_session.transaction_id:
#             return
#
#         msg = [
#             2,
#             f"remote_stop_{int(datetime.now().timestamp())}",
#             "RemoteStopTransaction",
#             {"transactionId": self.active_session.transaction_id},
#         ]
#
#         await self._forward_to_all_csms(json.dumps(msg))
#
#     # ============================================================
#     # FORWARDING
#     # ============================================================
#
#     async def _forward_to_all_csms(self, message):
#         if await self._is_station_occupied():
#             await self._broadcast_occupied()
#
#         for ws in self.remote_connections.values():
#             await ws.send(message)
#
#     async def _broadcast_occupied(self):
#         msg = [
#             2,
#             f"occupied_{int(datetime.now().timestamp())}",
#             "StatusNotification",
#             {
#                 "connectorId": 1,
#                 "errorCode": "NoError",
#                 "status": "Occupied",
#                 "timestamp": self._now(),
#             },
#         ]
#         raw = json.dumps(msg)
#
#         for ws in self.remote_connections.values():
#             await ws.send(raw)
#
#     # ============================================================
#     # HELPERS
#     # ============================================================
#
#     @database_sync_to_async
#     def _get_active_session(self):
#         return ChargingSession.objects.filter(
#             charge_point=self.charge_point,
#             status__in=["preparing", "charging"],
#         ).first()
#
#     @database_sync_to_async
#     def _is_station_occupied(self):
#         self.charge_point.refresh_from_db()
#         return self.charge_point.is_occupied
#
#     @database_sync_to_async
#     def _mark_station_available(self):
#         self.charge_point.is_occupied = False
#         self.charge_point.save()
#
#     @staticmethod
#     def _now():
#         return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
