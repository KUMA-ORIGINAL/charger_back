"""Сериализатор ресурса строится из его описания, а не пишется руками.

Связи отдаются как ``{id, label}`` (чтобы список не делал запрос на каждую
ячейку), а принимаются как id. Выбор для связи ограничен тем, что пользователь
видит в ресурсе целевой модели: владелец не привяжет товар к чужой точке.
"""

from django.core.exceptions import FieldDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.db.models import prefetch_related_objects
from phonenumber_field.modelfields import PhoneNumberField
from phonenumber_field.serializerfields import PhoneNumberField as PhoneNumberSerializerField
from rest_framework import serializers
from rest_framework.settings import api_settings

from .fields import plain, related_label


class RelatedLabelField(serializers.PrimaryKeyRelatedField):
    def use_pk_only_optimization(self):
        return False

    def to_representation(self, value):
        return {"id": value.pk, "label": related_label(value)}

    def to_internal_value(self, data):
        if isinstance(data, dict):
            data = data.get("id")
        return super().to_internal_value(data)


class FileUrlField(serializers.ImageField):
    """Файл отдаётся путём от корня сайта: админка живёт на том же домене."""

    def to_representation(self, value):
        return value.url if value else None


class FileUrlPlainField(serializers.FileField):
    def to_representation(self, value):
        return value.url if value else None


class ResourceModelSerializer(serializers.ModelSerializer):
    serializer_related_field = RelatedLabelField
    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.ImageField: FileUrlField,
        models.FileField: FileUrlPlainField,
        # Номер проверяется и приводится к +996… так же, как в модели.
        PhoneNumberField: PhoneNumberSerializerField,
    }

    def build_standard_field(self, field_name, model_field):
        field_class, field_kwargs = super().build_standard_field(field_name, model_field)
        if isinstance(model_field, models.DecimalField):
            field_kwargs["coerce_to_string"] = False
        return field_class, field_kwargs

    def save(self, **kwargs):
        try:
            return super().save(**kwargs)
        except DjangoValidationError as exc:
            # Модели проверяют себя в save() (StockMovement.full_clean) — отдаём
            # это как ошибку формы, а не как 500.
            if hasattr(exc, "message_dict"):
                raise serializers.ValidationError(exc.message_dict)
            raise serializers.ValidationError({api_settings.NON_FIELD_ERRORS_KEY: exc.messages})


def row_fields(resource, request, list_only=False):
    """Поля в ответе: для списка и выгрузки — только колонки, для карточки — все."""
    list_fields = tuple(resource.get_list_display(request))
    if list_only:
        return list(dict.fromkeys(("id",) + list_fields))
    form_fields = tuple(resource.get_fields(request))
    readonly = tuple(resource.get_readonly_fields(request))
    return list(dict.fromkeys(("id",) + list_fields + form_fields + readonly))


def preload_relations(resource, queryset, names):
    """Связи из ответа — одним запросом на поле, а не запросом на каждую строку."""
    select, prefetch = [], []
    for name in names:
        if name in resource.extra_fields or resource.computed(name) is not None:
            continue
        try:
            field = resource.model._meta.get_field(name)
        except FieldDoesNotExist:
            continue
        if field.many_to_many or field.one_to_many:
            prefetch.append(name)
        elif field.is_relation:
            select.append(name)
    if select:
        queryset = queryset.select_related(*select)
    if prefetch:
        queryset = queryset.prefetch_related(*prefetch)
    return queryset


# Поля, которые могут весить килобайты на строку (ответы банка и кассы, сырая
# телеметрия). Не TextField: его читают вычисляемые колонки (сообщение журнала),
# и отложенное поле стало бы запросом на строку.
HEAVY_FIELDS = (models.JSONField, models.BinaryField)


def defer_heavy(resource, queryset, names):
    """Список и выгрузка не читают тяжёлые поля, которых нет в колонках, — ни у
    самой модели, ни у связей из ``select_related`` (JSON транзакции в чеках)."""
    deferred = [
        field.name for field in resource.model._meta.concrete_fields
        if isinstance(field, HEAVY_FIELDS) and field.name not in names
    ]
    deferred += _heavy_related(resource.model, queryset.query.select_related, "")
    return queryset.defer(*deferred) if deferred else queryset


