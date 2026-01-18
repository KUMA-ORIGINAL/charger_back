from django.db import models

from common.base_model import BaseModel


class ChargePointCSMS(BaseModel):
    """Связь между зарядной станцией и CSMS сервисами"""

    charge_point = models.ForeignKey(
        "ChargePoint",
        on_delete=models.CASCADE,
        related_name="csms_links",
        verbose_name="Зарядная станция",
    )
    csms_service = models.ForeignKey(
        "CSMSService",
        on_delete=models.CASCADE,
        related_name="charge_points",
        verbose_name="CSMS сервис",
    )

    remote_cp_id = models.CharField(
        max_length=100,
        verbose_name="ID станции в CSMS",
        help_text="Идентификатор станции во внешнем CSMS",
    )

    class Meta:
        verbose_name = "Связь станции с CSMS"
        verbose_name_plural = "Связи станций с CSMS"
        unique_together = ['charge_point', 'csms_service']
        ordering = ("charge_point",)

    def __str__(self) -> str:
        return f"{self.charge_point} → {self.csms_service}"
