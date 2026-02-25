"""
Data migration: transfer charge24_cp_id from ChargePoint
into ChargePointCSMS records linked to the Charge24 CSMSService.
"""

from django.db import migrations


def forward(apps, schema_editor):
    ChargePoint = apps.get_model("account", "ChargePoint")
    CSMSService = apps.get_model("account", "CSMSService")
    ChargePointCSMS = apps.get_model("account", "ChargePointCSMS")

    # ensure the Charge24 service exists
    svc, _ = CSMSService.objects.get_or_create(
        name="Charge24",
        defaults={
            "service_type": "charge24",
            "is_active": True,
            "ws_url_template": "wss://charge24.app/c/{cp_id}",
        },
    )

    for cp in ChargePoint.objects.exclude(charge24_cp_id__isnull=True).exclude(
        charge24_cp_id=""
    ):
        ChargePointCSMS.objects.get_or_create(
            charge_point=cp,
            csms_service=svc,
            defaults={"remote_cp_id": cp.charge24_cp_id},
        )


def backward(apps, schema_editor):
    # nothing to undo — the old field still exists
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0012_chargepoint_occupied_by_and_more"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
