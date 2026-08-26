from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from account.models import (
    ChargePoint,
    ChargingSession,
    ChargingSessionMeterValue,
)


class ChargingSessionAdminSmokeTests(TestCase):
    """Страницы админки сессий открываются и показывают агрегаты."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            phone_number="+996700000001",
            password="admin-pass-123",
        )
        cls.cp = ChargePoint.objects.create(cp_id="777", name="Admin CP")

        started = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        cls.external = ChargingSession.objects.create(
            charge_point=cls.cp,
            source=ChargingSession.SOURCE_CSMS,
            csms_name="Charge24",
            status="completed",
            transaction_id=555001,
            csms_transaction_id=3331160,
            id_tag="TAG-A",
            started_at=started,
            stopped_at=started + timedelta(hours=1, minutes=5, seconds=30),
            start_meter_value=Decimal("1000"),
            last_meter_value=Decimal("7000"),
            stop_meter_value=Decimal("7000"),
            consumed_kwh=Decimal("6"),
            cost_per_kwh=Decimal("0"),
            start_soc=Decimal("41"),
            last_soc=Decimal("55"),
            last_power_kw=Decimal("11"),
            max_power_kw=Decimal("22"),
            stop_reason="Local",
        )
        ChargingSessionMeterValue.objects.create(
            session=cls.external,
            sampled_at=started + timedelta(minutes=10),
            energy_wh=Decimal("3000"),
            consumed_kwh=Decimal("2"),
            power_kw=Decimal("22"),
            soc=Decimal("41"),
        )
        cls.payment = ChargingSession.objects.create(
            charge_point=cls.cp,
            source=ChargingSession.SOURCE_PAYMENT,
            status="completed",
            initial_balance=Decimal("500"),
            cost_per_kwh=Decimal("12"),
            consumed_kwh=Decimal("3"),
            total_cost=Decimal("36"),
            started_at=started,
            stopped_at=started + timedelta(minutes=30),
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_changelist_renders_both_sources(self):
        response = self.client.get(
            reverse("admin:account_chargingsession_changelist")
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Charge24", content)
        self.assertIn("QR оплата", content)
        self.assertIn("1:05:30", content)          # длительность внешней сессии
        self.assertIn("41.0% → 55.0%", content)    # прирост заряда

    def test_change_page_renders_with_meter_values_inline(self):
        response = self.client.get(
            reverse(
                "admin:account_chargingsession_change", args=[self.external.id]
            )
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("История замеров", content)
        self.assertIn("3331160", content)

    def test_source_filter_narrows_list(self):
        response = self.client.get(
            reverse("admin:account_chargingsession_changelist"),
            {"source__exact": ChargingSession.SOURCE_CSMS},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [s.id for s in response.context["cl"].result_list],
            [self.external.id],
        )
