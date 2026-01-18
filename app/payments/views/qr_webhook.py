import logging
from decimal import Decimal
from pprint import pformat

from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response

from account.models import ChargePoint, ChargingSession
from payments.models import QRPayment

logger = logging.getLogger(__name__)


BANK_TO_LOCAL_STATUS = {
    "SUCCESS": "success",
    "WAITING": "pending",
    "PROCESSING": "pending",
    "CANCELLED": "failed",
    "ERROR": "failed",
}


class QRPaymentWebhookView(APIView):

    def post(self, request, *args, **kwargs):
        data = request.data

        logger.info("===== NEW QR WEBHOOK =====")
        logger.info("DATA:\n%s", pformat(data))
        logger.info("REMOTE_ADDR: %s", request.META.get("REMOTE_ADDR"))

        status = data.get("status")
        amount = data.get("amount")
        bank_id = data.get("id")
        merchant_service_id = str(data.get("qr_merchant_service", ""))

        # Валидация
        if not all([status, amount, bank_id, merchant_service_id]):
            logger.warning("Webhook: недостаточно данных")
            return Response({"error": "Недостаточно данных"}, status=400)

        if not merchant_service_id.startswith("111") or len(merchant_service_id) != 15:
            logger.error("Webhook: некорректный merchant_service_id=%s", merchant_service_id)
            return Response({"error": "Некорректный merchant_service_id"}, status=200)

        # Парсим charge_point_id
        try:
            charge_point_id = int(merchant_service_id[3:])
        except ValueError:
            logger.exception("Webhook: ошибка парсинга charge_point_id")
            return Response({"error": "Некорректный ID станции"}, status=200)

        # ChargePoint
        try:
            charge_point = ChargePoint.objects.get(pk=charge_point_id)
        except ChargePoint.DoesNotExist:
            logger.error("Webhook: ChargePoint не найден id=%s", charge_point_id)
            return Response({"error": "ChargePoint не найден"}, status=200)

        local_status = BANK_TO_LOCAL_STATUS.get(str(status).upper(), "failed")

        # Сохраняем платеж и создаем сессию
        with transaction.atomic():
            payment, created = QRPayment.objects.select_for_update().get_or_create(
                bank_id=bank_id,
                defaults={
                    "charge_point": charge_point,
                    "amount": amount,
                    "status": local_status,
                    "webhook_payload": data,
                },
            )

            if not created:
                payment.status = local_status
                payment.webhook_payload = data

            if local_status == "success" and not payment.paid_at:
                payment.paid_at = timezone.now()

                # Создаем сессию зарядки
                session = ChargingSession.objects.create(
                    charge_point=charge_point,
                    status='preparing',
                    initial_balance=Decimal(amount),
                    cost_per_kwh=Decimal('12.00'),
                )

                payment.charging_session = session

                # Помечаем станцию как занятую
                charge_point.is_occupied = True
                charge_point.save()

                logger.info(
                    f"[CHARGING SESSION CREATED] Session {session.id} | "
                    f"Balance: {session.initial_balance} som"
                )

            payment.save()

        logger.info(
            "QR payment processed | bank_id=%s | status=%s | charge_point_id=%s",
            bank_id,
            local_status,
            charge_point_id,
        )

        return Response({"success": True}, status=200)
