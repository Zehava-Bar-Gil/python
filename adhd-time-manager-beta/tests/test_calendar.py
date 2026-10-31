"""Google Calendar: OAuth עם state, סנכרון בלי כפילויות, חידוש אסימון, ניתוק, והמרת אירוע למשימה.

הרשת מוחלפת בפונקציה מדומה (google_calendar.http_request), ולכן אין פנייה ל-Google.
"""
from datetime import timedelta
from unittest import mock
from urllib.parse import parse_qs, urlparse

from timeflow import clock, google_calendar

from .helpers import TimeFlowTestCase

GOOGLE = {"GOOGLE_CLIENT_ID": "client-id.apps.googleusercontent.com", "GOOGLE_CLIENT_SECRET": "very-secret"}


class FakeGoogle:
    def __init__(self):
        self.events = [
            {"id": "e1", "summary": "פגישה עם המנחה", "start": {"dateTime": "2026-10-29T14:00:00+02:00"},
             "end": {"dateTime": "2026-10-29T15:00:00+02:00"}},
            {"id": "e2", "summary": "יום הולדת", "start": {"date": "2026-10-30"}, "end": {"date": "2026-10-31"}},
            {"id": "e3", "status": "cancelled", "summary": "בוטל", "start": {"date": "2026-10-30"}},
        ]
        self.events_status = 200
        self.refresh_ok = True
        self.calls = []

    def __call__(self, method, url, data=None, headers=None):
        self.calls.append((method, url.split("?")[0], data))
        if url == google_calendar.TOKEN_URL and data["grant_type"] == "authorization_code":
            return 200, {"access_token": "access-1", "refresh_token": "refresh-1", "expires_in": 3600,
                         "scope": google_calendar.SCOPE}
        if url == google_calendar.TOKEN_URL:
            if not self.refresh_ok:
                return 400, {"error": "invalid_grant"}
            return 200, {"access_token": "access-2", "expires_in": 3600, "scope": google_calendar.SCOPE}
        if url == google_calendar.REVOKE_URL:
            return 200, {}
        if url.startswith(google_calendar.EVENTS_URL):
            return self.events_status, {"items": self.events} if self.events_status == 200 else {}
        raise AssertionError(url)


