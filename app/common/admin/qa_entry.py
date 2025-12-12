from django.contrib import admin
from django.db import models
from modeltranslation.admin import TabbedTranslationAdmin
from unfold.contrib.forms.widgets import WysiwygWidget

from common.base_admin import BaseModelAdmin
from ..models import QAEntry


@admin.register(QAEntry)
class QAEntryAdmin(BaseModelAdmin, TabbedTranslationAdmin):
    formfield_overrides = {
        models.TextField: {
            "widget": WysiwygWidget,
        }
    }
    compressed_fields = True
    list_display = ('question', 'type', 'order')
    search_fields = ('question', 'answer')
    list_filter = ('type',)
    ordering = ('type', 'order')
    list_editable = ('order',)
