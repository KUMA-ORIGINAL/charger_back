import json
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import websockets
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from account.models import ChargePoint, ChargePointCSMS, ChargingSession

logger = logging.getLogger("ocpp")


class OCPPConsumer(AsyncWebsocketConsumer):
    """
    OCPP 1.6 JSON — Multi-CSMS Proxy

    Proxy acts as CSMS for the station and as a "virtual station"
    for each external CSMS (Charge24, etc.).

    Message flows
    -------------
    Station Call   → proxy responds + selectively forwards to CSMS
    CSMS   Call   → access-control check + forward to station
    Station Result → route back to the originating CSMS
    CSMS   Result → store txId mapping (StartTransaction), log, discard
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # --- CSMS connections ---
        self.remote_connections: dict = {}   # csms_name → websocket
        self.remote_tasks: list = []

        # --- message routing ---
        self.pending_calls: dict = {}        # msg_id → csms_name  (CSMS→station)
        self.forwarded_calls: dict = {}      # msg_id → {"action"}  (station→CSMS)

        # --- transaction tracking ---
        self.proxy_tx_id: int | None = None          # txId assigned to station
        self.csms_tx_ids: dict = {}                   # csms_name → csms txId
        self.initiating_csms: str | None = None       # who started current tx

        # --- occupancy ---
        self.occupied_by: str | None = None           # None | "self" | csms_name

        # --- payment session ---
        self.active_session = None                    # ChargingSession
        self.monitoring_task = None

        # --- state ---
        self.connector_status: dict = {}              # connector_id → status

    # ================================================================
    #  CONNECTION
    # ================================================================

    async def connect(self):
        self.cp_id: str = self.scope["url_route"]["kwargs"]["cp_id"]

        # --- load ChargePoint ---
        try:
            self.charge_point = await database_sync_to_async(
                ChargePoint.objects.get
            )(cp_id=self.cp_id)
        except ChargePoint.DoesNotExist:
            logger.error(f"[REJECT] Unknown CP={self.cp_id}")
            await self.close(code=4001)
            return

        # --- connect to every active CSMS ---
        csms_configs = await self._get_csms_configs()
        if not csms_configs:
            logger.warning(f"[WARN] CP={self.cp_id} no CSMS configured")

        for cfg in csms_configs:
            await self._connect_to_csms(cfg)

        # --- restore state ---
        self.active_session = await self._get_active_session()
        if self.active_session:
            self.occupied_by = "self"
            logger.info(
                f"[RESUME] CP={self.cp_id} active_session={self.active_session.id}"
            )
        else:
            cp_data = await self._get_charge_point_data()
            if cp_data["is_occupied"]:
                self.occupied_by = cp_data["occupied_by"] or "external"

        # --- background tasks ---
        self.monitoring_task = asyncio.create_task(self._monitor_session())

        # --- channel layer (for admin/API commands) ---
        await self.channel_layer.group_add(self.cp_id, self.channel_name)

        await self.accept(subprotocol="ocpp1.6")

        csms_list = ", ".join(self.remote_connections) or "none"
        logger.info(f"[CONNECTED] CP={self.cp_id} CSMS=[{csms_list}]")

    async def disconnect(self, close_code):
        if self.monitoring_task:
            self.monitoring_task.cancel()

        for task in self.remote_tasks:
            task.cancel()

        for name, ws in self.remote_connections.items():
            try:
                await ws.close()
            except Exception:
                pass

        if hasattr(self, "cp_id"):
            await self.channel_layer.group_discard(self.cp_id, self.channel_name)

        logger.info(
            f"[DISCONNECT] CP={getattr(self, 'cp_id', '?')} code={close_code}"
        )

    # ================================================================
    #  CSMS CONNECTION HELPERS
    # ================================================================

    @database_sync_to_async
    def _get_csms_configs(self) -> list[dict]:
        links = (
            ChargePointCSMS.objects
            .filter(
                charge_point=self.charge_point,
                csms_service__is_active=True,
            )
            .select_related("csms_service")
        )
        return [
            {
                "name": link.csms_service.name,
                "url": link.csms_service.ws_url_template.format(
                    cp_id=link.remote_cp_id
                ),
            }
            for link in links
        ]

    async def _connect_to_csms(self, cfg: dict):
        name, url = cfg["name"], cfg["url"]
        try:
            ws = await websockets.connect(
                url,
                subprotocols=["ocpp1.6"],
                ping_interval=30,
                ping_timeout=10,
            )
            self.remote_connections[name] = ws
            task = asyncio.create_task(self._listen_csms(name, ws))
            self.remote_tasks.append(task)
            logger.info(f"[CSMS OK] {name} url={url}")
        except Exception as exc:
            logger.error(f"[CSMS FAIL] {name} url={url}: {exc}")

    # ================================================================
    #  RECEIVE FROM STATION
    # ================================================================

    async def receive(self, text_data=None, bytes_data=None):
        logger.info(f"[ST→PX] CP={self.cp_id} {text_data}")

        try:
            frame = json.loads(text_data)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error(f"[PARSE] CP={self.cp_id} {exc}")
            return

        if not isinstance(frame, list) or len(frame) < 3:
            logger.warning(f"[BAD FRAME] CP={self.cp_id}")
            return

        msg_type = frame[0]
        if msg_type == 2:
            await self._handle_station_call(frame)
        elif msg_type == 3:
            await self._handle_station_call_result(frame)
        elif msg_type == 4:
            await self._handle_station_call_error(frame)

    # ================================================================
    #  STATION CALL  (station → proxy)
    # ================================================================

    async def _handle_station_call(self, frame: list):
        """[2, messageId, action, payload]"""
        _, message_id, action, payload = frame

        logger.info(f"[CALL] CP={self.cp_id} {action}")

        # 1) respond to station immediately
        resp = self._make_response(action, payload)
        await self.send(text_data=json.dumps([3, message_id, resp]))

        # 2) internal processing (DB, billing, occupancy)
        await self._process_station_call(action, payload)

        # 3) selective forwarding to CSMS
        await self._forward_station_call(frame, action, payload)

    # ---- response generator ----

    def _make_response(self, action: str, payload: dict) -> dict:
        if action == "BootNotification":
            return {
                "currentTime": self._now(),
                "interval": 30,
                "status": "Accepted",
            }
        if action == "Heartbeat":
            return {"currentTime": self._now()}
        if action == "Authorize":
            return {"idTagInfo": {"status": "Accepted"}}
        if action == "StatusNotification":
            return {}
        if action == "StartTransaction":
            self.proxy_tx_id = int(uuid.uuid4().int % 1_000_000)
            return {
                "transactionId": self.proxy_tx_id,
                "idTagInfo": {"status": "Accepted"},
            }
        if action == "StopTransaction":
            return {}
        if action == "MeterValues":
            return {}
        logger.warning(f"[UNKNOWN] {action}")
        return {}

    # ---- internal processing ----

    async def _process_station_call(self, action: str, payload: dict):
        if action == "StatusNotification":
            cid = payload.get("connectorId", 0)
            status = payload.get("status", "")
            self.connector_status[cid] = status
            logger.info(f"[STATUS] CP={self.cp_id} c={cid} s={status}")

            # auto-start on Preparing when we have a paid session
            if status == "Preparing" and cid == 1:
                if not self.active_session:
                    self.active_session = await self._get_active_session()
                if (
                    self.active_session
                    and self.active_session.status == "preparing"
                ):
                    logger.info(f"[AUTO START] session={self.active_session.id}")
                    await self._send_remote_start()

        elif action == "StartTransaction":
            await self._on_start_transaction(payload)

        elif action == "StopTransaction":
            await self._on_stop_transaction(payload)

        elif action == "MeterValues":
            await self._on_meter_values(payload)

    # ---- selective forwarding ----

    async def _forward_station_call(
        self, frame: list, action: str, payload: dict
    ):
        message_id = frame[1]
        raw = json.dumps(frame)

        # don't leak our payment Authorize to CSMS
        if action == "Authorize":
            if payload.get("idTag", "").startswith("payment_"):
                return

        # transaction-specific messages → only to initiating CSMS
        if action in ("StartTransaction", "StopTransaction", "MeterValues"):
            if self.occupied_by == "self":
                return  # our session — CSMS should not see details

            if (
                self.initiating_csms
                and self.initiating_csms in self.remote_connections
            ):
                csms_frame = self._rewrite_tx_for_csms(
                    self.initiating_csms, frame, action
                )
                # track so we can grab csms txId from the response
                if action == "StartTransaction":
                    self.forwarded_calls[message_id] = {"action": action}
                await self._send_to_csms(
                    self.initiating_csms, json.dumps(csms_frame)
                )
                return

        # everything else → broadcast to all CSMS
        for csms_name in list(self.remote_connections):
            await self._send_to_csms(csms_name, raw)

    # ================================================================
    #  STATION CALLRESULT / CALLERROR  (station → CSMS)
    # ================================================================

    async def _handle_station_call_result(self, frame: list):
        """[3, messageId, payload]"""
        _, message_id, payload = frame

        # response to our own proxy command (RemoteStart / RemoteStop)
        if isinstance(message_id, str) and message_id.startswith("proxy_"):
            status = payload.get("status", "")
            logger.info(f"[PX CMD] msg={message_id} status={status}")
            if message_id.startswith("proxy_start_") and status == "Rejected":
                logger.warning(f"[START REJECTED] CP={self.cp_id}")
                self.occupied_by = None
                await self._clear_occupancy()
            return

        # route to originating CSMS
        csms_name = self.pending_calls.pop(message_id, None)
        if not csms_name:
            logger.debug(f"[RESULT] msg={message_id} — no pending CSMS")
            return

        logger.info(f"[ST→{csms_name}] result msg={message_id}")
        await self._send_to_csms(csms_name, json.dumps(frame))

    async def _handle_station_call_error(self, frame: list):
        """[4, messageId, errorCode, errorDesc, details]"""
        _, message_id = frame[0], frame[1]

        if isinstance(message_id, str) and message_id.startswith("proxy_"):
            logger.error(f"[PX CMD ERR] msg={message_id} frame={frame}")
            return

        csms_name = self.pending_calls.pop(message_id, None)
        if csms_name:
            logger.error(f"[ST→{csms_name}] error msg={message_id}")
            await self._send_to_csms(csms_name, json.dumps(frame))

    # ================================================================
    #  LISTEN TO CSMS
    # ================================================================

    async def _listen_csms(self, csms_name: str, ws):
        try:
            async for raw in ws:
                logger.info(f"[{csms_name}→PX] {raw}")
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(frame, list) or len(frame) < 3:
                    continue

                msg_type = frame[0]
                if msg_type == 2:
                    await self._handle_csms_call(csms_name, frame)
                elif msg_type == 3:
                    await self._handle_csms_call_result(csms_name, frame)
                elif msg_type == 4:
                    await self._handle_csms_call_error(csms_name, frame)

        except asyncio.CancelledError:
            pass
        except websockets.exceptions.ConnectionClosed as exc:
            logger.warning(f"[CSMS CLOSED] {csms_name}: {exc}")
        except Exception as exc:
            logger.error(f"[CSMS ERR] {csms_name}: {exc}")

    # ================================================================
    #  CSMS CALL  (csms → proxy → station)
    # ================================================================

    async def _handle_csms_call(self, csms_name: str, frame: list):
        """[2, messageId, action, payload]"""
        _, message_id, action, payload = frame
        logger.info(f"[CSMS CALL] {csms_name} {action}")

        # --- access control for start / stop ---
        if action in ("RemoteStartTransaction", "RemoteStopTransaction"):
            if not self._is_command_allowed(csms_name, action):
                err = [4, message_id, "GenericError", "Station occupied", {}]
                await self._send_to_csms(csms_name, json.dumps(err))
                logger.warning(
                    f"[BLOCKED] {csms_name} {action} "
                    f"(occupied_by={self.occupied_by})"
                )
                return

        # --- txId rewrite (CSMS → station) ---
        if action == "RemoteStopTransaction" and csms_name in self.csms_tx_ids:
            payload = self._rewrite_tx_from_csms(csms_name, dict(payload))
            frame = [2, message_id, action, payload]

        # --- record initiating CSMS ---
        if action == "RemoteStartTransaction":
            self.initiating_csms = csms_name

        # --- track for response routing ---
        self.pending_calls[message_id] = csms_name

        # --- forward to station ---
        logger.info(f"[→ST] {csms_name} {action}")
        await self.send(text_data=json.dumps(frame))

    def _is_command_allowed(self, csms_name: str, action: str) -> bool:
        if action == "RemoteStartTransaction":
            return self.occupied_by is None

        if action == "RemoteStopTransaction":
            # allow the CSMS that started, or if already free
            return self.occupied_by in (csms_name, None)

        return True

    # ================================================================
    #  CSMS CALLRESULT / CALLERROR
    # ================================================================

    async def _handle_csms_call_result(self, csms_name: str, frame: list):
        """Response to a forwarded station Call — grab txId if needed."""
        _, message_id, payload = frame

        info = self.forwarded_calls.pop(message_id, None)
        if info and info.get("action") == "StartTransaction":
            csms_tx = payload.get("transactionId")
            if csms_tx is not None:
                self.csms_tx_ids[csms_name] = csms_tx
                logger.info(
                    f"[TX MAP] {csms_name} csms_tx={csms_tx} "
                    f"proxy_tx={self.proxy_tx_id}"
                )

        logger.debug(f"[CSMS RESULT] {csms_name} msg={message_id} (drop)")

    async def _handle_csms_call_error(self, csms_name: str, frame: list):
        message_id = frame[1]
        self.forwarded_calls.pop(message_id, None)
        logger.warning(f"[CSMS ERR] {csms_name} msg={message_id} {frame}")

    # ================================================================
    #  TRANSACTION-ID MAPPING
    # ================================================================

    def _rewrite_tx_for_csms(
        self, csms_name: str, frame: list, action: str
    ) -> list:
        """proxy_tx → csms_tx when forwarding TO a CSMS."""
        csms_tx = self.csms_tx_ids.get(csms_name)
        if csms_tx is None or self.proxy_tx_id is None:
            return frame

        frame = json.loads(json.dumps(frame))        # deep copy
        payload = frame[3] if len(frame) > 3 else {}

        if action in ("StopTransaction", "MeterValues"):
            if "transactionId" in payload:
                payload["transactionId"] = csms_tx
                frame[3] = payload

        return frame

    def _rewrite_tx_from_csms(self, csms_name: str, payload: dict) -> dict:
        """csms_tx → proxy_tx when forwarding FROM a CSMS to station."""
        csms_tx = self.csms_tx_ids.get(csms_name)
        if (
            csms_tx is not None
            and self.proxy_tx_id is not None
            and payload.get("transactionId") == csms_tx
        ):
            payload = dict(payload)
            payload["transactionId"] = self.proxy_tx_id
        return payload

    # ================================================================
    #  TRANSACTION LIFECYCLE
    # ================================================================

    async def _on_start_transaction(self, payload: dict):
        id_tag = payload.get("idTag", "")
        connector_id = payload.get("connectorId", 1)
        meter_start = Decimal(str(payload.get("meterStart", 0)))

        logger.info(
            f"[START TX] CP={self.cp_id} c={connector_id} "
            f"tag={id_tag} tx={self.proxy_tx_id}"
        )

        if id_tag.startswith("payment_"):
            self.occupied_by = "self"
            await self._update_occupancy("self")
            if self.active_session:
                await self._update_session_started(meter_start)
        else:
            csms = self.initiating_csms or "external"
            self.occupied_by = csms
            await self._update_occupancy(csms)

        await self._save_active_transaction(self.proxy_tx_id)

    async def _on_stop_transaction(self, payload: dict):
        tx_id = payload.get("transactionId")
        meter_stop = payload.get("meterStop")
        reason = payload.get("reason", "")

        logger.info(
            f"[STOP TX] CP={self.cp_id} tx={tx_id} reason={reason}"
        )

        if self.active_session and self.occupied_by == "self":
            await self._update_session_stopped(meter_stop)
            self.active_session = None

        self.occupied_by = None
        self.initiating_csms = None
        self.proxy_tx_id = None
        self.csms_tx_ids.clear()
        await self._clear_occupancy()

    async def _on_meter_values(self, payload: dict):
        if not self.active_session or self.occupied_by != "self":
            return

        for mv in payload.get("meterValue", []):
            for sv in mv.get("sampledValue", []):
                measurand = sv.get(
                    "measurand", "Energy.Active.Import.Register"
                )
                if measurand == "Energy.Active.Import.Register":
                    val = sv.get("value")
                    if val is not None:
                        await self._update_session_consumption(
                            Decimal(str(val))
                        )

    # ================================================================
    #  MONITOR LOOP  (payment sessions / billing)
    # ================================================================

    async def _monitor_session(self):
        while True:
            try:
                await asyncio.sleep(2)

                # ---- detect new paid session ----
                if self.active_session is None and self.occupied_by is None:
                    sess = await self._get_active_session()
                    if sess and sess.status == "preparing":
                        self.active_session = sess
                        self.occupied_by = "self"
                        await self._update_occupancy("self")
                        logger.info(
                            f"[NEW SESSION] CP={self.cp_id} "
                            f"session={sess.id}"
                        )
                        cst = self.connector_status.get(1)
                        if cst in ("Available", "Preparing", None):
                            await self._send_remote_start()

                # ---- check balance while charging ----
                elif (
                    self.active_session
                    and self.occupied_by == "self"
                    and self.active_session.status == "charging"
                ):
                    refreshed = await self._refresh_session()
                    if refreshed:
                        self.active_session = refreshed
                        if not self.active_session.can_continue_charging:
                            logger.warning(
                                f"[BALANCE OUT] session={self.active_session.id} "
                                f"left={self.active_session.remaining_balance:.2f}"
                            )
                            await self._send_remote_stop()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"[MONITOR] CP={self.cp_id} {exc}")

    # ================================================================
    #  PROXY → STATION COMMANDS
    # ================================================================

    async def _send_remote_start(self):
        if not self.active_session:
            return
        tag = f"payment_{self.active_session.id}"
        msg_id = f"proxy_start_{int(datetime.now(timezone.utc).timestamp())}"
        frame = [
            2, msg_id, "RemoteStartTransaction",
            {"connectorId": 1, "idTag": tag},
        ]
        logger.info(f"[REMOTE START] CP={self.cp_id} session={self.active_session.id}")
        await self.send(text_data=json.dumps(frame))

    async def _send_remote_stop(self):
        if not self.proxy_tx_id:
            return
        msg_id = f"proxy_stop_{int(datetime.now(timezone.utc).timestamp())}"
        frame = [
            2, msg_id, "RemoteStopTransaction",
            {"transactionId": self.proxy_tx_id},
        ]
        logger.info(f"[REMOTE STOP] CP={self.cp_id} tx={self.proxy_tx_id}")
        await self.send(text_data=json.dumps(frame))

    # channel-layer handler (admin / API)
    async def send_ocpp(self, event):
        frame = [
            2,
            event["message_id"],
            event["action"],
            event.get("payload", {}),
        ]
        logger.info(f"[CH CMD] CP={self.cp_id} {event['action']}")
        await self.send(text_data=json.dumps(frame))

    # ================================================================
    #  FORWARDING HELPER
    # ================================================================

    async def _send_to_csms(self, csms_name: str, data: str):
        ws = self.remote_connections.get(csms_name)
        if not ws:
            return
        try:
            await ws.send(data)
        except Exception as exc:
            logger.error(f"[SEND ERR] →{csms_name}: {exc}")
            self.remote_connections.pop(csms_name, None)

    # ================================================================
    #  DATABASE HELPERS
    # ================================================================

    @database_sync_to_async
    def _get_active_session(self):
        return ChargingSession.objects.filter(
            charge_point=self.charge_point,
            status__in=["preparing", "charging"],
        ).first()

    @database_sync_to_async
    def _refresh_session(self):
        if not self.active_session:
            return None
        try:
            return ChargingSession.objects.get(id=self.active_session.id)
        except ChargingSession.DoesNotExist:
            return None

    @database_sync_to_async
    def _update_session_started(self, meter_start: Decimal):
        if not self.active_session:
            return
        s = ChargingSession.objects.get(id=self.active_session.id)
        s.transaction_id = self.proxy_tx_id
        s.id_tag = f"payment_{s.id}"
        s.status = "charging"
        s.started_at = datetime.now(timezone.utc)
        s.start_meter_value = meter_start
        s.last_meter_value = meter_start
        s.save()
        self.active_session = s

    @database_sync_to_async
    def _update_session_stopped(self, meter_stop):
        if not self.active_session:
            return
        s = ChargingSession.objects.get(id=self.active_session.id)
        if meter_stop is not None:
            s.update_consumption(meter_stop)
        s.status = "completed"
        s.stopped_at = datetime.now(timezone.utc)
        s.save()

    @database_sync_to_async
    def _update_session_consumption(self, meter_wh: Decimal):
        if not self.active_session:
            return
        try:
            s = ChargingSession.objects.get(id=self.active_session.id)
            s.update_consumption(meter_wh)
            s.save()
            self.active_session = s
            logger.info(
                f"[BILL] s={s.id} kWh={s.consumed_kwh:.3f} "
                f"cost={s.total_cost:.2f} left={s.remaining_balance:.2f}"
            )
        except ChargingSession.DoesNotExist:
            self.active_session = None

    @database_sync_to_async
    def _update_occupancy(self, occupied_by: str):
        ChargePoint.objects.filter(cp_id=self.cp_id).update(
            is_occupied=True,
            occupied_by=occupied_by,
        )

    @database_sync_to_async
    def _clear_occupancy(self):
        ChargePoint.objects.filter(cp_id=self.cp_id).update(
            is_occupied=False,
            occupied_by=None,
            active_transaction_id=None,
        )

    @database_sync_to_async
    def _save_active_transaction(self, transaction_id: int):
        ChargePoint.objects.filter(cp_id=self.cp_id).update(
            active_transaction_id=transaction_id,
        )

    @database_sync_to_async
    def _get_charge_point_data(self) -> dict:
        cp = ChargePoint.objects.get(cp_id=self.cp_id)
        return {"is_occupied": cp.is_occupied, "occupied_by": cp.occupied_by}

    # ================================================================
    #  UTILS
    # ================================================================

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
