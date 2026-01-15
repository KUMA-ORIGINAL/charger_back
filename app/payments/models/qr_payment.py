import uuid

from django.db import models
from common.base_model import BaseModel


class QRPayment(BaseModel):
    """QR‑транзакция в банке"""
    STATUS_CHOICES = [
        ("success", "Оплачено"),
        ("pending", "В ожидании"),
        ("failed", "Не удалось"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    bank_id = models.CharField("ID платежа у банка", max_length=128, unique=False)

    charge_point = models.ForeignKey(
        "account.ChargePoint",
        verbose_name="Станция",
        on_delete=models.CASCADE,
        related_name="qr_payments",
    )
    link = models.URLField("Ссылка на оплату", blank=True, null=True)
    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2)
    status = models.CharField(
        "Статус", max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    paid_at = models.DateTimeField("Дата оплаты", null=True, blank=True)

    webhook_payload = models.JSONField("Webhook-ответ", null=True, blank=True)

    class Meta:
        verbose_name = "QR-платеж"
        verbose_name_plural = "QR-платежи"
        ordering = ("-created_at",)

    def __str__(self):
        return f"#{self.id} — {self.get_status_display()} — {self.amount} сом"
