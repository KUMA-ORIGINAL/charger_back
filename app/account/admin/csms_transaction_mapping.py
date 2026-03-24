from django.contrib import admin

from account.models import CSMSTransactionMapping
from common.base_admin import BaseModelAdmin


@admin.register(CSMSTransactionMapping)
class CSMSTransactionMappingAdmin(BaseModelAdmin):
    list_display = [
        "id",
        "charge_point",
        "csms_name",
        "csms_transaction_id",
        "station_transaction_id",
        "id_tag",
        "is_active",
        "created_at",
        "detail_link",
    ]
    list_filter = ["csms_name", "is_active", "charge_point"]
    search_fields = [
        "charge_point__cp_id",
        "charge_point__name",
        "id_tag",
        "csms_name",
        "csms_transaction_id",
        "station_transaction_id",
    ]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["charge_point"]
    date_hierarchy = "created_at"
