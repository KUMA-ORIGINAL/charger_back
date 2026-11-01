"""Разделы React-админки (``admin-ui``) для зарядной сети. Django-версия — ``account/admin/``."""

import logging
from io import BytesIO

import qrcode
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from staff.resources import Inline, StaffResource, action, display
from staff.site import staff_site

from .models import (
    ChargePoint,
    ChargePointCSMS,
    ChargingSession,
    ChargingSessionMeterValue,
    CSMSService,
    CSMSTransactionMapping,
    User,
)
from .services.ocpp_commands import (
    change_availability,
    clear_charging_profile,
    get_configuration,
    is_cp_connected,
    reset_station,
    start_charging,
    stop_charging,
    trigger_boot_notification,
    trigger_meter_values,
    trigger_status,
)
from .services.payment_qr_generator import build_payment_qr_link_without_amount

logger = logging.getLogger(__name__)

TELEMETRY_POINTS = 120
MEASUREMENTS_SHOWN = 30

ONLINE_BADGES = {"online": "green", "offline": "red"}
SESSION_BADGES = {
    "preparing": "amber",
    "charging": "cyan",
    "stopped": "gray",
    "completed": "green",
    "error": "red",
}
SOURCE_BADGES = {"payment": "violet", "csms": "orange"}


def _badges(mapping):
    return {str(value): color for value, color in mapping.items()}


class BadgesMixin:
    """``badges = {"поле": {значение: цвет}}`` — цветные бейджи у полей с choices."""

    badges: dict = {}

    def describe_field(self, name):
        info = super().describe_field(name)
        if name in self.badges:
            info["badges"] = _badges(self.badges[name])
        return info


def _number(value):
    return None if value is None else float(value)


# ----------------------------------------------------------------------
# Станции
# ----------------------------------------------------------------------


