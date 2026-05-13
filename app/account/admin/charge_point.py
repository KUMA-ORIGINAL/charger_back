import logging
from io import BytesIO

import qrcode
from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from unfold.admin import TabularInline

from unfold.decorators import action

from ..models import ChargePoint, ChargePointCSMS
from common.base_admin import BaseModelAdmin

from ..services.ocpp_commands import (
    start_charging,
    stop_charging,
    trigger_status,
    change_availability,
    reset_station,
    clear_charging_profile,
    get_configuration,
    trigger_boot_notification,
    trigger_meter_values,
)
from ..services.payment_qr_generator import build_payment_qr_link_without_amount


logger = logging.getLogger(__name__)


class ChargePointCSMSInline(TabularInline):
    model = ChargePointCSMS
    extra = 1


@admin.register(ChargePoint)
class ChargePointAdmin(BaseModelAdmin):
    list_display = ("cp_id", "name", 'is_occupied', 'detail_link')
    readonly_fields = ("created_at", "updated_at",)

    inlines = [ChargePointCSMSInline]

    actions_detail = (
        'download_qrcode',
        'start_charging_action',
        'stop_charging_action',
        'trigger_status_action',
        'make_operative_action',
        'make_inoperative_action',
        'soft_reset_action',
        'hard_reset_action',
        'clear_charging_profile_action',
        'get_configuration_action',
        'trigger_boot_action',
        'trigger_meter_values_action',
    )

    @action(
        description="Скачать QR-код для оплаты",
        url_path="download-qrcode",
    )
    def download_qrcode(self, request, object_id: int):
        charge_point = get_object_or_404(ChargePoint, pk=object_id)

        box_value = f"111{charge_point.pk:012d}"

        try:
            qr_link = build_payment_qr_link_without_amount(
                account_number="1240040002323627",
                box_name=f"BAKAIGULBOX.{box_value}",
                client_name="Rouming Charge",
                door=f"Станция ID: {charge_point.pk}",
            )

            charge_point.payment_qr_link = qr_link
            charge_point.save(update_fields=["payment_qr_link"])

            logger.info(
                "QR-код успешно сгенерирован для ChargePoint id=%s",
                charge_point.pk,
            )

        except Exception as e:
            logger.exception(
                "Ошибка генерации QR-кода для ChargePoint id=%s",
                charge_point.pk,
            )
            self.message_user(
                request,
                f"Ошибка генерации QR-кода: {e}",
                level=messages.ERROR,
            )
            change_url = reverse(
                "admin:account_chargepoint_change",
                args=[object_id],
            )
            return redirect(change_url)

        # --- Генерация PNG ---
        qr_image = qrcode.make(charge_point.payment_qr_link)

        buffer = BytesIO()
        qr_image.save(buffer, format="PNG")
        buffer.seek(0)

        filename = f"charge_point_{charge_point.pk}_qrcode.png"

        response = HttpResponse(buffer, content_type="image/png")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        self.message_user(
            request,
            "QR-код успешно сгенерирован и скачан",
            level=messages.SUCCESS,
        )

        logger.info(
            "QR-код для ChargePoint id=%s отправлен администратору",
            charge_point.pk,
        )

        return response

    @action(
        description="▶ Начать зарядку",
        url_path="start-charging",
    )
    def start_charging_action(
        self,
        request,
        object_id,
    ):
        """
        Action на странице объекта
        """
        cp = ChargePoint.objects.get(pk=object_id)

        start_charging(cp.cp_id)

        return redirect(
            reverse_lazy("admin:account_chargepoint_change", args=(object_id,))
        )

    @action(
        description="⛔ Остановить зарядку",
        url_path="stop-charging",
    )
    def stop_charging_action(
            self,
            request,
            object_id,
    ):
        cp = ChargePoint.objects.get(pk=object_id)

        if not cp.active_transaction_id:
            messages.warning(
                request,
                "Нет активной транзакции — остановка невозможна"
            )
            return redirect(
                reverse_lazy("admin:account_chargepoint_change", args=(object_id,))
            )

        stop_charging(
            cp.cp_id,
            transaction_id=cp.active_transaction_id,
        )
        return redirect(
            reverse_lazy("admin:account_chargepoint_change", args=(object_id,))
        )

    @action(description="📡 Запросить статус (коннекторы 0 и 1)", url_path="trigger-status")
    def trigger_status_action(self, request, object_id):
        cp = ChargePoint.objects.get(pk=object_id)
        trigger_status(cp.cp_id, connector_id=0)
        trigger_status(cp.cp_id, connector_id=1)
        messages.success(request, f"TriggerMessage StatusNotification отправлен на {cp.cp_id}")
        return redirect(reverse_lazy("admin:account_chargepoint_change", args=(object_id,)))

    @action(description="✅ Включить станцию (доступна)", url_path="make-operative")
    def make_operative_action(self, request, object_id):
        cp = ChargePoint.objects.get(pk=object_id)
        change_availability(cp.cp_id, connector_id=0, availability_type="Operative")
        change_availability(cp.cp_id, connector_id=1, availability_type="Operative")
        messages.success(request, f"ChangeAvailability Operative отправлен на {cp.cp_id}")
        return redirect(reverse_lazy("admin:account_chargepoint_change", args=(object_id,)))

    @action(description="🔴 Отключить станцию (недоступна)", url_path="make-inoperative")
    def make_inoperative_action(self, request, object_id):
        cp = ChargePoint.objects.get(pk=object_id)
        change_availability(cp.cp_id, connector_id=0, availability_type="Inoperative")
        change_availability(cp.cp_id, connector_id=1, availability_type="Inoperative")
        messages.success(request, f"ChangeAvailability Inoperative отправлен на {cp.cp_id}")
        return redirect(reverse_lazy("admin:account_chargepoint_change", args=(object_id,)))

    @action(description="🔄 Мягкая перезагрузка", url_path="soft-reset")
    def soft_reset_action(self, request, object_id):
        cp = ChargePoint.objects.get(pk=object_id)
        reset_station(cp.cp_id, reset_type="Soft")
        messages.success(request, f"Soft Reset отправлен на {cp.cp_id}")
        return redirect(reverse_lazy("admin:account_chargepoint_change", args=(object_id,)))

    @action(description="⚡ Жёсткая перезагрузка", url_path="hard-reset")
    def hard_reset_action(self, request, object_id):
        cp = ChargePoint.objects.get(pk=object_id)
        reset_station(cp.cp_id, reset_type="Hard")
        messages.success(request, f"Hard Reset отправлен на {cp.cp_id}")
        return redirect(reverse_lazy("admin:account_chargepoint_change", args=(object_id,)))

    @action(description="🧹 Очистить профиль зарядки", url_path="clear-charging-profile")
    def clear_charging_profile_action(self, request, object_id):
        cp = ChargePoint.objects.get(pk=object_id)
        clear_charging_profile(cp.cp_id)
        messages.success(request, f"ClearChargingProfile отправлен на {cp.cp_id}")
        return redirect(reverse_lazy("admin:account_chargepoint_change", args=(object_id,)))

    @action(description="⚙️ Получить конфигурацию", url_path="get-configuration")
    def get_configuration_action(self, request, object_id):
        cp = ChargePoint.objects.get(pk=object_id)
        get_configuration(cp.cp_id)
        messages.success(request, f"GetConfiguration отправлен на {cp.cp_id}")
        return redirect(reverse_lazy("admin:account_chargepoint_change", args=(object_id,)))

    @action(description="🔁 Запросить BootNotification", url_path="trigger-boot")
    def trigger_boot_action(self, request, object_id):
        cp = ChargePoint.objects.get(pk=object_id)
        trigger_boot_notification(cp.cp_id)
        messages.success(request, f"TriggerMessage BootNotification отправлен на {cp.cp_id}")
        return redirect(reverse_lazy("admin:account_chargepoint_change", args=(object_id,)))

    @action(description="📊 Запросить показания счётчика", url_path="trigger-meter-values")
    def trigger_meter_values_action(self, request, object_id):
        cp = ChargePoint.objects.get(pk=object_id)
        trigger_meter_values(cp.cp_id, connector_id=1)
        messages.success(request, f"TriggerMessage MeterValues отправлен на {cp.cp_id}")
        return redirect(reverse_lazy("admin:account_chargepoint_change", args=(object_id,)))
