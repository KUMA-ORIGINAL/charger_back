from django.contrib import admin

from account.models import ChargingSession
from common.base_admin import BaseModelAdmin


@admin.register(ChargingSession)
class ChargingSessionAdmin(BaseModelAdmin):
    list_display = [
        'id', 'charge_point', 'status', 'consumed_kwh',
        'total_cost', 'remaining_balance', 'created_at', 'detail_link'
    ]
    list_filter = ['status', 'charge_point']
    readonly_fields = ['total_cost', 'created_at', 'updated_at']

    def remaining_balance(self, obj):
        return f"{obj.remaining_balance:.2f} som"

    remaining_balance.short_description = 'Остаток'
