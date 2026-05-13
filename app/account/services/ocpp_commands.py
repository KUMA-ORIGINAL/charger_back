"""
Send OCPP commands to a charge point via the channel layer.

The OCPPConsumer handles these through its ``send_ocpp`` method,
which forwards the OCPP Call frame directly to the station.

Use this module for manual / admin-initiated commands.
Payment-initiated start/stop is handled by the consumer's
internal monitor loop and does NOT go through the channel layer.
"""

import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def ocpp_call(cp_id: str, action: str, payload: dict):
    """Send an OCPP Call to the station through the consumer."""
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        cp_id,
        {
            "type": "send_ocpp",
            "action": action,
            "message_id": str(uuid.uuid4()),
            "payload": payload,
        },
    )


def start_charging(cp_id: str, connector_id: int = 1, id_tag: str = "ADMIN"):
    """Send RemoteStartTransaction (admin / manual trigger)."""
    ocpp_call(
        cp_id,
        "RemoteStartTransaction",
        {
            "connectorId": connector_id,
            "idTag": id_tag,
        },
    )


def stop_charging(cp_id: str, transaction_id: int):
    """Send RemoteStopTransaction (admin / manual trigger)."""
    ocpp_call(
        cp_id,
        "RemoteStopTransaction",
        {
            "transactionId": transaction_id,
        },
    )


def trigger_status(cp_id: str, connector_id: int = 0):
    ocpp_call(cp_id, "TriggerMessage", {
        "requestedMessage": "StatusNotification",
        "connectorId": connector_id,
    })


def change_availability(cp_id: str, connector_id: int, availability_type: str):
    ocpp_call(cp_id, "ChangeAvailability", {
        "connectorId": connector_id,
        "type": availability_type,
    })


def reset_station(cp_id: str, reset_type: str = "Soft"):
    ocpp_call(cp_id, "Reset", {"type": reset_type})


def clear_charging_profile(cp_id: str):
    ocpp_call(cp_id, "ClearChargingProfile", {})


def get_configuration(cp_id: str):
    ocpp_call(cp_id, "GetConfiguration", {})


def trigger_boot_notification(cp_id: str):
    ocpp_call(cp_id, "TriggerMessage", {"requestedMessage": "BootNotification"})


def trigger_meter_values(cp_id: str, connector_id: int = 1):
    ocpp_call(cp_id, "TriggerMessage", {
        "requestedMessage": "MeterValues",
        "connectorId": connector_id,
    })
