"""Описание модели для React-админки — аналог ``ModelAdmin``.

Пример::

    @staff_site.register(Order)
    class OrderResource(StaffResource):
        group = "Продажи"
        list_display = ("id", "phone", "status", "total_price", "created_at")
        list_filter = ("status", "spot", "created_at")
        search_fields = ("phone",)

Что можно делать, решают стандартные права Django (``view``/``add``/``change``/
``delete``), как в Django admin: группы и права настраиваются сразу для обеих админок.
"""

from dataclasses import dataclass

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.utils.text import capfirst

from .fields import describe_model_field, model_field_type

OPERATIONS = ("view", "add", "change", "delete")


@dataclass(frozen=True)
class Inline:
    """Связанные строки в карточке объекта (как TabularInline).

    Без ``resource`` — только чтение. С ``resource`` (ключ скрытого ресурса
    связанной модели) и ``fk`` (поле связи на родителя) строки можно добавлять,
    менять и удалять прямо из карточки — с правами этого ресурса.
    """

    accessor: str
    label: str
    fields: tuple
    money_fields: tuple = ()
    resource: str = None
    fk: str = None
    # Подписи колонок короче verbose_name: {"payment_id": "ID платежа"}.
    labels: dict = None

    def describe(self, model):
        related = getattr(model, self.accessor).rel.related_model
        columns = []
        for name in self.fields:
            field = related._meta.get_field(name)
            columns.append({
                "format": "money" if name in self.money_fields else None,
                "name": name,
                "label": (self.labels or {}).get(name) or capfirst(str(field.verbose_name)),
                "type": model_field_type(field),
                "choices": _choices(field),
            })
        return {"name": self.accessor, "label": self.label, "columns": columns,
                "resource": self.resource, "fk": self.fk}


def display(label, *, type="string", badges=None, with_request=False):
    """Вычисляемая колонка или поле карточки: метод ресурса ``(self, obj)``,
    с ``with_request=True`` — ``(self, obj, request)`` (если значение зависит от
    того, что видит пользователь: остатки только по его точкам).

    ``type`` — как фронту показать значение (типы из :mod:`staff.fields` плюс
    ``badge``, ``table``: ``{"columns": [{name, label}], "rows": [...]}`` и
    ``link`` — ссылка на отфильтрованный список другого раздела:
    ``{"label": "Заказы клиента", "resource": "order", "filters": {"client": 5}}``,
    ``series`` — график ``{"unit", "normal": [min, max], "points": [{"t": iso, "v": число}]}``).
    """

    def decorator(func):
        func.staff_display = {"label": label, "type": type, "badges": badges, "with_request": with_request}
        return func

    return decorator


def action(label, *, detail=True, confirm=None, variant="default", permission="change",
           superuser_only=False, icon=None, form=None, available=None):
    """Действие над объектом (``detail=True``: ``(self, request, obj)``) или над
    выбранными строками (``detail=False``: ``(self, request, queryset)``).

    ``form`` — что спросить у пользователя перед запуском: список полей
    ``{"name", "label", "type", "required", "choices", "help_text"}`` или имя
    метода ``(self, request, obj) -> список`` (варианты зависят от объекта).
    С формой функция получает введённое последним аргументом: ``(..., data)``.

    ``available`` — имя метода ``(self, request, obj) -> bool``: кнопка видна
    только у подходящих объектов (повтор чека — только у «Не пробит»). Запуск
    у неподходящего объекта отклоняется и на бэкенде.

    Возвращает ``{"message": ..., "level": "success"|"info"|"warning"|"error"}``
    (с ``"open": {"resource", "id"}`` фронт перейдёт в карточку, например копии)
    либо готовый ``HttpResponse`` (файл).
    """

    def decorator(func):
        func.staff_action = {
            "label": label,
            "detail": detail,
            "confirm": confirm,
            "variant": variant,
            "permission": permission,
            "superuser_only": superuser_only,
            "icon": icon,
            "form": form,
            "available": available,
        }
        return func

    return decorator


