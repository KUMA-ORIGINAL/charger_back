from django.db import models
from django.core.validators import RegexValidator

from common.base_model import BaseModel


class CSMSService(BaseModel):
    """Конфигурация внешних CSMS сервисов"""

    class ServiceType(models.TextChoices):
        CHARGE24 = "charge24", "Charge24"
        OTHER = "other_csms", "Other CSMS"

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Название сервиса",
    )

    service_type = models.CharField(
        max_length=50,
        choices=ServiceType.choices,
        db_index=True,
        verbose_name="Тип сервиса",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Активен",
    )

    ws_url_template = models.CharField(
        max_length=255,
        verbose_name="WebSocket URL шаблон",
        help_text="Пример: wss://charge24.app/c/{cp_id}",
    )

    class Meta:
        verbose_name = "CSMS сервис"
        verbose_name_plural = "CSMS сервисы"
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_service_type_display()})"
