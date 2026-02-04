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
# import logging
# import asyncio
# from datetime import datetime, timezone
#
# import websockets
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
#     OCPP 1.6 JSON – Proxy / Relay CSMS
#     """
#
#     # ============================================================
#     # CONNECTION
#     # ============================================================
#     async def connect(self):
#         self.cp_id = self.scope["url_route"]["kwargs"]["cp_id"]
#
#         # --- load ChargePoint ---
#         try:
#             self.charge_point = await database_sync_to_async(
#                 ChargePoint.objects.get
#             )(cp_id=self.cp_id)
#         except ChargePoint.DoesNotExist:
#             logger.error(f"[REJECT] Unknown CP={self.cp_id}")
#             await self.close(code=4001)
#             return
#
#         if not self.charge_point.charge24_cp_id:
#             logger.error(f"[REJECT] CP={self.cp_id} no charge24_cp_id")
#             await self.close(code=4002)
#             return
#
#         self.charge24_cp_id = self.charge_point.charge24_cp_id
#
#         # --- connect to Charge24 ---
#         try:
#             self.remote_ws = await websockets.connect(
#                 f"wss://charge24.app/c/{self.charge24_cp_id}",
#                 subprotocols=["ocpp1.6"],
#             )
#         except Exception as e:
#             logger.error(
#                 f"[CHARGE24 CONNECT ERROR] CP={self.cp_id} {e}"
#             )
#             await self.close(code=4003)
#             return
#
#         # start listener
#         self.remote_task = asyncio.create_task(self._listen_charge24())
#
#         await self.accept()
#         logger.info(
#             f"[CONNECTED] CP={self.cp_id} → Charge24={self.charge24_cp_id}"
#         )
#
#     async def disconnect(self, close_code):
#         if hasattr(self, "remote_task"):
#             self.remote_task.cancel()
#
#         if hasattr(self, "remote_ws"):
#             await self.remote_ws.close()
#
#         logger.info(f"[DISCONNECT] CP={self.cp_id}")
#
#     # ============================================================
#     # RECEIVE FROM STATION → SEND TO CHARGE24
#     # ============================================================
#     async def receive(self, text_data=None, bytes_data=None):
#         logger.info(
#             f"[CP → PROXY] CP={self.cp_id} RAW={text_data}"
#         )
#
#         # 🔥 forward as-is
#         try:
#             await self.remote_ws.send(text_data)
#         except Exception as e:
#             logger.error(
#                 f"[SEND TO CHARGE24 ERROR] CP={self.cp_id} {e}"
#             )
#
#     # ============================================================
#     # RECEIVE FROM CHARGE24 → SEND TO STATION
#     # ============================================================
#     async def _listen_charge24(self):
#         try:
#             async for message in self.remote_ws:
#                 logger.info(
#                     f"[CHARGE24 → PROXY] CP={self.cp_id} RAW={message}"
#                 )
#
#                 await self.send(text_data=message)
#         except asyncio.CancelledError:
#             pass
#         except Exception as e:
#             logger.error(
#                 f"[CHARGE24 WS ERROR] CP={self.cp_id} {e}"
#             )
#             await self.close()
#
#     # ============================================================
#     # UTILS
#     # ============================================================
#     @staticmethod
#     def _now():
#         return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")



import logging
import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal

import websockets
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from account.models import ChargePoint, ChargePointCSMS, ChargingSession

logger = logging.getLogger("ocpp")


