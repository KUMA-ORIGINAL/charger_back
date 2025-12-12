import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger("ocpp")

class OCPPConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.cp_id = self.scope['url_route']['kwargs']['cp_id']
        logger.info(f"[CONNECT] ChargePoint {self.cp_id} подключился")
        await self.accept()

    async def disconnect(self, close_code):
        logger.info(f"[DISCONNECT] ChargePoint {self.cp_id} отключился")

    async def receive(self, text_data=None, bytes_data=None):
        logger.info(f"[RECEIVED] CP={self.cp_id} RAW={text_data}")

        try:
            frame = json.loads(text_data)
        except Exception as e:
            logger.error(f"[ERROR] CP={self.cp_id} JSON decode failed: {e}")
            return

        if isinstance(frame, list) and len(frame) >= 3 and frame[0] == 2:
            message_id = frame[1]
            response = [3, message_id, {}]

            logger.info(f"[SEND] CP={self.cp_id} CALLRESULT={response}")
            await self.send(text_data=json.dumps(response))
