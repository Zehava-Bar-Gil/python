"""זמן מסך: שער הכוונה, רישום דקות, יעדים, תמונת השבוע ופרטיות."""
import json
from datetime import date, datetime, timedelta

from timeflow import clock, db, screen_time
from timeflow.texts import texts

from .helpers import TimeFlowTestCase


class ScreenLogicTests(TimeFlowTestCase):
    def test_logged_minutes_win_over_the_gate(self):
        visits = [{"day": "2026-10-29", "app": "instagram", "minutes": 10, "opened": 1},
                  {"day": "2026-10-29", "app": "instagram", "minutes": 5, "opened": 1},
                  {"day": "2026-10-29", "app": "tiktok", "minutes": None, "opened": 0}]
        usage = screen_time.usage([], visits)
        self.assertEqual(usage[("2026-10-29", "instagram")], (15, "planned"))
        self.assertNotIn(("2026-10-29", "tiktok"), usage)
        usage = screen_time.usage([{"day": "2026-10-29", "app": "instagram", "minutes": 42}], visits)
        self.assertEqual(usage[("2026-10-29", "instagram")], (42, "logged"))

    def test_parse_minutes(self):
        self.assertEqual(screen_time.parse_minutes("", 0, 10), "")
        self.assertEqual(screen_time.parse_minutes(" 7 ", 0, 10), 7)
        for bad in ("11", "-1", "2.5", "abc"):
            with self.subTest(bad=bad):
                self.assertIsNone(screen_time.parse_minutes(bad, 0, 10))

    def test_week_compares_with_last_week(self):
        today = date(2026, 10, 29)
        usage = {(today.isoformat(), "instagram"): (60, "logged"),
                 ((today - timedelta(days=8)).isoformat(), "instagram"): (100, "logged")}
        week = screen_time.week_summary(usage, {"instagram": 30}, [], today)
        self.assertEqual((week["total"], week["previous"], week["trend"], week["diff"]), (60, 100, "less", 40))
        self.assertEqual(len(week["bars"]), 7)
        self.assertTrue(week["bars"][-1]["over"])
        self.assertEqual(week["bars"][-1]["height"], 100)
        self.assertEqual(week["goal_height"], 50)

    def test_week_trends(self):
        today = date(2026, 10, 29)
        last = (today - timedelta(days=7)).isoformat()
        cases = {"empty": {}, "first": {(today.isoformat(), "x"): (20, "logged")},
                 "same": {(today.isoformat(), "x"): (50, "logged"), (last, "x"): (40, "logged")},
                 "more": {(today.isoformat(), "x"): (90, "logged"), (last, "x"): (40, "logged")}}
        for trend, usage in cases.items():
            with self.subTest(trend=trend):
                self.assertEqual(screen_time.week_summary(usage, {}, [], today)["trend"], trend)

    def test_form_action_allows_only_the_listed_apps(self):
        self.assertEqual(screen_time.app_origins(), ["https://web.whatsapp.com", "https://www.facebook.com",
                                                     "https://www.instagram.com", "https://www.tiktok.com",
                                                     "https://www.youtube.com", "https://x.com"])


class ScreenPageTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()

    def test_page_and_side_link(self):
        html = self.html(self.client_.get("/zehava/screen"))
        self.assertIn("זמן מסך", html)
        self.assertIn('href="/zehava/screen"', html)
        for name in ("WhatsApp", "Instagram", "Facebook", "TikTok", "YouTube"):
            self.assertIn(f"לפתוח את {name}", html)
        self.assertIn("מגבלות יישומים", html)

    def test_gate_asks_why_in_the_chosen_address(self):
        expected = {"f": "למה אני נכנסת?", "m": "למה אני נכנס?", "x": "למה אני נכנס.ת?"}
        for address, words in expected.items():
            with self.subTest(address=address):
                self.repo().update_settings(self.user, address=address)
                self.assertIn(words, self.html(self.client_.get("/zehava/screen/open/instagram")))

    def test_gate_redirects_to_the_app_and_records_the_visit(self):
        response = self.post(self.client_, "/zehava/screen/open/instagram",
                             {"reason": "message", "minutes": "10", "note": "  לענות   לדנה "})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["Location"], "https://www.instagram.com/")
        visit = self.repo().screen_visits(self.user, "2026-10-29", "2026-10-29")[0]
        self.assertEqual((visit["reason"], visit["minutes"], visit["note"], visit["opened"]),
                         ("message", 10, "לענות לדנה", 1))
        html = self.html(self.client_.get("/zehava/screen"))
        self.assertIn("10 דק&#39;", html)
        self.assertIn("לפי השער", html)
        self.assertIn("לענות להודעה", html)
        self.assertIn("<time>10:00</time>", html)   # נשמר ב-UTC ומוצג בשעון ישראל

    def test_gate_rejects_bad_answers_and_unknown_apps(self):
        for data in ({"reason": "boredom", "minutes": "10"}, {"reason": "check", "minutes": "999"}, {}):
            with self.subTest(data=data):
                response = self.post(self.client_, "/zehava/screen/open/youtube", data)
                self.assertEqual(response.headers["Location"], "/zehava/screen/open/youtube")
        self.assertEqual(self.repo().screen_visits(self.user, "2026-01-01", "2026-12-31"), [])
        self.assertEqual(self.client_.get("/zehava/screen/open/evil.example").status_code, 404)
        response = self.post(self.client_, "/zehava/screen/open/x?next=https://evil.example",
                             {"reason": "check", "minutes": "5", "url": "https://evil.example"})
        self.assertEqual(response.headers["Location"], "https://x.com/")

    def test_whatsapp_gate(self):
        response = self.post(self.client_, "/zehava/screen/open/whatsapp", {"reason": "message", "minutes": "5"})
        self.assertEqual(response.headers["Location"], "https://web.whatsapp.com/")
        self.assertIn("https://web.whatsapp.com", response.headers["Content-Security-Policy"])

    def test_choosing_not_to_open(self):
        response = self.post(self.client_, "/zehava/screen/open/tiktok", {"skip": "1"}, follow_redirects=True)
        self.assertIn("בחירה טובה", self.html(response))
        self.assertIn("בחרתי לא להיכנס", self.html(response))
        visit = self.repo().screen_visits(self.user, "2026-10-29", "2026-10-29")[0]
        self.assertEqual((visit["opened"], visit["minutes"]), (0, None))

    def test_log_minutes_for_today_and_yesterday(self):
        self.post(self.client_, "/zehava/screen/log", {"day": "today", "min_instagram": "45", "min_youtube": ""})
        self.post(self.client_, "/zehava/screen/log", {"day": "yesterday", "min_facebook": "20"})
        rows = {(row["app"], row["day"]): row["minutes"]
                for row in self.repo().screen_log(self.user, "2026-10-01", "2026-10-31")}
        self.assertEqual(rows, {("instagram", "2026-10-29"): 45, ("facebook", "2026-10-28"): 20})
        response = self.post(self.client_, "/zehava/screen/log", {"min_instagram": "5000"}, follow_redirects=True)
        self.assertIn("בין 0 ל-1440", self.html(response))
        self.assertEqual(self.repo().screen_log(self.user, "2026-10-29", "2026-10-29")[0]["minutes"], 45)

    def test_goals(self):
        self.post(self.client_, "/zehava/screen/limits", {"limit_instagram": "30", "limit_tiktok": "15"})
        self.assertEqual(self.repo().screen_limits(self.user), {"instagram": 30, "tiktok": 15})
        self.post(self.client_, "/zehava/screen/limits", {"limit_instagram": "30", "limit_tiktok": ""})
        self.assertEqual(self.repo().screen_limits(self.user), {"instagram": 30})
        response = self.post(self.client_, "/zehava/screen/limits", {"limit_instagram": "2"}, follow_redirects=True)
        self.assertIn("בין 5 ל-600", self.html(response))
        self.assertEqual(self.repo().screen_limits(self.user), {"instagram": 30})
        self.post(self.client_, "/zehava/screen/log", {"min_instagram": "45"})
        html = self.html(self.client_.get("/zehava/screen"))
        self.assertIn("45 מתוך 30 דק&#39;", html)
        self.assertIn("מחר מתחילים מחדש", html)

    def test_week_card_in_insights(self):
        self.assertIn("עוד אין נתוני זמן מסך", self.html(self.client_.get("/zehava/insights")))
        self.repo().set_screen_limit(self.user, "instagram", 30)
        self.repo().save_screen_log(self.user, "instagram", "2026-10-22", 100)
        self.repo().save_screen_log(self.user, "instagram", "2026-10-29", 60)
        self.repo().add_screen_visit(self.user, "tiktok", "2026-10-29", None, None, opened=False)
        html = self.html(self.client_.get("/zehava/insights"))
        self.assertIn("השבוע 40 דקות פחות מהשבוע שעבר.", html)
        self.assertIn("השבוע בחרת פעם אחת לא להיכנס.", html)
        self.repo().add_screen_visit(self.user, "x", "2026-10-28", None, None, opened=False)
        self.assertIn("השבוע 2 פעמים בחרת לא להיכנס.", self.html(self.client_.get("/zehava/insights")))
        self.assertIn('class="week-chart"', html)

    def test_english_pages(self):
        self.repo().update_settings(self.user, lang="en")
        self.assertIn("Why am I opening it?", self.html(self.client_.get("/zehava/screen/open/facebook")))
        self.assertIn("Screen time", self.html(self.client_.get("/zehava/screen")))

    def test_csp_lets_the_gate_continue(self):
        csp = self.client_.get("/zehava/screen").headers["Content-Security-Policy"]
        self.assertIn("form-action 'self' https://accounts.google.com https://web.whatsapp.com https://www.facebook.com", csp)
        self.assertIn("https://x.com", csp)
        self.assertIn("script-src 'none'", csp)

    def test_login_required(self):
        response = self.client().get("/zehava/screen/open/instagram")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/zehava/login", response.headers["Location"])


