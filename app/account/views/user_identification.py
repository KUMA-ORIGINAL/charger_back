import logging

from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from insurance.services import send_telegram_message
from ..serializers import UserIdentificationSerializer

logger = logging.getLogger(__name__)


class IdentificationSubmitView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserIdentificationSerializer

    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = self.serializer_class(
            user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        try:
            telegram_text = (
                f"📤 <b>Поступила новая заявка на идентификацию</b>\n\n"
                f"👤 Пользователь: {user.phone_number}\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"🕒 Время: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_telegram_message(telegram_text)
        except Exception as e:
            logger.error("[TELEGRAM][IDENTIFICATION_SEND_ERROR]: %s", e, exc_info=True)

        return Response({'detail': 'Заявка на идентификацию отправлена!'}, status=status.HTTP_200_OK)
