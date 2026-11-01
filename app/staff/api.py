"""Общие настройки всех view React-админки."""

from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.renderers import JSONRenderer

from .permissions import IsStaffMember


class StaffAPIMixin:
    """Сессия Django вместо JWT и snake_case вместо camelCase.

    Админка открывается с того же домена, поэтому сессионная кука (httpOnly) +
    CSRF надёжнее токена в браузере. Имена полей в ответах совпадают с именами
    полей модели — по ним фронт сопоставляет данные с описанием из ``/meta/``.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsStaffMember]
    renderer_classes = [JSONRenderer]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
