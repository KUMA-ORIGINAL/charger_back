from django.db import models

from common.base_model import BaseModel


class CSMSTransactionMapping(BaseModel):
    """
    Persistent mapping between external CSMS transactionId and station transactionId.
    Needed to resolve RemoteStop after proxy reconnect/restart.
    """

    charge_point = models.ForeignKey(
        "ChargePoint",
        on_delete=models.CASCADE,
        related_name="tx_mappings",
    )
    csms_name = models.CharField(max_length=100, db_index=True)
    csms_transaction_id = models.IntegerField(db_index=True)
    station_transaction_id = models.IntegerField(db_index=True)
    id_tag = models.CharField(max_length=100, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "CSMS transaction mapping"
        verbose_name_plural = "CSMS transaction mappings"
        indexes = [
            models.Index(fields=["charge_point", "csms_name", "csms_transaction_id"]),
            models.Index(fields=["charge_point", "station_transaction_id"]),
            models.Index(fields=["charge_point", "is_active"]),
        ]

    def __str__(self):
        return (
            f"{self.charge_point.cp_id} "
            f"{self.csms_name}:{self.csms_transaction_id} -> {self.station_transaction_id}"
        )