class ScreenPrivacyTests(TimeFlowTestCase):
    def test_export_isolation_and_delete(self):
        a_client, a = self.register("a@example.com")
        b_client, b = self.register("b@example.com")
        self.repo().set_screen_limit(a, "instagram", 30)
        self.repo().save_screen_log(a, "instagram", "2026-10-29", 12)
        self.repo().add_screen_visit(a, "instagram", "2026-10-29", "check", 5)
        data = json.loads(a_client.get("/zehava/settings/export").get_data(as_text=True))
        self.assertEqual([row["minutes"] for row in data["screen_limits"]], [30])
        self.assertEqual([row["minutes"] for row in data["screen_log"]], [12])
        self.assertEqual([row["reason"] for row in data["screen_visits"]], ["check"])
        other = json.loads(b_client.get("/zehava/settings/export").get_data(as_text=True))
        self.assertEqual((other["screen_limits"], other["screen_log"], other["screen_visits"]), ([], [], []))
        self.assertNotIn("12 מתוך 30", self.html(b_client.get("/zehava/screen")))
        self.repo().delete_user(a)
        conn = self.repo().conn
        for table in ("screen_limits", "screen_log", "screen_visits"):
            self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)

    def test_privacy_page_mentions_screen_time(self):
        client, _ = self.register()
        self.assertIn("האתר לא רואה את הטלפון", self.html(client.get("/zehava/privacy")))
        self.assertTrue(texts("he")["privacy_points"])

    def test_migration_6(self):
        self.assertGreaterEqual(db.LATEST_VERSION, 6)
        tables = {row[0] for row in self.repo().conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertTrue({"screen_limits", "screen_log", "screen_visits"} <= tables)
