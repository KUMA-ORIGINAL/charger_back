from django.db import models
from django.utils.translation import gettext_lazy as _


class ChargePoint(models.Model):
    """
    OCPP Charge Point
    """
    cp_id = models.CharField(
        unique=True,
        max_length=64,
        verbose_name=_("Charge Point ID"),
        help_text=_("ID станции (cp_id в URL WebSocket)"),
    )

    charge24_cp_id = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        verbose_name=_("Charge24 CP ID"),
        help_text=_("ID станции в системе Charge24"),
    )

    name = models.CharField(
        max_length=128,
        verbose_name=_("Name"),
    )

    active_transaction_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Active transaction ID"),
        help_text=_("Последний активный OCPP transactionId"),
    )

    payment_qr_link = models.URLField("QR ссылка для оплаты", max_length=2000, blank=True, null=True)

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated at"),
    )

    class Meta:
        verbose_name = _("Charge Point")
        verbose_name_plural = _("Charge Points")

    def __str__(self):
        return f"{self.cp_id}"
