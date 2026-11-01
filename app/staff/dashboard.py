"""Сводка для главной страницы: выручка, сессии и энергия по дням, состояние станций."""

import logging
from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDay
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import ChargePoint, ChargingSession
from account.services.ocpp_commands import is_cp_connected
from payments.models import QRPayment
from staff.api import StaffAPIMixin
from staff.site import staff_site

logger = logging.getLogger(__name__)

MAX_RANGE_DAYS = 366
ACTIVE_STATUSES = ("preparing", "charging")


class SummarySerializer(serializers.Serializer):
    revenue = serializers.FloatField(help_text="Оплаченные QR-платежи за период, сом")
    payments = serializers.IntegerField()
    sessions = serializers.IntegerField()
    kwh = serializers.FloatField()
    previous_revenue = serializers.FloatField()
    previous_payments = serializers.IntegerField()
    previous_sessions = serializers.IntegerField()
    previous_kwh = serializers.FloatField()


class DayPointSerializer(serializers.Serializer):
    date = serializers.DateField()
    revenue = serializers.FloatField()
    sessions = serializers.IntegerField()
    kwh = serializers.FloatField()


class StationStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    cp_id = serializers.CharField()
    name = serializers.CharField()
    online = serializers.BooleanField(allow_null=True, help_text="null — связь проверить не удалось")
    charging = serializers.BooleanField()
    session_id = serializers.IntegerField(allow_null=True)
    power_kw = serializers.FloatField(allow_null=True)
    soc = serializers.FloatField(allow_null=True)
    sessions_today = serializers.IntegerField()


class DashboardSerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    summary = SummarySerializer()
    days = DayPointSerializer(many=True)
    stations = StationStatusSerializer(many=True)
    active_sessions = serializers.IntegerField(help_text="Сессий в статусах «Подготовка» и «Зарядка» сейчас")


class DashboardView(StaffAPIMixin, APIView):
    @extend_schema(
        operation_id="staff_dashboard",
        parameters=[
            OpenApiParameter("date_from", str, description="YYYY-MM-DD, по умолчанию — начало месяца"),
            OpenApiParameter("date_to", str, description="YYYY-MM-DD, по умолчанию — сегодня"),
        ],
        responses=DashboardSerializer,
    )
    def get(self, request):
        sessions_resource = staff_site.resource_for_model(ChargingSession)
        stations_resource = staff_site.resource_for_model(ChargePoint)
        if not sessions_resource.has_perm(request, "view"):
            raise PermissionDenied("Нет доступа к сессиям зарядки.")
        date_from, date_to = _period(request)
        length = (date_to - date_from).days + 1
        prev_from, prev_to = date_from - timedelta(days=length), date_from - timedelta(days=1)

        sessions = sessions_resource.get_queryset(request)
        started = sessions.exclude(started_at__isnull=True)
        payments = _paid_payments(request)

        days = _days(started, payments, date_from, date_to)
        before_sessions = started.filter(started_at__date__range=(prev_from, prev_to)).aggregate(
            count=Count("id"), kwh=Sum("consumed_kwh"),
        )
        before_payments = payments.filter(paid_at__date__range=(prev_from, prev_to)).aggregate(
            count=Count("id"), amount=Sum("amount"),
        )

        return Response({
            "date_from": date_from,
            "date_to": date_to,
            "summary": {
                "revenue": round(sum(day["revenue"] for day in days), 2),
                "payments": payments.filter(paid_at__date__range=(date_from, date_to)).count(),
                "sessions": sum(day["sessions"] for day in days),
                "kwh": round(sum(day["kwh"] for day in days), 3),
                "previous_revenue": float(before_payments["amount"] or 0),
                "previous_payments": before_payments["count"] or 0,
                "previous_sessions": before_sessions["count"] or 0,
                "previous_kwh": float(before_sessions["kwh"] or 0),
            },
            "days": days,
            "stations": _stations(stations_resource.get_queryset(request), sessions) if stations_resource else [],
            "active_sessions": sessions.filter(status__in=ACTIVE_STATUSES).count(),
        })