@staff_site.register(ChargePoint)
class ChargePointResource(StaffResource):
    key = "chargepoint"
    label = "Станция"
    label_plural = "Станции"
    group = "Сеть"
    icon = "zap"
    order = 10
    auto_refresh = 30

    list_display = ("id", "cp_id", "name", "online", "is_occupied", "occupied_by", "active_transaction_id")
    list_display_links = ("id", "cp_id", "name")
    list_filter = ("is_occupied",)
    search_fields = ("cp_id", "name", "charge24_cp_id")
    search_help = "ID станции или название"
    ordering = ("name",)

    fieldsets = [
        ("Станция", ("cp_id", "name", "charge24_cp_id", "online")),
        ("Состояние", ("is_occupied", "occupied_by", "active_transaction_id")),
        ("Оплата", ("payment_qr_link",)),
        ("Служебное", ("created_at", "updated_at")),
    ]
    readonly_fields = (
        "online", "is_occupied", "occupied_by", "active_transaction_id", "created_at", "updated_at",
    )
    labels = {
        "cp_id": "ID станции", "name": "Название", "charge24_cp_id": "ID в Charge24",
        "is_occupied": "Занята", "occupied_by": "Кем занята", "active_transaction_id": "Активная транзакция",
        "payment_qr_link": "QR-ссылка для оплаты", "created_at": "Создана", "updated_at": "Обновлена",
    }
    inlines = (
        Inline(
            accessor="csms_links", label="Подключения к CSMS", fields=("csms_service", "remote_cp_id"),
            resource="chargepointcsms", fk="charge_point",
        ),
    )

    def describe_field(self, name):
        info = super().describe_field(name)
        if name == "online":
            info["badges"] = _badges(ONLINE_BADGES)
        return info

    @display("Связь", type="badge")
    def online(self, obj):
        try:
            connected = is_cp_connected(obj.cp_id)
        except Exception:
            logger.exception("Не удалось проверить связь со станцией %s", obj.cp_id)
            return {"value": "offline", "label": "Нет данных"}
        return {"value": "online", "label": "На связи"} if connected else {"value": "offline", "label": "Нет связи"}

    # --- команды станции ---------------------------------------------------

    def _command(self, obj, sender, success):
        if not is_cp_connected(obj.cp_id):
            return {"message": f"Станция {obj.cp_id} не подключена — команда не отправлена", "level": "warning"}
        try:
            sender(obj.cp_id)
        except Exception as exc:
            logger.exception("Команда станции %s не отправлена", obj.cp_id)
            return {"message": f"Не удалось отправить команду: {exc}", "level": "error"}
        return {"message": f"{success} → {obj.cp_id}", "level": "success"}

    @action("Начать зарядку", icon="play")
    def start_charging_action(self, request, obj):
        return self._command(obj, start_charging, "RemoteStartTransaction отправлен")

    @action("Остановить зарядку", icon="square", confirm="Остановить текущую зарядку?",
            available="has_active_transaction")
    def stop_charging_action(self, request, obj):
        return self._command(
            obj, lambda cp_id: stop_charging(cp_id, transaction_id=obj.active_transaction_id),
            "RemoteStopTransaction отправлен",
        )

    def has_active_transaction(self, request, obj):
        return bool(obj.active_transaction_id)

    @action("Запросить статус", icon="radio")
    def trigger_status_action(self, request, obj):
        def send(cp_id):
            trigger_status(cp_id, connector_id=0)
            trigger_status(cp_id, connector_id=1)

        return self._command(obj, send, "TriggerMessage StatusNotification отправлен")

    @action("Включить станцию", icon="power")
    def make_operative_action(self, request, obj):
        def send(cp_id):
            change_availability(cp_id, connector_id=0, availability_type="Operative")
            change_availability(cp_id, connector_id=1, availability_type="Operative")

        return self._command(obj, send, "ChangeAvailability Operative отправлен")

    @action("Отключить станцию", icon="power-off", variant="destructive",
            confirm="Станция станет недоступной для зарядки. Продолжить?")
    def make_inoperative_action(self, request, obj):
        def send(cp_id):
            change_availability(cp_id, connector_id=0, availability_type="Inoperative")
            change_availability(cp_id, connector_id=1, availability_type="Inoperative")

        return self._command(obj, send, "ChangeAvailability Inoperative отправлен")

    @action("Мягкая перезагрузка", icon="refresh-cw", confirm="Перезагрузить станцию (Soft)?")
    def soft_reset_action(self, request, obj):
        return self._command(obj, lambda cp_id: reset_station(cp_id, reset_type="Soft"), "Soft Reset отправлен")

    @action("Жёсткая перезагрузка", icon="zap-off", variant="destructive",
            confirm="Жёсткая перезагрузка прервёт активные сессии. Продолжить?")
    def hard_reset_action(self, request, obj):
        return self._command(obj, lambda cp_id: reset_station(cp_id, reset_type="Hard"), "Hard Reset отправлен")

    @action("Очистить профиль зарядки", icon="eraser", confirm="Очистить профиль зарядки на станции?")
    def clear_charging_profile_action(self, request, obj):
        return self._command(obj, clear_charging_profile, "ClearChargingProfile отправлен")

    @action("Получить конфигурацию", icon="settings")
    def get_configuration_action(self, request, obj):
        return self._command(obj, get_configuration, "GetConfiguration отправлен")

    @action("Запросить BootNotification", icon="rotate-cw")
    def trigger_boot_action(self, request, obj):
        return self._command(obj, trigger_boot_notification, "TriggerMessage BootNotification отправлен")

    @action("Запросить показания счётчика", icon="gauge")
    def trigger_meter_values_action(self, request, obj):
        return self._command(
            obj, lambda cp_id: trigger_meter_values(cp_id, connector_id=1),
            "TriggerMessage MeterValues отправлен",
        )

    @action("Скачать QR-код оплаты", icon="qr-code")
    def download_qrcode(self, request, obj):
        box_value = f"111{obj.pk:012d}"
        try:
            link = build_payment_qr_link_without_amount(
                account_number="1240040002323627",
                box_name=f"BAKAIGULBOX.{box_value}",
                client_name="Rouming Charge",
                door=f"Станция ID: {obj.pk}",
            )
            obj.payment_qr_link = link
            obj.save(update_fields=["payment_qr_link"])
        except Exception as exc:
            logger.exception("Ошибка генерации QR-кода для ChargePoint id=%s", obj.pk)
            return {"message": f"Ошибка генерации QR-кода: {exc}", "level": "error"}

        buffer = BytesIO()
        qrcode.make(obj.payment_qr_link).save(buffer, format="PNG")
        response = HttpResponse(buffer.getvalue(), content_type="image/png")
        response["Content-Disposition"] = f'attachment; filename="charge_point_{obj.pk}_qrcode.png"'
        return response


@staff_site.register(ChargePointCSMS)
class ChargePointCSMSResource(StaffResource):
    """Скрытый ресурс — строки «Подключения к CSMS» в карточке станции."""

    key = "chargepointcsms"
    hidden = True
    fields = ("charge_point", "csms_service", "remote_cp_id")
    list_display = ("id", "charge_point", "csms_service", "remote_cp_id")
    select_related = ("charge_point", "csms_service")
    labels = {"charge_point": "Станция", "csms_service": "CSMS", "remote_cp_id": "ID станции в CSMS"}