def _heavy_related(model, tree, prefix):
    if not isinstance(tree, dict):
        return []
    result = []
    for name, subtree in tree.items():
        related = model._meta.get_field(name).related_model
        path = f"{prefix}{name}__"
        result += [
            path + field.name for field in related._meta.concrete_fields if isinstance(field, HEAVY_FIELDS)
        ]
        result += _heavy_related(related, subtree, path)
    return result


def build_serializer(resource, request, list_only=False):
    """Сериализатор под конкретного пользователя: набор полей зависит от роли.

    ``list_only`` — для списка и выгрузки: только колонки, без действий и инлайнов
    (фронт берёт из строки списка только их и ``id``).
    """
    model = resource.model
    form_fields = resource.get_fields(request)
    readonly = set(resource.get_readonly_fields(request))

    names = row_fields(resource, request, list_only)
    extra_names = [name for name in names if name in resource.extra_fields]
    model_names = [name for name in names if resource.computed(name) is None and name not in extra_names]
    computed_names = [name for name in names if resource.computed(name) is not None]
    editable = set(form_fields) - readonly

    attrs = {}
    for name in computed_names:
        attrs[name] = serializers.SerializerMethodField()
        attrs[f"get_{name}"] = _computed_getter(resource, name, request)

    for name in extra_names:
        attrs[name] = serializers.CharField(
            write_only=True, required=False, allow_blank=True, trim_whitespace=False,
        )

    attrs["validate"] = _validator(resource, request)

    if not list_only and any(meta["detail"] for meta in resource.get_actions(request).values()):
        attrs["_actions"] = serializers.SerializerMethodField()
        attrs["get__actions"] = _actions_getter(resource, request)
        computed_names.append("_actions")

    if not list_only and resource.inlines:
        attrs["inlines"] = serializers.SerializerMethodField()
        attrs["get_inlines"] = _inlines_getter(resource)
        computed_names.append("inlines")

    extra_kwargs = {}
    for name in model_names:
        if name == "id":
            continue
        if name not in editable:
            extra_kwargs[name] = {"read_only": True}
            continue
        field = model._meta.get_field(name)
        if field.is_relation:
            target = resource.site.resource_for_model(field.related_model)
            extra_kwargs[name] = {"queryset": _RelatedQueryset(target, field.related_model, request)}

    meta = type("Meta", (), {
        "model": model,
        "fields": model_names + computed_names + extra_names,
        "read_only_fields": ("id",),
        "extra_kwargs": extra_kwargs,
    })
    attrs["Meta"] = meta
    return type(f"{model.__name__}StaffSerializer", (ResourceModelSerializer,), attrs)


def _computed_getter(resource, name, request):
    # Поля только карточки (таблица остатков, график) в сериализатор списка не
    # попадают (row_fields): там это был бы запрос на каждую строку страницы.
    func = getattr(resource, name)
    with_request = func.staff_display.get("with_request")

    def getter(self, obj):
        return plain(func(obj, request) if with_request else func(obj))

    return getter


def _validator(resource, request):
    def validate(self, data):
        return resource.validate(request, data, self.instance)

    return validate


def _actions_getter(resource, request):
    # Только в карточке: доступность считается по объекту и может стоить запроса.
    def getter(self, obj):
        return resource.object_actions(request, obj)

    return getter


def _inlines_getter(resource):
    def getter(self, obj):
        result = {}
        for inline in resource.inlines:
            manager = getattr(obj, inline.accessor)
            rows = list(manager.all())
            # Связи в колонках инлайна (товар в составе заказа) — запросом на поле,
            # а не на строку. Строки могли быть уже подгружены ресурсом (prefetch).
            fields = (manager.model._meta.get_field(name) for name in inline.fields)
            related = [field.name for field in fields if field.many_to_one or field.one_to_one]
            if related:
                prefetch_related_objects(rows, *related)
            result[inline.accessor] = [
                {"id": row.pk, **{name: plain(getattr(row, name)) for name in inline.fields}}
                for row in rows
            ]
        return result

    return getter


class _RelatedQueryset:
    """Ленивый queryset связи: вычисляется на запросе, а не при импорте.

    DRF вызывает ``.all()`` у queryset поля — отдаём то, что пользователь видит
    в целевом ресурсе. Модель без ресурса доступна только суперпользователю.
    """

    def __init__(self, target, model, request):
        self.target = target
        self.model = model
        self.request = request

    def all(self):
        if self.target is not None:
            return self.target.get_queryset(self.request)
        manager = self.model._default_manager
        return manager.all() if self.request.user.is_superuser else manager.none()

    def __getattr__(self, name):
        return getattr(self.all(), name)
