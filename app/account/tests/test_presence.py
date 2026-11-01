from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from account.services.ocpp_commands import is_cp_connected, mark_cp_offline, mark_cp_online

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM)
class PresenceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_unknown_station_is_offline(self):
        self.assertFalse(is_cp_connected("301"))

    def test_online_after_activity_and_offline_after_disconnect(self):
        mark_cp_online("301", "chan-1")
        self.assertTrue(is_cp_connected("301"))
        mark_cp_offline("301", "chan-1")
        self.assertFalse(is_cp_connected("301"))

    def test_old_connection_closing_does_not_drop_the_new_one(self):
        mark_cp_online("301", "old")
        mark_cp_online("301", "new")  # станция уже переподключилась
        mark_cp_offline("301", "old")
        self.assertTrue(is_cp_connected("301"))

    def test_other_station_is_not_affected(self):
        mark_cp_online("301", "chan-1")
        self.assertFalse(is_cp_connected("302"))
