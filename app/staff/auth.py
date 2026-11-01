"""Вход в React-админку той же сессией Django, что и в /admin/.

Перебор пароля ограничен по номеру: после ``LOGIN_FAILURE_LIMIT`` ошибок номер
блокируется на ``LOGIN_LOCKOUT`` секунд. django-axes здесь не помогает: он
настроен только на /admin/ (``AXES_ONLY_ADMIN_SITE``).
"""

from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from phonenumber_field.phonenumber import to_python
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .api import StaffAPIMixin

LOGIN_FAILURE_LIMIT = 5
LOGIN_LOCKOUT = 15 * 60


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    phone_number = serializers.CharField()
    full_name = serializers.CharField()
    role = serializers.CharField(allow_blank=True)
    role_label = serializers.CharField()
    is_superuser = serializers.BooleanField()


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


def me_payload(user):
    return {
        "id": user.pk,
        "phone_number": str(user.phone_number),
        "full_name": user.full_name or str(user.phone_number),
        "role": "",
        "role_label": "Суперпользователь" if user.is_superuser else "Сотрудник",
        "is_superuser": user.is_superuser,
    }


def _lock_key(phone):
    return f"staff-login-failures:{phone}"


class CsrfView(StaffAPIMixin, APIView):
    """Ставит куку csrftoken — фронт вызывает перед входом."""

    permission_classes = [AllowAny]

    @extend_schema(responses=DetailSerializer, operation_id="staff_csrf")
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({"detail": "ok"})


class LoginView(StaffAPIMixin, APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer, responses={200: MeSerializer, 400: DetailSerializer},
                   operation_id="staff_login")
    @method_decorator(csrf_protect)
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_phone = serializer.validated_data["phone_number"]
        phone = to_python(raw_phone)
        phone = phone.as_e164 if phone and phone.is_valid() else raw_phone.strip()

        # Считаем попытку до проверки пароля и атомарно (add + incr): иначе
        # параллельные запросы читали бы один и тот же счётчик и обходили лимит.
        key = _lock_key(phone)
        cache.add(key, 0, LOGIN_LOCKOUT)
        if cache.incr(key) > LOGIN_FAILURE_LIMIT:
            return Response(
                {"detail": "Слишком много попыток. Попробуйте через 15 минут."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        user = authenticate(request._request, username=phone, password=serializer.validated_data["password"])
        if user is None or not user.is_staff:
            return Response({"detail": "Неверный номер или пароль."}, status=status.HTTP_400_BAD_REQUEST)

        cache.delete(key)
        login(request._request, user)
        return Response(me_payload(user))


class LogoutView(StaffAPIMixin, APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses=DetailSerializer, operation_id="staff_logout")
    def post(self, request):
        logout(request._request)
        return Response({"detail": "ok"})


class MeView(StaffAPIMixin, APIView):
    @extend_schema(responses=MeSerializer, operation_id="staff_me")
    def get(self, request):
        return Response(me_payload(request.user))
