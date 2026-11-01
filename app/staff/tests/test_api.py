from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from account.models import ChargePoint, ChargingSession, ChargingSessionMeterValue, User
from payments.models import QRPayment

BASE = "/api/staff/v1"


class StaffApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(phone_number="+996700000001", password="pass-12345!")
        cls.plain = User.objects.create_user(phone_number="+996700000002", password="pass-12345!")
        cls.station = ChargePoint.objects.create(cp_id="CP-1", name="Станция 1")
        cls.session = ChargingSession.objects.create(
            charge_point=cls.station, transaction_id=7, status="charging", started_at=timezone.now(),
            consumed_kwh=Decimal("4.5"), last_power_kw=Decimal("22"),
        )
        ChargingSessionMeterValue.objects.create(
            session=cls.session, sampled_at=timezone.now(), power_kw=Decimal("21.5"), soc=Decimal("40"),
        )
        QRPayment.objects.create(
            bank_id="b1", charge_point=cls.station, amount=Decimal("100"), status="success", paid_at=timezone.now(),
        )

    def login(self, user):
        self.client.force_login(user)

    def test_anonymous_has_no_access(self):
        self.assertEqual(self.client.get(f"{BASE}/meta/").status_code, 403)

    def test_login_flow(self):
        self.client.get(f"{BASE}/auth/csrf/")
        response = self.client.post(
            f"{BASE}/auth/login/", {"phone_number": "+996700000001", "password": "pass-12345!"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["is_superuser"])

    def test_non_staff_cannot_login(self):
        response = self.client.post(
            f"{BASE}/auth/login/", {"phone_number": "+996700000002", "password": "pass-12345!"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_meta_lists_sections(self):
        self.login(self.admin)
        keys = {resource["key"] for resource in self.client.get(f"{BASE}/meta/").json()["resources"]}
        self.assertTrue({"chargepoint", "chargingsession", "csmsservice", "qrpayment", "user"} <= keys)

    def test_station_list_and_detail(self):
        self.login(self.admin)
        with mock.patch("account.staff.is_cp_connected", return_value=True):
            rows = self.client.get(f"{BASE}/resources/chargepoint/").json()["results"]
            detail = self.client.get(f"{BASE}/resources/chargepoint/{self.station.pk}/").json()
        self.assertEqual(rows[0]["cp_id"], "CP-1")
        self.assertEqual(rows[0]["state"]["value"], "free")
        self.assertIn("start_charging_action", detail["_actions"])
        self.assertEqual(detail["sessions_total"], 1)
        self.assertEqual(detail["revenue_total"], 100.0)
        self.assertEqual(detail["recent_sessions"]["rows"][0]["status"], "Зарядка")

    def test_session_detail_has_telemetry(self):
        self.login(self.admin)
        data = self.client.get(f"{BASE}/resources/chargingsession/{self.session.pk}/").json()
        self.assertEqual(data["power_chart"]["points"][0]["v"], 21.5)
        self.assertEqual(len(data["measurements"]["rows"]), 1)

    def test_sessions_are_read_only(self):
        self.login(self.admin)
        response = self.client.delete(f"{BASE}/resources/chargingsession/{self.session.pk}/")
        self.assertEqual(response.status_code, 403)

    def test_command_when_station_offline(self):
        self.login(self.admin)
        with mock.patch("account.staff.is_cp_connected", return_value=False), \
                mock.patch("account.staff.start_charging") as start:
            response = self.client.post(
                f"{BASE}/resources/chargepoint/{self.station.pk}/actions/start_charging_action/",
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["level"], "warning")
        start.assert_not_called()

    def test_command_when_station_online(self):
        self.login(self.admin)
        with mock.patch("account.staff.is_cp_connected", return_value=True), \
                mock.patch("account.staff.reset_station") as reset:
            response = self.client.post(
                f"{BASE}/resources/chargepoint/{self.station.pk}/actions/soft_reset_action/",
                content_type="application/json",
            )
        self.assertEqual(response.json()["level"], "success")
        reset.assert_called_once_with("CP-1", reset_type="Soft")

    def test_user_without_permissions_sees_nothing(self):
        self.plain.is_staff = True
        self.plain.save()
        self.login(self.plain)
        self.assertEqual(self.client.get(f"{BASE}/meta/").json()["resources"], [])
        self.assertEqual(self.client.get(f"{BASE}/resources/chargepoint/").status_code, 403)

    def test_create_user_sets_password(self):
        self.login(self.admin)
        response = self.client.post(
            f"{BASE}/resources/user/",
            {"phone_number": "+996700000003", "new_password": "Str0ng-pass-77", "is_active": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(User.objects.get(phone_number="+996700000003").check_password("Str0ng-pass-77"))

    def test_dashboard(self):
        self.login(self.admin)
        with mock.patch("staff.dashboard.is_cp_connected", return_value=True):
            data = self.client.get(f"{BASE}/dashboard/").json()
        self.assertEqual(data["summary"]["revenue"], 100.0)
        self.assertEqual(data["summary"]["sessions"], 1)
        self.assertEqual(data["active_sessions"], 1)
        self.assertEqual(data["stations"][0]["power_kw"], 22.0)

    def test_dashboard_rejects_long_period(self):
        self.login(self.admin)
        start = (timezone.localdate() - timedelta(days=400)).isoformat()
        self.assertEqual(self.client.get(f"{BASE}/dashboard/?date_from={start}").status_code, 400)

    def test_nav_badges_count_offline_stations(self):
        self.login(self.admin)
        with mock.patch("staff.dashboard.is_cp_connected", return_value=False):
            badges = self.client.get(f"{BASE}/nav-badges/").json()["badges"]
        self.assertEqual(badges["chargepoint"], 1)
