import json
import uuid
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger("ocpp")


class OCPPConsumer(AsyncWebsocketConsumer):
    """
    OCPP 1.6 JSON
    """

    async def connect(self):
        self.cp_id = self.scope["url_route"]["kwargs"]["cp_id"]

        # group = конкретная станция
        await self.channel_layer.group_add(
            self.cp_id,
            self.channel_name
        )

        logger.info(f"[CONNECT] CP={self.cp_id}")
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.cp_id,
            self.channel_name
        )
        logger.info(f"[DISCONNECT] CP={self.cp_id}")

    # ======== ПРИЁМ ОТ СТАНЦИИ ========
    async def receive(self, text_data=None, bytes_data=None):
        logger.info(f"[RECV] CP={self.cp_id} RAW={text_data}")

        try:
            frame = json.loads(text_data)
        except Exception as e:
            logger.error(f"[ERROR] CP={self.cp_id} JSON error: {e}")
            return

        if not isinstance(frame, list) or len(frame) < 3:
            logger.warning(f"[WARN] CP={self.cp_id} Invalid frame")
            return

        message_type = frame[0]

        # CALL (запрос от станции)
        if message_type == 2:
            await self.handle_call(frame)

        # CALLRESULT (ответ на нашу команду)
        elif message_type == 3:
            await self.handle_call_result(frame)

        # CALLERROR
        elif message_type == 4:
            await self.handle_call_error(frame)

    # ======== CALL ========
    async def handle_call(self, frame):
        _, message_id, action, payload = frame

        logger.info(
            f"[CALL] CP={self.cp_id} ACTION={action} PAYLOAD={payload}"
        )

        # Заглушки ответов
        handlers = {
            "BootNotification": self.on_boot_notification,
            "Heartbeat": self.on_heartbeat,
            "StartTransaction": self.on_start_transaction,
            "StopTransaction": self.on_stop_transaction,
        }

        handler = handlers.get(action)
        if handler:
            response_payload = await handler(payload)
        else:
            response_payload = {}

        response = [3, message_id, response_payload]

        logger.info(f"[SEND] CP={self.cp_id} CALLRESULT={response}")
        await self.send(text_data=json.dumps(response))

    # ======== CALLRESULT ========
    async def handle_call_result(self, frame):
        _, message_id, payload = frame
        logger.info(
            f"[CALLRESULT] CP={self.cp_id} MSG_ID={message_id} PAYLOAD={payload}"
        )

    # ======== CALLERROR ========
    async def handle_call_error(self, frame):
        _, message_id, error_code, error_desc, details = frame
        logger.error(
            f"[CALLERROR] CP={self.cp_id} MSG_ID={message_id} "
            f"CODE={error_code} DESC={error_desc}"
        )

    # ======== HANDLERS ========
    async def on_boot_notification(self, payload):
        return {
            "currentTime": "2025-01-01T00:00:00Z",
            "interval": 30,
            "status": "Accepted",
        }

    async def on_heartbeat(self, payload):
        return {
            "currentTime": "2025-01-01T00:00:00Z",
        }

    async def on_start_transaction(self, payload):
        return {
            "transactionId": 1001,
            "idTagInfo": {"status": "Accepted"},
        }

    async def on_stop_transaction(self, payload):
        return {}

    # ======== ОТПРАВКА КОМАНД ========
    async def send_ocpp(self, event):
        frame = [
            2,
            event["message_id"],
            event["action"],
            event.get("payload", {}),
        ]

        logger.info(f"[SEND] CP={self.cp_id} CALL={frame}")
        await self.send(text_data=json.dumps(frame))
