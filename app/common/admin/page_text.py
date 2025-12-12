from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin

from common.base_admin import BaseModelAdmin
from common.models import PageText


@admin.register(PageText)
class PageTextAdmin(BaseModelAdmin, TabbedTranslationAdmin):
    list_display = ('key', 'text_ru', 'text_ky')
    search_fields = ('key', 'text')
    list_filter = ('key',)
