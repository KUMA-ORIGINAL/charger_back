"""``/meta/`` — описание доступных пользователю ресурсов.

Сериализаторы ниже ничего не проверяют: они описывают форму ответа для
OpenAPI, из которого фронт генерирует типы (``pnpm api:generate``). Меняете
:meth:`staff.resources.StaffResource.describe` — меняйте и их.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .api import StaffAPIMixin
from .fields import FIELD_TYPES
from .site import staff_site

# Наборы значений вынесены, чтобы в OpenAPI у enum'ов были стабильные имена
# (см. ENUM_NAME_OVERRIDES в staff_openapi).
FIELD_TYPE_CHOICES = FIELD_TYPES + ("badge", "table", "link", "series")
FILTER_TYPE_CHOICES = ("choice", "boolean", "relation", "date_range", "number_range", "exact")
ACTION_VARIANT_CHOICES = ("default", "destructive")


class ChoiceSerializer(serializers.Serializer):
    value = serializers.JSONField()
    label = serializers.CharField()


class FieldMetaSerializer(serializers.Serializer):
    name = serializers.CharField()
    label = serializers.CharField()
    type = serializers.ChoiceField(choices=FIELD_TYPE_CHOICES)
    help_text = serializers.CharField(allow_blank=True)
    required = serializers.BooleanField()
    read_only = serializers.BooleanField()
    computed = serializers.BooleanField()
    choices = ChoiceSerializer(many=True, required=False)
    related_resource = serializers.CharField(allow_null=True, required=False)
    decimal_places = serializers.IntegerField(required=False)
    max_length = serializers.IntegerField(required=False)
    badges = serializers.DictField(child=serializers.CharField(), allow_null=True)
    format = serializers.ChoiceField(choices=("money",), allow_null=True)
    write_only = serializers.BooleanField(required=False, help_text="Поле только для записи (пароль)")
    default = serializers.JSONField(required=False, help_text="Значение по умолчанию для формы создания")


class ColumnMetaSerializer(FieldMetaSerializer):
    sortable = serializers.BooleanField()


class FilterMetaSerializer(serializers.Serializer):
    name = serializers.CharField()
    label = serializers.CharField()
    type = serializers.ChoiceField(choices=FILTER_TYPE_CHOICES)
    choices = ChoiceSerializer(many=True, required=False)
    related_resource = serializers.CharField(allow_null=True, required=False)


class FieldsetMetaSerializer(serializers.Serializer):
    title = serializers.CharField(allow_null=True)
    fields = serializers.ListField(child=serializers.CharField())


class InlineColumnSerializer(serializers.Serializer):
    name = serializers.CharField()
    label = serializers.CharField()
    type = serializers.CharField()
    choices = ChoiceSerializer(many=True, allow_null=True)
    format = serializers.ChoiceField(choices=("money",), allow_null=True)


class InlineMetaSerializer(serializers.Serializer):
    name = serializers.CharField()
    label = serializers.CharField()
    columns = InlineColumnSerializer(many=True)
    resource = serializers.CharField(allow_null=True, help_text="Ресурс строк: если доступен — строки редактируемые")
    fk = serializers.CharField(allow_null=True, help_text="Поле связи строки с родителем")


class ActionFieldSerializer(serializers.Serializer):
    name = serializers.CharField()
    label = serializers.CharField()
    type = serializers.ChoiceField(choices=FIELD_TYPE_CHOICES)
    required = serializers.BooleanField(required=False)
    help_text = serializers.CharField(required=False, allow_blank=True)
    choices = ChoiceSerializer(many=True, required=False)


class ActionMetaSerializer(serializers.Serializer):
    name = serializers.CharField()
    label = serializers.CharField()
    detail = serializers.BooleanField()
    confirm = serializers.CharField(allow_null=True)
    variant = serializers.ChoiceField(choices=ACTION_VARIANT_CHOICES)
    permission = serializers.CharField()
    icon = serializers.CharField(allow_null=True)
    form = ActionFieldSerializer(many=True, allow_null=True)


class PermissionsSerializer(serializers.Serializer):
    view = serializers.BooleanField()
    add = serializers.BooleanField()
    change = serializers.BooleanField()
    delete = serializers.BooleanField()


class SearchMetaSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    help = serializers.CharField(allow_blank=True)


class LinkMetaSerializer(serializers.Serializer):
    label = serializers.CharField()
    to = serializers.CharField()
    icon = serializers.CharField(allow_null=True)


class ResourceMetaSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    label_plural = serializers.CharField()
    group = serializers.CharField()
    icon = serializers.CharField()
    order = serializers.IntegerField()
    hidden = serializers.BooleanField()
    links = LinkMetaSerializer(many=True)
    auto_refresh = serializers.IntegerField(help_text="Секунды между автообновлениями списка, 0 — выключено")
    list_tabs = serializers.CharField(
        allow_null=True, help_text="Фильтр-поле вкладок над списком; счётчики — в tab_counts ответа списка",
    )
    permissions = PermissionsSerializer()
    list_display = ColumnMetaSerializer(many=True)
    list_display_links = serializers.ListField(child=serializers.CharField())
    list_filter = FilterMetaSerializer(many=True)
    search = SearchMetaSerializer()
    ordering = serializers.ListField(child=serializers.CharField())
    per_page = serializers.IntegerField()
    fields = FieldMetaSerializer(many=True)
    fieldsets = FieldsetMetaSerializer(many=True)
    inlines = InlineMetaSerializer(many=True)
    actions = ActionMetaSerializer(many=True)
    export = serializers.BooleanField()


class MetaSerializer(serializers.Serializer):
    resources = ResourceMetaSerializer(many=True)


class MetaView(StaffAPIMixin, APIView):
    @extend_schema(responses=MetaSerializer, operation_id="staff_meta")
    def get(self, request):
        return Response({"resources": [resource.describe(request) for resource in staff_site.visible(request)]})