class CalendarTests(TimeFlowTestCase):
    app_overrides = GOOGLE

    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()
        self.google = FakeGoogle()
        patcher = mock.patch.object(google_calendar, "http_request", self.google)
        patcher.start()
        self.addCleanup(patcher.stop)

    def connect(self):
        self.post(self.client_, "/zehava/calendar/connect", {"consent": "1"})
        with self.client_.session_transaction() as session:
            state = session["google_oauth_state"]
        return self.client_.get(f"/zehava/calendar/oauth/callback?state={state}&code=abc")

    def events(self):
        return self.repo().calendar_events_between(self.user, "0000", "9999")

    def test_consent_page_then_redirect_to_google(self):
        self.assertEqual(self.client_.get("/zehava/calendar/connect").status_code, 200)
        response = self.post(self.client_, "/zehava/calendar/connect", {})
        self.assertTrue(response.headers["Location"].endswith("/zehava/calendar/connect"))
        response = self.post(self.client_, "/zehava/calendar/connect", {"consent": "1"})
        url = urlparse(response.headers["Location"])
        params = parse_qs(url.query)
        self.assertEqual(url.netloc, "accounts.google.com")
        self.assertEqual(params["scope"], [google_calendar.SCOPE])
        self.assertEqual(params["redirect_uri"], ["http://localhost/zehava/calendar/oauth/callback"])
        self.assertTrue(params["state"][0])
        self.assertNotIn("very-secret", response.headers["Location"])

    def test_wrong_state_is_rejected(self):
        self.post(self.client_, "/zehava/calendar/connect", {"consent": "1"})
        self.client_.get("/zehava/calendar/oauth/callback?state=forged&code=abc")
        self.assertIsNone(self.repo().get_google_account(self.user))
        # גם בלי שהתחיל חיבור בכלל
        self.client_.get("/zehava/calendar/oauth/callback?state=&code=abc")
        self.assertIsNone(self.repo().get_google_account(self.user))

    def test_connect_syncs_events(self):
        self.connect()
        self.assertEqual(self.repo().get_google_account(self.user)["refresh_token"], "refresh-1")
        summaries = sorted(e["summary"] for e in self.events())
        self.assertEqual(summaries, ["יום הולדת", "פגישה עם המנחה"])
        html = self.html(self.client_.get("/zehava/calendar?day=2026-10-29"))
        self.assertIn("פגישה עם המנחה", html)
        self.assertNotIn("access-1", html)
        self.assertEqual(google_calendar.status(self.repo(), self.app.config, self.user)["state"], "synced")
        self.assertIn("פגישה עם המנחה", self.html(self.client_.get("/zehava")))

    def test_sync_again_has_no_duplicates_and_removes_deleted(self):
        self.connect()
        self.post(self.client_, "/zehava/calendar/sync")
        self.assertEqual(len(self.events()), 2)
        self.google.events = self.google.events[:1]
        self.google.events[0]["summary"] = "פגישה (עודכן)"
        self.post(self.client_, "/zehava/calendar/sync")
        self.assertEqual([e["summary"] for e in self.events()], ["פגישה (עודכן)"])

    def test_revoked_access_shows_reconnect(self):
        self.connect()
        self.google.events_status = 401
        self.post(self.client_, "/zehava/calendar/sync")
        self.assertEqual(google_calendar.status(self.repo(), self.app.config, self.user)["state"], "needs_reconnect")
        self.assertEqual(len(self.events()), 2)    # מה שכבר סונכרן נשאר

    def test_expired_token_is_refreshed(self):
        self.connect()
        self.freeze(clock.now() + timedelta(hours=2))
        self.post(self.client_, "/zehava/calendar/sync")
        self.assertEqual(self.repo().get_google_account(self.user)["access_token"], "access-2")
        self.assertEqual(self.repo().get_google_account(self.user)["refresh_token"], "refresh-1")
        self.google.refresh_ok = False
        self.freeze(clock.now() + timedelta(hours=2))
        self.post(self.client_, "/zehava/calendar/sync")
        self.assertEqual(google_calendar.status(self.repo(), self.app.config, self.user)["state"], "needs_reconnect")

    def test_disconnect_revokes_and_deletes(self):
        self.connect()
        self.post(self.client_, "/zehava/calendar/disconnect")
        self.assertIn(("POST", google_calendar.REVOKE_URL, {"token": "refresh-1"}), self.google.calls)
        self.assertIsNone(self.repo().get_google_account(self.user))
        self.assertEqual(self.events(), [])

    def test_event_becomes_task_once(self):
        self.connect()
        event = next(e for e in self.events() if e["google_id"] == "e1")
        self.post(self.client_, f"/zehava/calendar/event/{event['id']}/to-task")
        self.post(self.client_, f"/zehava/calendar/event/{event['id']}/to-task")
        tasks = self.repo().list_tasks(self.user)
        self.assertEqual(len(tasks), 1)
        self.assertEqual((tasks[0]["title"], tasks[0]["due_date"], tasks[0]["due_time"], tasks[0]["source"]),
                         ("פגישה עם המנחה", "2026-10-29", "14:00", "calendar"))

    def test_account_deletion_disconnects_google(self):
        self.connect()
        self.post(self.client_, "/zehava/settings/delete-account", {"password": "calm-steps-2026", "confirm": "1"})
        self.assertIn(("POST", google_calendar.REVOKE_URL, {"token": "refresh-1"}), self.google.calls)

    def test_month_navigation(self):
        html = self.html(self.client_.get("/zehava/calendar?month=2026-12"))
        self.assertIn("2026-11", html)      # חודש קודם
        self.assertIn("2027-01", html)      # חודש הבא
        self.assertEqual(self.client_.get("/zehava/calendar?month=garbage").status_code, 200)


class NotConfiguredTests(TimeFlowTestCase):
    def test_without_keys_nothing_pretends_to_be_connected(self):
        client, user = self.register()
        response = client.get("/zehava/calendar/connect")
        self.assertTrue(response.headers["Location"].endswith("/zehava/calendar"))
        html = self.html(client.get("/zehava/calendar"))
        self.assertNotIn("accounts.google.com", html)
        self.assertEqual(google_calendar.status(self.repo(), self.app.config, user), {"state": "not_configured"})