class StaffResource:
    model: type[models.Model] = None
    key: str = None
    label: str = None
    label_plural: str = None
    group: str = "Прочее"
    icon: str = "table"
    order: int = 100
    # Не показывать в меню: ресурс нужен только как редактируемый инлайн.
    hidden: bool = False
    # Кнопки-ссылки над списком на особые экраны: (подпись, путь в панели, иконка[, право]).
    # С правом (``"add"``) кнопку видит только тот, у кого оно есть.
    links: tuple = ()
    # Раз в сколько секунд список перечитывается сам (новые заказы); 0 — не перечитывать.
    auto_refresh: int = 0
    # Поле с choices из list_filter, по которому над списком вкладки со счётчиками
    # («Все 4 148 · Оформлен 12 · …»): список отдаёт их в ``tab_counts``.
    list_tabs: str = None

    list_display: tuple = ("id",)
    list_display_links: tuple = None
    list_filter: tuple = ()
    # Числовые поля в list_filter по умолчанию фильтруются точным значением,
    # перечисленные здесь — диапазоном «от/до».
    range_filters: tuple = ()
    search_fields: tuple = ()
    search_help: str = ""
    ordering: tuple = ("-pk",)
    list_per_page: int = 25

    # Поля формы; None — все редактируемые поля модели.
    fields: tuple = None
    # [("Заголовок", ("поле", ...)), ...]; None — одна секция из fields.
    fieldsets: list = None
    readonly_fields: tuple = ()
    # Видны только суперпользователю: в списке, фильтрах, форме и ответах API.
    superuser_fields: tuple = ()
    inlines: tuple = ()
    # Суммы в сомах — фронт показывает их как деньги.
    money_fields: tuple = ()
    # Подписи короче verbose_name модели: {"product_photo": "Фото"}.
    labels: dict = {}
    # Другой виджет для поля модели: {"weekdays": {"type": "multichoice", "choices": [...]}}.
    widgets: dict = {}
    # Поля формы, которых нет в модели (пароль): {"new_password": {"label", "type", "help_text"}}.
    # Только запись: в ответах API их нет, значение забирает ``save`` из validated_data.
    extra_fields: dict = {}

    can_add = True
    can_change = True
    can_delete = True
    export = True

    select_related: tuple = ()
    prefetch_related: tuple = ()

    def __init__(self, site):
        self.site = site
        opts = self.model._meta
        self.key = self.key or opts.model_name
        self.label = self.label or capfirst(str(opts.verbose_name))
        self.label_plural = self.label_plural or capfirst(str(opts.verbose_name_plural))

    # ------------------------------------------------------------------
    # Права
    # ------------------------------------------------------------------

    def has_perm(self, request, operation):
        user = request.user
        if not (user and user.is_authenticated and user.is_active and user.is_staff):
            return False
        if operation != "view" and not getattr(self, f"can_{operation}"):
            return False
        opts = self.model._meta
        if operation == "view":
            return (user.has_perm(f"{opts.app_label}.view_{opts.model_name}")
                    or user.has_perm(f"{opts.app_label}.change_{opts.model_name}"))
        return user.has_perm(f"{opts.app_label}.{operation}_{opts.model_name}")

    def permissions(self, request):
        return {operation: self.has_perm(request, operation) for operation in OPERATIONS}

    # ------------------------------------------------------------------
    # Данные
    # ------------------------------------------------------------------

    def get_queryset(self, request):
        qs = self.model._default_manager.all()
        if self.select_related:
            qs = qs.select_related(*self.select_related)
        if self.prefetch_related:
            qs = qs.prefetch_related(*self.prefetch_related)
        return qs

    def annotate_rows(self, request, qs):
        """Дорогие аннотации для колонок (остаток, последняя температура).

        Вызывается только для списка, карточки и выгрузки самого раздела — не
        для выпадашек связей, фильтров и дашборда, где те же строки нужны без них.
        """
        return qs

    def save(self, request, serializer, created):
        """Сохраняет форму.

        Значения ``extra_fields`` в модель не идут — их получает :meth:`save_extra`.
        """
        values = {
            name: serializer.validated_data.pop(name)
            for name in self.extra_fields if name in serializer.validated_data
        }
        obj = serializer.save()
        if self.extra_fields:
            self.save_extra(request, obj, values, created)
        return obj

    def save_extra(self, request, obj, values, created):
        """Обработка полей из ``extra_fields`` после сохранения объекта."""

    def validate(self, request, data, instance):
        """Проверка формы целиком (как ``Serializer.validate``): ``instance`` —
        ``None`` при создании. Ошибки — ``serializers.ValidationError({поле: [...]})``."""
        return data

    def delete(self, request, obj):
        obj.delete()

    def label_for(self, obj):
        """Как подписать объект в связях и выпадашках (по умолчанию ``__str__``)."""
        return str(obj)

    def can_modify(self, request, obj):
        """Можно ли менять и удалять именно этот объект (права на модель уже есть).

        Возвращает ``True`` или текст отказа: он уйдёт пользователю как 403.
        """
        return True

    # ------------------------------------------------------------------
    # Что показывать этому пользователю
    # ------------------------------------------------------------------

    def _visible(self, request, names):
        if request.user.is_superuser:
            return tuple(names)
        return tuple(name for name in names if name not in self.superuser_fields)

    def get_list_display(self, request):
        return self._visible(request, self.list_display)

    def get_list_filter(self, request):
        return self._visible(request, self.list_filter)

    def get_fields(self, request):
        if self.fields is not None:
            names = self.fields
        elif self.fieldsets is not None:
            names = tuple(name for _, section in self.fieldsets for name in section)
        else:
            names = tuple(
                field.name for field in self.model._meta.get_fields()
                if field.concrete and not field.auto_created and field.editable
            ) + tuple(field.name for field in self.model._meta.many_to_many)
        return self._visible(request, names)

    def get_readonly_fields(self, request):
        return self._visible(request, self.readonly_fields)

    def get_fieldsets(self, request):
        fields = self.get_fields(request)
        if self.fieldsets is None:
            return [{"title": None, "fields": list(fields)}]
        sections = []
        for title, names in self.fieldsets:
            names = [name for name in names if name in fields]
            if names:
                sections.append({"title": title, "fields": names})
        return sections

    def get_actions(self, request):
        result = {}
        for name in dir(type(self)):
            func = getattr(type(self), name, None)
            meta = getattr(func, "staff_action", None)
            if not meta:
                continue
            if meta["superuser_only"] and not request.user.is_superuser:
                continue
            if not self.has_perm(request, meta["permission"]):
                continue
            result[name] = meta
        return result

    def action_available(self, request, meta, obj):
        if not meta["available"]:
            return True
        return bool(getattr(self, meta["available"])(request, obj))

    def action_form(self, request, meta, obj=None):
        form = meta["form"]
        if isinstance(form, str):
            return list(getattr(self, form)(request, obj))
        return list(form) if form else None

    def object_actions(self, request, obj):
        """Detail-действия, доступные для этого объекта, с их формами — для карточки."""
        return {
            name: {"form": self.action_form(request, meta, obj)}
            for name, meta in self.get_actions(request).items()
            if meta["detail"] and self.action_available(request, meta, obj)
        }

    def computed(self, name):
        func = getattr(type(self), name, None)
        return func if getattr(func, "staff_display", None) else None

    # ------------------------------------------------------------------
    # Описание для фронта
    # ------------------------------------------------------------------

    def _has_field(self, name):
        try:
            self.model._meta.get_field(name)
        except FieldDoesNotExist:
            return False
        return True

    def describe_field(self, name):
        if name in self.extra_fields:
            extra = self.extra_fields[name]
            return {
                "name": name,
                "label": extra["label"],
                "type": extra.get("type", "string"),
                "badges": None,
                "read_only": False,
                "required": extra.get("required", False),
                "help_text": extra.get("help_text", ""),
                "computed": False,
                "write_only": True,
                "format": None,
            }
        func = self.computed(name)
        if func is not None:
            meta = func.staff_display
            return {
                "name": name,
                "label": meta["label"],
                "type": meta["type"],
                "badges": meta["badges"],
                "read_only": True,
                "required": False,
                "help_text": "",
                "computed": True,
                "format": "money" if name in self.money_fields else None,
            }
        info = describe_model_field(self.model._meta.get_field(name), self.site)
        info["badges"] = None
        info["computed"] = False
        info["format"] = "money" if name in self.money_fields else None
        if name in self.labels:
            info["label"] = self.labels[name]
        if name in self.widgets:
            info.update(self.widgets[name])
        if name in self.readonly_fields:
            info["read_only"] = True
        return info

    def sortable(self, name):
        return self.computed(name) is None and self._has_field(name) and not isinstance(
            self.model._meta.get_field(name), models.ManyToManyField
        )

    def describe(self, request):
        list_display = self.get_list_display(request)
        readonly = set(self.get_readonly_fields(request))
        detail_names = list(dict.fromkeys(
            list(self.get_fields(request)) + list(self.get_readonly_fields(request))
        ))
        return {
            "key": self.key,
            "label": self.label,
            "label_plural": self.label_plural,
            "group": self.group,
            "icon": self.icon,
            "order": self.order,
            "hidden": self.hidden,
            "links": [
                {"label": link[0], "to": link[1], "icon": link[2]}
                for link in self.links if len(link) < 4 or self.has_perm(request, link[3])
            ],
            "auto_refresh": self.auto_refresh,
            "list_tabs": self.list_tabs if self.list_tabs in self.get_list_filter(request) else None,
            "permissions": self.permissions(request),
            "list_display": [
                dict(self.describe_field(name), sortable=self.sortable(name)) for name in list_display
            ],
            "list_display_links": list(self.list_display_links or list_display[:2]),
            "list_filter": [self.site.filters.describe(self, name) for name in self.get_list_filter(request)],
            "search": {
                "enabled": bool(self.search_fields),
                "help": self.search_help,
            },
            "ordering": list(self.ordering),
            "per_page": self.list_per_page,
            # read_only по запросу: get_readonly_fields может зависеть от роли.
            "fields": [
                dict(self.describe_field(name), **({"read_only": True} if name in readonly else {}))
                for name in detail_names
            ],
            "fieldsets": self.get_fieldsets(request) + self._readonly_section(request),
            "inlines": [inline.describe(self.model) for inline in self.inlines],
            "actions": [
                {
                    "name": name,
                    **{k: v for k, v in meta.items() if k not in ("superuser_only", "available", "form")},
                    # Форма, зависящая от объекта, приходит с самим объектом (``_actions``).
                    "form": None if isinstance(meta["form"], str) else self.action_form(request, meta),
                }
                for name, meta in self.get_actions(request).items()
            ],
            "export": self.export,
        }

    def _readonly_section(self, request):
        fields = self.get_fields(request)
        extra = [name for name in self.get_readonly_fields(request) if name not in fields]
        return [{"title": "Сведения", "fields": extra}] if extra else []


def _choices(field):
    if not getattr(field, "choices", None):
        return None
    return [{"value": value, "label": str(label)} for value, label in field.flatchoices]