# ----------------------------------------------------------------------
# Сессии зарядки
# ----------------------------------------------------------------------


@staff_site.register(ChargingSession)
class ChargingSessionResource(BadgesMixin, StaffResource):
    key = "chargingsession"
    label = "Сессия"
    label_plural = "Сессии зарядки"
    group = "Сеть"
    icon = "battery-charging"
    order = 20
    auto_refresh = 15
    list_tabs = "status"

    can_add = False
    can_change = False
    can_delete = False

    list_display = (
        "id", "charge_point", "source", "status", "started_at", "duration",
        "consumed_kwh", "soc_progress", "power", "total_cost",
    )
    list_display_links = ("id",)
    list_filter = ("status", "source", "csms_name", "charge_point", "started_at")
    search_fields = ("id_tag", "transaction_id", "csms_transaction_id", "charge_point__cp_id")
    search_help = "Метка, номер транзакции или станция"
    ordering = ("-created_at",)
    range_filters = ()
    select_related = ("charge_point",)
    money_fields = ("total_cost", "initial_balance", "cost_per_kwh")

    fieldsets = [
        ("Станция и транзакция", (
            "charge_point", "source", "csms_name", "status", "transaction_id",
            "csms_transaction_id", "connector_id", "id_tag",
        )),
        ("Время", ("started_at", "stopped_at", "duration", "last_meter_at", "stop_reason")),
        ("Энергия", (
            "start_meter_value", "last_meter_value", "stop_meter_value", "consumed_kwh",
            "power", "average_power", "last_voltage", "last_current",
        )),
        ("Заряд батареи", ("start_soc", "last_soc", "soc_progress")),
        ("Биллинг", ("initial_balance", "cost_per_kwh", "total_cost")),
        ("Телеметрия", ("power_chart", "soc_chart", "measurements")),
        ("Служебное", ("created_at", "updated_at")),
    ]
    readonly_fields = tuple(
        name for _, section in fieldsets for name in section
    )
    labels = {
        "charge_point": "Станция", "source": "Источник", "csms_name": "CSMS", "status": "Статус",
        "transaction_id": "Транзакция станции", "csms_transaction_id": "Транзакция CSMS",
        "connector_id": "Коннектор", "id_tag": "Метка (idTag)", "started_at": "Начало",
        "stopped_at": "Конец", "last_meter_at": "Последний замер", "stop_reason": "Причина остановки",
        "start_meter_value": "Счётчик на старте, Wh", "last_meter_value": "Счётчик сейчас, Wh",
        "stop_meter_value": "Счётчик на финише, Wh", "consumed_kwh": "Потреблено, кВт⋅ч",
        "last_voltage": "Напряжение, В", "last_current": "Ток, А", "start_soc": "Заряд на старте, %",
        "last_soc": "Заряд сейчас, %", "initial_balance": "Оплачено", "cost_per_kwh": "Тариф за кВт⋅ч",
        "total_cost": "Стоимость", "created_at": "Создана", "updated_at": "Обновлена",
    }
    badges = {"status": SESSION_BADGES, "source": SOURCE_BADGES}

    @display("Длительность")
    def duration(self, obj):
        return obj.duration_display if obj.started_at else None

    @display("Заряд батареи")
    def soc_progress(self, obj):
        if obj.last_soc is None:
            return None
        if obj.start_soc is None:
            return f"{obj.last_soc}%"
        return f"{obj.start_soc}% → {obj.last_soc}% ({obj.soc_gain or 0:+.0f})"

    @display("Мощность")
    def power(self, obj):
        if obj.last_power_kw is None:
            return None
        if obj.max_power_kw is None:
            return f"{obj.last_power_kw} кВт"
        return f"{obj.last_power_kw} кВт (макс. {obj.max_power_kw})"

    @display("Средняя мощность")
    def average_power(self, obj):
        return f"{obj.average_power_kw:.2f} кВт"

    def _series(self, obj, field, unit):
        rows = list(
            obj.meter_values.exclude(**{f"{field}__isnull": True})
            .order_by("-sampled_at").values_list("sampled_at", field)[:TELEMETRY_POINTS]
        )
        return {"unit": unit, "normal": None, "points": [{"t": t, "v": float(v)} for t, v in reversed(rows)]}

    @display("Мощность по времени", type="series")
    def power_chart(self, obj):
        return self._series(obj, "power_kw", "кВт")

    @display("Заряд батареи по времени", type="series")
    def soc_chart(self, obj):
        return self._series(obj, "soc", "%")

    @display("Последние замеры", type="table")
    def measurements(self, obj):
        rows = obj.meter_values.order_by("-sampled_at")[:MEASUREMENTS_SHOWN]
        return {
            "columns": [
                {"name": "time", "label": "Время"}, {"name": "kwh", "label": "кВт⋅ч"},
                {"name": "power", "label": "кВт"}, {"name": "soc", "label": "Заряд, %"},
                {"name": "voltage", "label": "В"}, {"name": "current", "label": "А"},
            ],
            "rows": [
                {
                    "time": row.sampled_at.isoformat(), "kwh": _number(row.consumed_kwh),
                    "power": _number(row.power_kw), "soc": _number(row.soc),
                    "voltage": _number(row.voltage), "current": _number(row.current),
                }
                for row in rows
            ],
        }

    def can_stop(self, request, obj):
        return obj.status in ("preparing", "charging") and bool(obj.transaction_id)

    @action("Остановить зарядку", icon="square", variant="destructive", permission="view",
            confirm="Отправить станции команду остановки?", available="can_stop")
    def stop_session(self, request, obj):
        if not request.user.has_perm("account.change_chargepoint"):
            raise PermissionDenied("Нужно право менять станции.")
        cp_id = obj.charge_point.cp_id
        if not is_cp_connected(cp_id):
            return {"message": f"Станция {cp_id} не подключена — команда не отправлена", "level": "warning"}
        stop_charging(cp_id, transaction_id=obj.transaction_id)
        return {"message": f"RemoteStopTransaction отправлен → {cp_id}", "level": "success"}


