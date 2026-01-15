from django.contrib import admin

from common.base_admin import BaseModelAdmin
from ..models import QRPayment


@admin.register(QRPayment)
class QRPaymentAdmin(BaseModelAdmin):
    list_display = (
        "id", "charge_point", "amount", "status", "created_at", 'paid_at', 'detail_link'
    )
    list_filter = ("status", "charge_point")
    ordering = ("-created_at",)
