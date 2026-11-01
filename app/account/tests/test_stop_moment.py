from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from account.consumers import OCPPConsumer


class StopMomentTests(SimpleTestCase):
    def setUp(self):
        self.started = datetime.now(timezone.utc) - timedelta(minutes=20)

    def test_uses_station_timestamp(self):
        moment = (datetime.now(timezone.utc) - timedelta(minutes=5)).replace(microsecond=0)
        iso = moment.isoformat().replace("+00:00", "Z")
        self.assertEqual(OCPPConsumer._stop_moment(iso, self.started), moment)

    def test_missing_or_broken_timestamp_falls_back_to_now(self):
        for value in (None, "", "не дата"):
            result = OCPPConsumer._stop_moment(value, self.started)
            self.assertLess((datetime.now(timezone.utc) - result).total_seconds(), 5)

    def test_timestamp_outside_session_is_ignored(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
        before_start = (self.started - timedelta(hours=1)).isoformat()
        for value in (future, before_start):
            result = OCPPConsumer._stop_moment(value, self.started)
            self.assertLess((datetime.now(timezone.utc) - result).total_seconds(), 5)