@staff_site.register(ChargingSessionMeterValue)
class MeterValueResource(StaffResource):
    """Замеры телеметрии: только чтение, в основном ради выгрузки."""

    key = "metervalue"
    label = "Замер"
    label_plural = "Замеры сессий"
    group = "Сеть"
    icon = "activity"
    order = 25
    hidden = True

    can_add = False
    can_change = False
    can_delete = False
    list_display = ("id", "session", "sampled_at", "consumed_kwh", "power_kw", "soc", "voltage", "current")
    list_filter = ("session", "sampled_at")
    ordering = ("-sampled_at",)
    select_related = ("session",)


# ----------------------------------------------------------------------
# CSMS
# ----------------------------------------------------------------------


@staff_site.register(CSMSService)
class CSMSServiceResource(StaffResource):
    key = "csmsservice"
    label = "CSMS-сервис"
    label_plural = "CSMS-сервисы"
    group = "Сеть"
    icon = "server"
    order = 30

    list_display = ("id", "name", "service_type", "is_active", "ws_url_template")
    list_display_links = ("id", "name")
    list_filter = ("service_type", "is_active")
    search_fields = ("name",)
    ordering = ("name",)
    fields = ("name", "service_type", "is_active", "ws_url_template")
    readonly_fields = ()
    labels = {
        "name": "Название", "service_type": "Тип", "is_active": "Активен", "ws_url_template": "WebSocket URL",
    }
    inlines = (
        Inline(
            accessor="charge_points", label="Станции", fields=("charge_point", "remote_cp_id"),
            resource="chargepointcsms", fk="csms_service",
        ),
    )


@staff_site.register(CSMSTransactionMapping)
class CSMSTransactionMappingResource(StaffResource):
    key = "csmstransactionmapping"
    label = "Соответствие транзакций"
    label_plural = "Соответствия транзакций CSMS"
    group = "Сеть"
    icon = "git-compare"
    order = 40

    can_add = False
    list_display = (
        "id", "charge_point", "csms_name", "csms_transaction_id", "station_transaction_id", "id_tag", "is_active",
    )
    list_filter = ("is_active", "csms_name", "charge_point")
    search_fields = ("csms_name", "id_tag", "charge_point__cp_id")
    ordering = ("-created_at",)
    select_related = ("charge_point",)
    labels = {
        "charge_point": "Станция", "csms_name": "CSMS", "csms_transaction_id": "Транзакция CSMS",
        "station_transaction_id": "Транзакция станции", "id_tag": "Метка", "is_active": "Активно",
    }


# ----------------------------------------------------------------------
# Сотрудники и пользователи
# ----------------------------------------------------------------------


