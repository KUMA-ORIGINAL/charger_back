"""Фильтры списка из ``list_filter`` — FilterSet для API и описание для фронта.

Параметры запроса повторяют синтаксис ORM, чтобы их было видно в адресной
строке: ``?status=1``, ``?spot=3``, ``?created_at__gte=2026-10-01``. Фильтр
может идти и через связи: ``"transaction__order__spot"`` в ``list_filter``
фильтрует чеки по точке заказа.
"""

import django_filters
from django.db import models
from django.db.models.constants import LOOKUP_SEP
from django.utils.text import capfirst

from .fields import model_field_type

RANGE_TYPES = ("integer", "decimal", "number")


def resolve_field(model, path):
    """Поле модели по пути ORM (``order__spot`` → ``Order.spot``)."""
    *hops, last = path.split(LOOKUP_SEP)
    for name in hops:
        model = model._meta.get_field(name).related_model
    return model._meta.get_field(last)


def _multiplies_rows(model, path):
    """Идёт ли путь через M2M или обратную связь — тогда фильтр размножает строки."""
    for name in path.split(LOOKUP_SEP):
        field = model._meta.get_field(name)
        if field.many_to_many or field.one_to_many:
            return True
        model = field.related_model
    return False


def filter_kind(resource, name):
    field = resolve_field(resource.model, name)
    kind = model_field_type(field)
    if kind == "choice":
        return "choice"
    if kind == "boolean":
        return "boolean"
    if kind in ("fk", "m2m"):
        return "relation"
    if kind in ("date", "datetime"):
        return "date_range"
    if kind in RANGE_TYPES and name in resource.range_filters:
        return "number_range"
    return "exact"


def describe(resource, name):
    field = resolve_field(resource.model, name)
    kind = filter_kind(resource, name)
    label = resource.labels.get(name) or capfirst(str(field.verbose_name))
    info = {"name": name, "label": label, "type": kind}
    if kind == "choice":
        info["choices"] = [{"value": value, "label": str(label)} for value, label in field.flatchoices]
    if kind == "relation":
        target = resource.site.resource_for_model(field.related_model)
        info["related_resource"] = target.key if target else None
    return info


def build_filterset(resource, names):
    attrs = {}
    for name in names:
        field = resolve_field(resource.model, name)
        kind = filter_kind(resource, name)
        if kind == "date_range":
            # По дате, а не по моменту: «по 21.10» включает весь день по Бишкеку.
            path = f"{name}__date" if isinstance(field, models.DateTimeField) else name
            attrs[f"{name}__gte"] = django_filters.DateFilter(field_name=path, lookup_expr="gte")
            attrs[f"{name}__lte"] = django_filters.DateFilter(field_name=path, lookup_expr="lte")
        elif kind == "number_range":
            attrs[f"{name}__gte"] = django_filters.NumberFilter(field_name=name, lookup_expr="gte")
            attrs[f"{name}__lte"] = django_filters.NumberFilter(field_name=name, lookup_expr="lte")
        elif kind == "boolean":
            attrs[name] = django_filters.BooleanFilter(field_name=name)
        elif kind == "choice":
            # Неизвестное значение — 400, а не 500 из ORM.
            attrs[name] = django_filters.ChoiceFilter(field_name=name, choices=field.flatchoices)
        elif kind == "relation" or model_field_type(field) in RANGE_TYPES:
            attrs[name] = django_filters.NumberFilter(
                field_name=name, distinct=_multiplies_rows(resource.model, name),
            )
        else:
            attrs[name] = django_filters.CharFilter(field_name=name, lookup_expr="exact")

    meta = type("Meta", (), {"model": resource.model, "fields": []})
    attrs["Meta"] = meta
    return type(f"{resource.model.__name__}StaffFilterSet", (django_filters.FilterSet,), attrs)
