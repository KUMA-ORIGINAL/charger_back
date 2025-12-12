import logging
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from account import serializers
from insurance.services import send_telegram_message
from ..models import PhoneVerification, User
from ..services import send_sms, handle_referral

logger = logging.getLogger(__name__)


class SendSMSCodeView(APIView):
    serializer_class = serializers.PhoneNumberSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data.get("phone_number")

        try:
            last_otp = PhoneVerification.objects.filter(
                phone_number=phone_number
            ).order_by('-created_at').first()

            now = timezone.now()
            if last_otp and last_otp.created_at > now - timedelta(seconds=60):
                seconds_passed = (now - last_otp.created_at).total_seconds()
                seconds_left = int(60 - seconds_passed)
                return Response(
                    {
                        "error": "Код уже был отправлен недавно. Подождите минуту.",
                        "seconds_left": max(0, seconds_left)
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )

            with transaction.atomic():
                # Очищаем старые коды
                PhoneVerification.objects.filter(
                    phone_number=phone_number,
                    created_at__lt=timezone.now() - timedelta(hours=1)
                ).delete()

                code = f"{secrets.randbelow(1000000):06d}"
                otp = PhoneVerification.objects.create(
                    phone_number=phone_number,
                    code=code
                )
                logger.info(f"Created new verification code with ID {otp.id} for phone {phone_number}")

                text = f"Код подтверждения: {code}. Никому не сообщайте его."
                if not send_sms(phone=phone_number, text=text):
                    return Response(
                        {"error": "Не удалось отправить SMS"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                logger.info(f"SMS successfully sent to phone {phone_number}, verification ID {otp.id}")

            return Response(
                {"message": "Код подтверждения отправлен"},
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error(f"Unexpected error while sending SMS to {phone_number}: {str(e)}", exc_info=True)
            return Response(
                {"error": "Внутренняя ошибка сервера"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifySMSCodeView(APIView):
    serializer_class = serializers.VerifyCodeSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        phone_number = serializer.validated_data.get("phone_number")
        code = serializer.validated_data.get("code")
        referral_code = serializer.validated_data.get("referral_code", None)

        try:
            with transaction.atomic():
                obj = PhoneVerification.objects.select_for_update().get(
                    phone_number=phone_number,
                    code=code,
                    is_verified=False
                )

                if timezone.now() - obj.created_at > timedelta(minutes=5):
                    return Response({"error": "Код просрочен"}, status=400)

                obj.is_verified = True
                obj.save()
                logger.info(f"SMS code verified successfully for phone {phone_number}, verification ID {obj.id}")

                user, created = User.objects.get_or_create(phone_number=phone_number)

                if created and referral_code:
                    try:
                        handle_referral(user, referral_code)
                    except ValueError as e:
                        return Response({"error": str(e)}, status=400)

                    try:
                        telegram_text = (
                            f"🧾 <b>Создан новый агент</b>\n\n"
                            f"👤 Телефон: {user.phone_number}\n"
                            f"🆔 ID: <code>{user.id}</code>\n"
                            f"🕒 Время: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        if referral_code:
                            telegram_text += f"\n👥 Реферал-код: {referral_code}"

                        send_telegram_message(telegram_text)
                    except Exception as e:
                        logger.error("[TELEGRAM][SEND_ERROR]: %s", e, exc_info=True)

        except PhoneVerification.DoesNotExist:
            return Response({"error": "Неверный код"}, status=400)

        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        })
