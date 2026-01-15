import logging
from io import BytesIO

import qrcode
from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy, reverse

from unfold.decorators import action

from ..models import ChargePoint
from common.base_admin import BaseModelAdmin

from ..services.ocpp_commands import start_charging, stop_charging
from ..services.payment_qr_generator import build_payment_qr_link_without_amount


logger = logging.getLogger(__name__)


@admin.register(ChargePoint)
class ChargePointAdmin(BaseModelAdmin):
    list_display = ("cp_id", "name", 'detail_link')
    readonly_fields = ("created_at", "updated_at",)

    actions_detail = ('start_charging_action', 'stop_charging_action', 'download_qrcode')

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
        description="▶ Start charging",
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
        description="⛔ Stop charging",
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
