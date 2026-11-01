"""CRUD, действия, экспорт и подбор связей для любого зарегистрированного ресурса."""

from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action as drf_action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from . import audit
from .api import StaffAPIMixin
from .export import export_xlsx
from .fields import related_label
from .filters import resolve_field
from .pagination import StaffPagination
from .permissions import ResourcePermission
from .serializers import defer_heavy, preload_relations, row_fields

LOOKUP_LIMIT = 50
# Экраны, где показываются колонки раздела, — им нужны аннотации ресурса.
ROW_ACTIONS = {"list", "retrieve", "update", "partial_update", "export"}
# Экраны со строками таблицы: в ответе только колонки.
LIST_ACTIONS = {"list", "export"}


@extend_schema(exclude=True)
class ResourceViewSet(StaffAPIMixin, viewsets.ModelViewSet):
    """Базовый ViewSet; под каждый ресурс сайт создаёт подкласс с ``resource``."""

    resource = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    permission_classes = StaffAPIMixin.permission_classes + [ResourcePermission]
    pagination_class = StaffPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    # --- то, что DRF читает с view ---------------------------------------

    @property
    def search_fields(self):
        return self.resource.search_fields

    @property
    def ordering(self):
        return self.resource.ordering

    @property
    def ordering_fields(self):
        return [name for name in self.resource.get_list_display(self.request) if self.resource.sortable(name)] + ["id"]

    @property
    def filterset_class(self):
        return self.resource.site.filterset_for(self.resource, self.request)

    def get_queryset(self):
        qs = self.resource.get_queryset(self.request)
        if self.action in ROW_ACTIONS:
            qs = self.resource.annotate_rows(self.request, qs)
            names = row_fields(self.resource, self.request, list_only=self.action in LIST_ACTIONS)
            qs = preload_relations(self.resource, qs, names)
            if self.action in LIST_ACTIONS:
                qs = defer_heavy(self.resource, qs, names)
        return qs

    def get_serializer_class(self):
        return self.resource.site.serializer_for(self.resource, self.request, list_only=self.action in LIST_ACTIONS)

    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        response.data["page_size"] = self.paginator.get_page_size(self.request)
        if self.resource.list_tabs in self.resource.get_list_filter(self.request):
            response.data["tab_counts"] = self._tab_counts(self.resource.list_tabs)
        return response

    def _tab_counts(self, field):
        """Сколько строк в каждой вкладке — с поиском и прочими фильтрами, но без
        фильтра самой вкладки: иначе все вкладки, кроме текущей, показали бы ноль."""
        queryset = self.resource.get_queryset(self.request)
        params = self.request.query_params.copy()
        params.pop(field, None)
        queryset = self.filterset_class(params, queryset=queryset, request=self.request).qs
        queryset = SearchFilter().filter_queryset(self.request, queryset, self)
        rows = queryset.order_by().values_list(field).annotate(count=Count("pk"))
        return {str(value): count for value, count in rows}

    # --- запись ------------------------------------------------------------

    def perform_create(self, serializer):
        obj = self.resource.save(self.request, serializer, created=True)
        audit.log_addition(self.request, obj)

    def perform_update(self, serializer):
        self._check_object(serializer.instance)
        changed = self._changed_labels(serializer)
        obj = self.resource.save(self.request, serializer, created=False)
        audit.log_change(self.request, obj, changed)

    def perform_destroy(self, instance):
        self._check_object(instance)
        # Запись в журнал и удаление — вместе: отказ в удалении (остаток в минус,
        # «нельзя удалить себя») не должен оставить в журнале «удалено».
        with transaction.atomic():
            audit.log_deletion(self.request, instance)
            self.resource.delete(self.request, instance)

    def _changed_labels(self, serializer):
        """Подписи полей, значение которых правка действительно меняет — для журнала."""
        instance = serializer.instance
        labels = []
        for name, value in serializer.validated_data.items():
            if name not in self.resource.extra_fields:
                current = getattr(instance, name, None)
                if hasattr(current, "all"):
                    if {item.pk for item in current.all()} == {item.pk for item in value}:
                        continue
                elif current == value:
                    continue
            elif not value:
                continue
            labels.append(self.resource.describe_field(name)["label"])
        return labels

    def _check_object(self, obj):
        allowed = self.resource.can_modify(self.request, obj)
        if allowed is not True:
            raise PermissionDenied(allowed or "Этот объект менять нельзя.")

    # --- действия ----------------------------------------------------------

    def _get_action(self, name, detail):
        meta = self.resource.get_actions(self.request).get(name)
        if meta is None or meta["detail"] != detail:
            raise NotFound("Действие не найдено или недоступно.")
        return getattr(self.resource, name), meta

    def _form_data(self, meta, obj=None):
        fields = self.resource.action_form(self.request, meta, obj)
        if fields is None:
            return ()
        data = _body(self.request).get("data") or {}
        if not isinstance(data, dict):
            raise ValidationError({"data": "Ожидается объект с полями формы."})
        return (clean_action_data(fields, data),)

    @drf_action(detail=True, methods=["post"], url_path=r"actions/(?P<name>[\w]+)")
    def run_action(self, request, pk=None, name=None):
        func, meta = self._get_action(name, detail=True)
        obj = self.get_object()
        if not self.resource.action_available(request, meta, obj):
            raise ValidationError({"detail": "Действие недоступно для этого объекта — обновите страницу."})
        result = func(request, obj, *self._form_data(meta, obj))
        if _changed_something(result):
            audit.log_action(request, [obj], meta["label"])
        return _action_response(result)

    @drf_action(detail=False, methods=["post"], url_path=r"bulk-actions/(?P<name>[\w]+)")
    def run_bulk_action(self, request, name=None):
        func, meta = self._get_action(name, detail=False)
        ids = _body(request).get("ids") or []
        if not isinstance(ids, list) or not ids:
            raise ValidationError({"ids": "Выберите хотя бы одну строку."})
        if not all(isinstance(pk, int) and not isinstance(pk, bool) for pk in ids):
            raise ValidationError({"ids": "Ожидается список id."})
        queryset = self.get_queryset().filter(pk__in=ids)
        data = self._form_data(meta)
        # Список до действия: после него строки могут уже не подходить под выборку.
        objects = list(queryset)
        result = func(request, queryset, *data)
        if _changed_something(result):
            audit.log_action(request, objects, meta["label"])
        return _action_response(result)

    @drf_action(detail=False, methods=["get"])
    def export(self, request):
        if not self.resource.export:
            raise PermissionDenied("Экспорт для этого раздела выключен.")
        queryset = self.filter_queryset(self.get_queryset())
        return export_xlsx(self.resource, request, queryset)

    @drf_action(detail=False, methods=["get"], url_path=r"lookup/(?P<field>\w+)")
    def lookup(self, request, field=None):
        """Варианты для выпадашки связи: ``?search=`` и/или ``?ids=1,2``."""
        allowed = set(self.resource.get_fields(request)) | set(self.resource.get_list_filter(request))
        if field not in allowed or field in self.resource.extra_fields:
            raise NotFound("Поле недоступно.")
        model_field = resolve_field(self.resource.model, field)
        if not model_field.is_relation:
            raise NotFound("Поле не связь.")

        target = self.resource.site.resource_for_model(model_field.related_model)
        if target is not None:
            queryset = target.get_queryset(request)
            search_fields = target.search_fields
        elif request.user.is_superuser:
            queryset = model_field.related_model._default_manager.all()
            search_fields = ()
        else:
            queryset = model_field.related_model._default_manager.none()
            search_fields = ()

        ids = [part for part in request.query_params.get("ids", "").split(",") if part.strip().isdigit()]
        if ids:
            queryset = queryset.filter(pk__in=ids)
        search = request.query_params.get("search", "").strip()
        if search and search_fields:
            condition = Q()
            for name in search_fields:
                condition |= Q(**{f"{name}__icontains": search})
            queryset = queryset.filter(condition)

        items = [{"id": obj.pk, "label": related_label(obj)} for obj in queryset[:LOOKUP_LIMIT]]
        return Response({"results": items})