def _paid_payments(request):
    resource = staff_site.resource_for_model(QRPayment)
    if resource is None or not resource.has_perm(request, "view"):
        return QRPayment.objects.none()
    return resource.get_queryset(request).filter(status="success", paid_at__isnull=False)


def _period(request):
    today = timezone.localdate()
    try:
        date_from = _parse(request.query_params.get("date_from")) or today.replace(day=1)
        date_to = _parse(request.query_params.get("date_to")) or today
    except ValueError:
        raise ValidationError({"detail": "Дата в формате ГГГГ-ММ-ДД."})
    if date_from > date_to:
        raise ValidationError({"detail": "Начало периода позже конца."})
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise ValidationError({"detail": "Период не длиннее года."})
    return date_from, date_to


def _parse(value):
    if not value:
        return None
    return timezone.datetime.strptime(value, "%Y-%m-%d").date()


def _by_day(qs, field, **aggregates):
    rows = qs.annotate(day=TruncDay(field)).values("day").annotate(**aggregates)
    return {row["day"].date() if hasattr(row["day"], "date") else row["day"]: row for row in rows}


def _days(started, payments, date_from, date_to):
    in_period = started.filter(started_at__date__range=(date_from, date_to))
    sessions = _by_day(in_period, "started_at", sessions=Count("id"), kwh=Sum("consumed_kwh"))
    money = _by_day(
        payments.filter(paid_at__date__range=(date_from, date_to)), "paid_at", revenue=Sum("amount"),
    )
    result = []
    day = date_from
    while day <= date_to:
        result.append({
            "date": day,
            "revenue": float(money.get(day, {}).get("revenue") or 0),
            "sessions": sessions.get(day, {}).get("sessions", 0),
            "kwh": float(sessions.get(day, {}).get("kwh") or 0),
        })
        day += timedelta(days=1)
    return result


def _online(cp_id):
    try:
        return is_cp_connected(cp_id)
    except Exception:
        logger.exception("Не удалось проверить связь со станцией %s", cp_id)
        return None


def _stations(stations, sessions):
    today = timezone.localdate()
    active = {}
    for session in sessions.filter(status__in=ACTIVE_STATUSES).order_by("created_at"):
        active[session.charge_point_id] = session
    counts = dict(
        sessions.filter(started_at__date=today).order_by().values_list("charge_point").annotate(n=Count("id")),
    )
    result = []
    for station in stations.order_by("name"):
        session = active.get(station.pk)
        result.append({
            "id": station.pk,
            "cp_id": station.cp_id,
            "name": station.name,
            "online": _online(station.cp_id),
            "charging": session is not None and session.status == "charging",
            "session_id": session.pk if session else None,
            "power_kw": float(session.last_power_kw) if session and session.last_power_kw is not None else None,
            "soc": float(session.last_soc) if session and session.last_soc is not None else None,
            "sessions_today": counts.get(station.pk, 0),
        })
    return result


class NavBadgesSerializer(serializers.Serializer):
    badges = serializers.DictField(
        child=serializers.IntegerField(),
        help_text="Раздел → число проблем: chargepoint (станции без связи), chargingsession (ошибки за сутки)",
    )


class NavBadgesView(StaffAPIMixin, APIView):
    """Счётчики проблем для меню: дешевле дашборда, меню спрашивает их раз в минуту."""

    @extend_schema(operation_id="staff_nav_badges", responses=NavBadgesSerializer)
    def get(self, request):
        badges = {}
        stations = staff_site.resource_for_model(ChargePoint)
        if stations is not None and stations.has_perm(request, "view"):
            badges["chargepoint"] = sum(
                1 for cp_id in stations.get_queryset(request).values_list("cp_id", flat=True)
                if _online(cp_id) is False
            )
        sessions = staff_site.resource_for_model(ChargingSession)
        if sessions is not None and sessions.has_perm(request, "view"):
            since = timezone.now() - timedelta(days=1)
            badges["chargingsession"] = sessions.get_queryset(request).filter(
                status="error", created_at__gte=since,
            ).count()
        return Response({"badges": {key: count for key, count in badges.items() if count}})
