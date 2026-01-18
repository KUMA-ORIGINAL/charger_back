from django.contrib import admin

from account.models import CSMSService
from common.base_admin import BaseModelAdmin


@admin.register(CSMSService)
class CSMSServiceAdmin(BaseModelAdmin):
    list_display = ['name', 'service_type', 'is_active', 'detail_link']
    list_filter = ['service_type', 'is_active']