class OCPPConsumer(AsyncWebsocketConsumer):
    """
    OCPP 1.6 JSON – Multi-CSMS Proxy

    Все CSMS равноправны:
    - Любой CSMS может занять станцию
    - Occupied = только во время charging
    - Оплата ≠ занятость
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.remote_connections = {}  # csms_name -> websocket
        self.remote_tasks = []
        self.monitoring_task = None
        self.active_session = None

    # ============================================================
    # CONNECTION
    # ============================================================

    async def connect(self):
        self.cp_id = self.scope["url_route"]["kwargs"]["cp_id"]

        try:
            self.charge_point = await database_sync_to_async(
                ChargePoint.objects.get
            )(cp_id=self.cp_id)
        except ChargePoint.DoesNotExist:
            logger.error(f"[REJECT] Unknown CP={self.cp_id}")
            await self.close(code=4001)
            return

        csms_configs = await self._get_csms_configs()
        if not csms_configs:
            logger.error(f"[REJECT] CP={self.cp_id} no CSMS configured")
            await self.close(code=4002)
            return

        for config in csms_configs:
            await self._connect_to_csms(config)

        if not self.remote_connections:
            logger.error(f"[REJECT] CP={self.cp_id} no CSMS connected")
            await self.close(code=4003)
            return

        self.active_session = await self._get_active_session()

        # 🔥 ЗАПУСКАЕМ МОНИТОРИНГ ОПЛАТЫ
        self.monitoring_task = asyncio.create_task(self._monitor_session())

        await self.accept(subprotocol="ocpp1.6")

        logger.info(
            f"[CONNECTED] CP={self.cp_id} → CSMS: {', '.join(self.remote_connections.keys())}"
        )

        # 🔥 НЕМЕДЛЕННО СООБЩАЕМ ВСЕМ CSMS О ТЕКУЩЕМ СТАТУСЕ
        await self._notify_all_csms_current_status()

    async def disconnect(self, close_code):
        if self.monitoring_task:
            self.monitoring_task.cancel()

        for task in self.remote_tasks:
            task.cancel()

        for name, ws in self.remote_connections.items():
            try:
                await ws.close()
                logger.info(f"[CSMS CLOSED] {name}")
            except Exception:
                pass

        logger.info(f"[DISCONNECT] CP={self.cp_id} code={close_code}")

    # ============================================================
    # CSMS
    # ============================================================

    @database_sync_to_async
    def _get_csms_configs(self):
        configs = ChargePointCSMS.objects.filter(
            charge_point=self.charge_point,
            csms_service__is_active=True,
        ).select_related("csms_service")

        return [
            {
                "name": c.csms_service.name,
                "url": c.csms_service.ws_url_template.format(cp_id=c.remote_cp_id),
            }
            for c in configs
        ]

    async def _connect_to_csms(self, config):
        try:
            ws = await websockets.connect(
                config["url"],
                subprotocols=["ocpp1.6"],
                ping_interval=30,
                ping_timeout=10,
            )

            self.remote_connections[config["name"]] = ws
            task = asyncio.create_task(self._listen_csms(config["name"], ws))
            self.remote_tasks.append(task)

            logger.info(f"[CSMS CONNECTED] {config['name']}")

        except Exception as e:
            logger.error(f"[CSMS CONNECT ERROR] {config['name']}: {e}")

    async def _listen_csms(self, csms_name, ws):
        try:
            async for raw in ws:
                logger.info(f"[{csms_name} → STATION] {raw}")

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # Обрабатываем только Call (тип 2)
                if msg[0] == 2:
                    action = msg[2]

                    # 🔥 ПРОВЕРЯЕМ ДОПУСТИМОСТЬ КОМАНДЫ
                    if action in ["RemoteStartTransaction", "RemoteStopTransaction"]:
                        is_allowed = await self._check_command_allowed(csms_name, action, msg)
                        if not is_allowed:
                            # Отправляем ошибку этому CSMS
                            error_msg = [
                                4,  # CallError
                                msg[1],  # MessageId
                                "GenericError",
                                "Station is occupied by another CSMS",
                                {}
                            ]
                            await ws.send(json.dumps(error_msg))
                            continue

                    # Пересылаем на станцию
                    await self.send(text_data=raw)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[CSMS WS ERROR] {csms_name}: {e}")

    # ============================================================
    # STATION → PROXY
    # ============================================================

    async def receive(self, text_data=None, bytes_data=None):
        logger.info(f"[STATION → PROXY] {text_data}")
        try:
            msg = json.loads(text_data)
        except json.JSONDecodeError:
            return

        # обрабатываем входящие Call/Result как раньше
        if msg[0] == 2:
            await self._handle_station_call(msg)
        elif msg[0] == 3:
            await self._handle_station_response(msg)

        # 🔥 ОТПРАВЛЯЕМ СООБЩЕНИЯ ВСЕМ CSMS, НО С ФИЛЬТРАЦИЕЙ
        await self._forward_to_csms_filtered(text_data, msg)

    async def _forward_to_csms_filtered(self, text_data, msg):
        """Отправляет сообщение всем CSMS с фильтрацией"""

        # 🔥 НЕ отправляем Authorize с нашими payment_ тегами другим CSMS
        if (msg[0] == 2 and msg[2] == "Authorize" and
                isinstance(msg[3], dict) and
                msg[3].get("idTag", "").startswith("payment_")):
            logger.info(f"[FILTERED] Authorize with payment_ tag not forwarded to CSMS")
            return

        # 🔥 НЕ отправляем наши локальные сообщения
        if isinstance(msg[1], str) and msg[1].startswith("local_"):
            return

        # Все остальное отправляем всем CSMS
        for csms_name, ws in self.remote_connections.items():
            try:
                await ws.send(text_data)
            except Exception as e:
                logger.error(f"[FORWARD ERROR] {csms_name}: {e}")

    async def _handle_station_call(self, msg):
        action = msg[2]
        payload = msg[3]

        if action == "StatusNotification":
            await self._handle_status(payload)

        elif action == "MeterValues":
            await self._handle_meter_values(payload)

        elif action == "StartTransaction":
            await self._on_transaction_started(payload)

        elif action == "StopTransaction":
            await self._on_transaction_stopped(payload)

    async def _handle_station_response(self, msg):
        """Обрабатывает CallResult от станции"""
        message_id = msg[1]
        payload = msg[2]

        # Проверяем ответ на RemoteStartTransaction
        if message_id.startswith("local_start_"):
            status = payload.get("status")
            logger.info(f"[REMOTE START RESPONSE] status={status}")

            if status == "Accepted":
                logger.info(f"[REMOTE START ACCEPTED] session={self.active_session.id}")
            elif status == "Rejected":
                logger.warning(f"[REMOTE START REJECTED] session={self.active_session.id}")

        # Проверяем ответ на RemoteStopTransaction
        elif message_id.startswith("local_stop_"):
            status = payload.get("status")
            logger.info(f"[REMOTE STOP RESPONSE] status={status}")

    # ============================================================
    # STATUS / METER
    # ============================================================

    async def _handle_status(self, payload):
        status = payload.get("status")
        connector_id = payload.get("connectorId", 1)
        logger.info(f"[STATUS] {status} (connector={connector_id})")

        # 🔥 СОХРАНЯЕМ ТЕКУЩИЙ СТАТУС КОННЕКТОРА
        await self._update_connector_status(connector_id, status)

        # Обновляем active_session при статусе Preparing
        if status == "Preparing" and connector_id == 1:
            self.active_session = await self._get_active_session()

            # 🔥 АВТОСТАРТ: если есть оплаченная сессия
            if self.active_session and self.active_session.status == "preparing":
                logger.info(f"[AUTO START] Triggering RemoteStart for session={self.active_session.id}")
                await self._send_remote_start()

    async def _update_connector_status(self, connector_id, status):
        """Сохраняет статус коннектора для использования"""
        if not hasattr(self, 'connector_status'):
            self.connector_status = {}

        self.connector_status[connector_id] = status

    async def _handle_meter_values(self, payload):
        if not self.active_session or self.active_session.status != "charging":
            return

        for mv in payload.get("meterValue", []):
            for sv in mv.get("sampledValue", []):
                if sv.get("measurand") == "Energy.Active.Import.Register":
                    await self._update_session_consumption(
                        Decimal(sv["value"])
                    )

    # ============================================================
    # TRANSACTIONS
    # ============================================================

    @database_sync_to_async
    def _on_transaction_started(self, payload):
        transaction_id = payload.get("transactionId")
        id_tag = payload.get("idTag")
        meter_start = Decimal(str(payload.get("meterStart", 0)))

        # 🔥 УСТАНАВЛИВАЕМ ФЛАГ ЗАНЯТОСТИ
        self.charge_point.is_occupied = True
        self.charge_point.occupied_by = id_tag if id_tag.startswith("payment_") else "external"
        self.charge_point.save()

        if self.active_session and id_tag == f"payment_{self.active_session.id}":
            self.active_session.transaction_id = transaction_id
            self.active_session.status = "charging"
            self.active_session.started_at = timezone.now()
            self.active_session.start_meter_value = meter_start
            self.active_session.last_meter_value = meter_start
            self.active_session.save()

            logger.info(
                f"[TRANSACTION STARTED] session={self.active_session.id} tx={transaction_id}"
            )
        else:
            logger.info(f"[EXTERNAL TRANSACTION STARTED] tx={transaction_id}")

    @database_sync_to_async
    def _on_transaction_stopped(self, payload):
        transaction_id = payload.get("transactionId")
        meter_stop = payload.get("meterStop")

        # 🔥 СБРАСЫВАЕМ ФЛАГ ЗАНЯТОСТИ
        self.charge_point.is_occupied = False
        self.charge_point.occupied_by = None
        self.charge_point.save()

        if self.active_session and self.active_session.transaction_id == transaction_id:
            if meter_stop:
                self.active_session.update_consumption(meter_stop)

            self.active_session.status = "completed"
            self.active_session.stopped_at = timezone.now()
            self.active_session.save()

            logger.info(
                f"[TRANSACTION STOPPED] session={self.active_session.id} tx={transaction_id}"
            )
            self.active_session = None
        else:
            logger.info(f"[EXTERNAL TRANSACTION STOPPED] tx={transaction_id}")

    # ============================================================
    # BILLING & MONITORING
    # ============================================================

    async def _update_session_consumption(self, meter_wh):
        try:
            session = await database_sync_to_async(
                ChargingSession.objects.select_for_update().get
            )(id=self.active_session.id)

            session.update_consumption(meter_wh)
            await database_sync_to_async(session.save)()

            self.active_session = session

            logger.info(
                f"[BILLING] session={session.id} "
                f"kWh={session.consumed_kwh:.3f} "
                f"cost={session.total_cost:.2f} "
                f"balance={session.remaining_balance:.2f}"
            )
        except ChargingSession.DoesNotExist:
            logger.error(
                f"[BILLING ERROR] Session {self.active_session.id} not found"
            )
            self.active_session = None

    async def _monitor_session(self):
        """Мониторинг: проверяет оплату и баланс"""
        while True:
            try:
                await asyncio.sleep(2)

                # 🔥 ПРОВЕРЯЕМ ПОЯВЛЕНИЕ НОВОЙ ОПЛАЧЕННОЙ СЕССИИ
                if not self.active_session:
                    new_session = await self._get_active_session()

                    if new_session and new_session.status == "preparing":
                        self.active_session = new_session
                        logger.info(
                            f"[NEW SESSION DETECTED] session={self.active_session.id}"
                        )

                        # 🔥 УВЕДОМЛЯЕМ ВСЕХ CSMS ЧТО СТАНЦИЯ ЗАНЯТА
                        await self._notify_all_csms_occupied()

                # Проверяем баланс во время зарядки
                elif self.active_session.status == "charging":
                    self.active_session = await self._get_active_session()

                    if self.active_session and not self.active_session.can_continue_charging:
                        logger.warning(
                            f"[BILLING STOP] session={self.active_session.id}"
                        )
                        await self._stop_charging()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MONITOR ERROR] {e}")

    async def _check_command_allowed(self, csms_name, action, msg):
        """Проверяет, разрешена ли команда от этого CSMS"""

        # 🔥 ЕСЛИ СТАНЦИЯ ЗАНЯТА НАШЕЙ ОПЛАТОЙ - БЛОКИРУЕМ ВСЕМ CSMS
        if await self._is_station_occupied():
            occupied_by = await self._get_occupied_by()

            # Если занято нашим платежом - блокируем всех
            if occupied_by and occupied_by.startswith("payment_"):
                logger.warning(
                    f"[COMMAND BLOCKED] {csms_name} {action} - "
                    f"station occupied by payment session"
                )
                return False

        return True

    async def _send_remote_start(self):
        if not self.active_session:
            return

        msg = [
            2,
            f"local_start_{int(datetime.now().timestamp())}",
            "RemoteStartTransaction",
            {"connectorId": 1, "idTag": f"payment_{self.active_session.id}"}
        ]
        logger.info(f"[SENDING REMOTE START] session={self.active_session.id} → STATION")
        await self.send(text_data=json.dumps(msg))

    async def _stop_charging(self):
        msg = [
            2,
            f"local_stop_{int(datetime.now().timestamp())}",
            "RemoteStopTransaction",
            {"transactionId": self.active_session.transaction_id},
        ]
        await self.send(json.dumps(msg))

    # ============================================================
    # CSMS NOTIFICATIONS
    # ============================================================

    async def _notify_all_csms_current_status(self):
        """Уведомляет все CSMS о текущем статусе станции"""
        try:
            # Получаем текущий статус коннектора 1
            current_status = self.connector_status.get(1, "Available") if hasattr(self,
                                                                                  'connector_status') else "Available"

            # Если есть активная сессия - статус Occupied
            if self.active_session and self.active_session.status in ["preparing", "charging"]:
                current_status = "Occupied"

            msg = [
                2,
                f"proxy_status_{int(datetime.now().timestamp())}",
                "StatusNotification",
                {
                    "connectorId": 1,
                    "errorCode": "NoError",
                    "status": current_status,
                    "timestamp": self._now(),
                    "info": "Proxy notification",
                },
            ]

            for csms_name, ws in self.remote_connections.items():
                try:
                    await ws.send(json.dumps(msg))
                    logger.info(f"[STATUS NOTIFY] {current_status} sent to {csms_name}")
                except Exception as e:
                    logger.error(f"[STATUS NOTIFY ERROR] {csms_name}: {e}")

        except Exception as e:
            logger.error(f"[NOTIFY STATUS ERROR] {e}")

    async def _notify_all_csms_occupied(self):
        """Уведомляет все CSMS что станция занята оплаченной сессией"""
        try:
            msg = [
                2,
                f"proxy_occupied_{int(datetime.now().timestamp())}",
                "StatusNotification",
                {
                    "connectorId": 1,
                    "errorCode": "NoError",
                    "status": "Occupied",
                    "timestamp": self._now(),
                    "info": "Station occupied by payment session",
                },
            ]

            for csms_name, ws in self.remote_connections.items():
                try:
                    await ws.send(json.dumps(msg))
                    logger.info(f"[OCCUPIED NOTIFY] sent to {csms_name}")
                except Exception as e:
                    logger.error(f"[OCCUPIED NOTIFY ERROR] {csms_name}: {e}")

        except Exception as e:
            logger.error(f"[NOTIFY OCCUPIED ERROR] {e}")

    async def _notify_all_csms_available(self):
        """Уведомляет все CSMS что станция свободна"""
        try:
            msg = [
                2,
                f"proxy_available_{int(datetime.now().timestamp())}",
                "StatusNotification",
                {
                    "connectorId": 1,
                    "errorCode": "NoError",
                    "status": "Available",
                    "timestamp": self._now(),
                    "info": "Station available",
                },
            ]

            for csms_name, ws in self.remote_connections.items():
                try:
                    await ws.send(json.dumps(msg))
                    logger.info(f"[AVAILABLE NOTIFY] sent to {csms_name}")
                except Exception as e:
                    logger.error(f"[AVAILABLE NOTIFY ERROR] {csms_name}: {e}")

        except Exception as e:
            logger.error(f"[NOTIFY AVAILABLE ERROR] {e}")

    # ============================================================
    # HELPERS
    # ============================================================

    @database_sync_to_async
    def _get_active_session(self):
        return ChargingSession.objects.filter(
            charge_point=self.charge_point,
            status__in=["preparing", "charging"],
        ).first()

    @database_sync_to_async
    def _is_station_occupied(self):
        self.charge_point.refresh_from_db()
        return self.charge_point.is_occupied

    @database_sync_to_async
    def _get_occupied_by(self):
        self.charge_point.refresh_from_db()
        return self.charge_point.occupied_by

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