def _changed_something(result):
    """В журнал — только действия: не скачивания файлов (QR) и не отказы («не удалось»)."""
    if isinstance(result, HttpResponse):
        return False
    return (result or {}).get("level", "success") != "error"


def _body(request):
    """Тело запроса как объект; список или строка вместо объекта — 400, а не 500."""
    if not isinstance(request.data, dict):
        raise ValidationError({"detail": "Ожидается JSON-объект."})
    return request.data


def clean_action_data(fields, data):
    """Проверяет ввод формы действия по описанию полей; ошибки — 400 по полям."""
    cleaned, errors = {}, {}
    for field in fields:
        name = field["name"]
        value = data.get(name)
        if value in (None, "", []):
            if field.get("required"):
                errors[name] = ["Обязательное поле."]
            cleaned[name] = None
            continue
        kind = field.get("type", "string")
        if kind == "choice":
            allowed = {str(choice["value"]): choice["value"] for choice in field.get("choices") or ()}
            if str(value) not in allowed:
                errors[name] = ["Выберите вариант из списка."]
                continue
            value = allowed[str(value)]
        elif kind in ("integer", "decimal", "number"):
            try:
                value = int(value) if kind == "integer" else float(value)
            except (TypeError, ValueError):
                errors[name] = ["Введите число."]
                continue
        elif kind == "boolean":
            # Из формы может прийти строка: "false" — это «нет», а не непустая строка.
            value = value is True or str(value).lower() in ("true", "1", "on")
        else:
            value = str(value)
        cleaned[name] = value
    if errors:
        raise ValidationError(errors)
    return cleaned


def _action_response(result):
    if isinstance(result, HttpResponse):
        return result
    result = result or {}
    body = {"message": result.get("message", "Готово."), "level": result.get("level", "success")}
    # Действие создало объект (копия товара) — фронт откроет его карточку.
    if result.get("open"):
        body["open"] = result["open"]
    return Response(body, status=status.HTTP_200_OK)
