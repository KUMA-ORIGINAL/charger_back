import uuid
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def ocpp_call(cp_id: str, action: str, payload: dict):
    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        cp_id,
        {
            "type": "send_ocpp",
            "action": action,
            "message_id": str(uuid.uuid4()),
            "payload": payload,
        },
    )


def start_charging(cp_id, connector_id=1):
    ocpp_call(
        cp_id,
        "StartTransaction",
        {
            "connectorId": connector_id,
            "idTag": "ADMIN",
            "meterStart": 0,
            "timestamp": "2025-01-01T00:00:00Z",
        },
    )


def stop_charging(cp_id, transaction_id):
    ocpp_call(
        cp_id,
        "StopTransaction",
        {
            "transactionId": transaction_id,
            "timestamp": "2025-01-01T00:00:00Z",
        },
    )