@staff_site.register(User)
class UserResource(StaffResource):
    key = "user"
    label = "Пользователь"
    label_plural = "Пользователи"
    group = "Администрирование"
    icon = "users"
    order = 80

    list_display = ("id", "phone_number", "full_name", "is_staff", "is_active", "last_login")
    list_display_links = ("id", "phone_number")
    list_filter = ("is_staff", "is_active")
    search_fields = ("phone_number", "first_name", "last_name")
    search_help = "Телефон или имя"
    ordering = ("-date_joined",)

    fieldsets = [
        ("Пользователь", ("phone_number", "last_name", "first_name", "middle_name", "email")),
        ("Доступ", ("is_active", "is_staff", "is_superuser", "groups")),
        ("Пароль", ("new_password",)),
        ("Служебное", ("last_login", "date_joined")),
    ]
    readonly_fields = ("last_login", "date_joined")
    superuser_fields = ("is_staff", "is_superuser", "groups")
    extra_fields = {
        "new_password": {
            "label": "Новый пароль",
            "type": "password",
            "help_text": "Обязателен для нового пользователя. У существующего заполните, только чтобы сменить пароль.",
        },
    }
    labels = {
        "phone_number": "Телефон", "first_name": "Имя", "last_name": "Фамилия", "middle_name": "Отчество",
        "email": "Email", "is_active": "Активен", "is_staff": "Доступ в админку",
        "is_superuser": "Суперпользователь", "groups": "Группы", "last_login": "Последний вход",
        "date_joined": "Добавлен",
    }
    prefetch_related = ("groups",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.exclude(is_superuser=True)
        return qs

    @display("ФИО")
    def full_name(self, obj):
        return obj.full_name

    def label_for(self, obj):
        return obj.full_name or str(obj.phone_number)

    def validate(self, request, data, instance):
        errors = {}
        password = data.get("new_password") or ""
        if instance is None and not password:
            errors["new_password"] = ["Задайте пароль."]
        if password:
            try:
                validate_password(password, user=instance)
            except DjangoValidationError as exc:
                errors["new_password"] = list(exc.messages)
        if instance is not None and instance.pk == request.user.pk and data.get("is_active") is False:
            errors["is_active"] = ["Нельзя отключить самого себя."]
        if errors:
            raise serializers.ValidationError(errors)
        return data

    def save_extra(self, request, obj, values, created):
        password = values.get("new_password")
        if password:
            obj.set_password(password)
            obj.save(update_fields=["password"])

    def delete(self, request, obj):
        if obj.pk == request.user.pk:
            raise PermissionDenied("Нельзя удалить самого себя.")
        obj.delete()


@staff_site.register(Group)
class GroupResource(StaffResource):
    key = "group"
    label = "Группа"
    label_plural = "Группы"
    group = "Администрирование"
    icon = "shield"
    order = 85
    hidden = True

    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("name",)
    fields = ("name",)

    def has_perm(self, request, operation):
        return request.user.is_superuser and super().has_perm(request, operation)


ACTION_BADGES = {ADDITION: "success", CHANGE: "info", DELETION: "danger"}


@staff_site.register(LogEntry)
class LogEntryResource(StaffResource):
    """Кто, что и когда менял — и в панели, и в Django admin (общий ``LogEntry``)."""

    key = "logentry"
    label = "Действие"
    label_plural = "Журнал действий"
    group = "Администрирование"
    icon = "scroll-text"
    order = 90

    list_display = ("action_time", "user", "action_flag", "content_type", "object_link", "message")
    list_display_links = ("action_time",)
    list_filter = ("action_flag", "user", "content_type", "action_time")
    search_fields = ("object_repr", "change_message")
    search_help = "Объект или изменение"
    ordering = ("-action_time",)
    list_per_page = 50

    fields = ()
    readonly_fields = ("action_time", "user", "action_flag", "content_type", "object_link", "message")
    labels = {"action_time": "Время", "user": "Кто", "action_flag": "Что", "content_type": "Раздел"}
    select_related = ("user", "content_type")

    can_add = False
    can_change = False
    can_delete = False

    def has_perm(self, request, operation):
        return request.user.is_superuser and super().has_perm(request, operation)

    def describe_field(self, name):
        info = super().describe_field(name)
        if name == "action_flag":
            info["badges"] = {str(value): color for value, color in ACTION_BADGES.items()}
        return info

    @display("Объект", type="link")
    def object_link(self, obj):
        model = obj.content_type.model_class() if obj.content_type_id else None
        target = self.site.resource_for_model(model) if model else None
        if target is None or obj.action_flag == DELETION or not str(obj.object_id).isdigit():
            return {"label": obj.object_repr, "to": None}
        return {"label": obj.object_repr, "resource": target.key, "id": int(obj.object_id)}

    @display("Изменение", type="text")
    def message(self, obj):
        return obj.get_change_message()
