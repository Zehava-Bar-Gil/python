"""Daily Pulse, הסיכום היומי במייל, קישורי המייל והסרה מרשימת התפוצה."""
from datetime import datetime, timedelta

from timeflow import clock, mailer, security
from timeflow.texts import texts

from .helpers import TimeFlowTestCase


def at(hour, minute=0, day=29):
    return datetime(2026, 10, day, hour, minute, tzinfo=clock.LOCAL_TZ)


class PulseTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()

    def pulse(self):
        return self.repo().get_pulse(self.user, clock.today().isoformat())

    def test_save_rating_with_valid_reasons_only(self):
        self.client_.post("/zehava/pulse")  # בלי CSRF: נדחה
        self.assertIsNone(self.pulse())
        self.post(self.client_, "/zehava/pulse", {"rating": "4", "reasons": ["tired", "evil", "focused"]})
        self.assertEqual((self.pulse()["rating"], self.pulse()["reasons"]), (4, "tired,focused"))

    def test_edit_keeps_one_answer_per_day(self):
        self.post(self.client_, "/zehava/pulse", {"rating": "4"})
        self.post(self.client_, "/zehava/pulse", {"rating": "2", "reasons": "distractions"})
        rows = self.repo().pulses_since(self.user, "2000-01-01")
        self.assertEqual([(r["rating"], r["reasons"]) for r in rows], [(2, "distractions")])

    def test_skip_and_invalid(self):
        self.post(self.client_, "/zehava/pulse", {"rating": "9"})
        self.assertIsNone(self.pulse())
        self.post(self.client_, "/zehava/pulse", {"skip": "1"})
        self.assertEqual((self.pulse()["skipped"], self.pulse()["rating"]), (1, None))

    def test_home_asks_only_in_the_evening(self):
        self.repo().update_settings(self.user, notifications="normal")
        self.assertNotIn('id="pulse"', self.html(self.client_.get("/zehava")))
        self.freeze(at(18))
        self.assertIn('id="pulse"', self.html(self.client_.get("/zehava")))
        self.post(self.client_, "/zehava/pulse", {"rating": "3"})
        self.assertNotIn('id="pulse"', self.html(self.client_.get("/zehava")))

    def test_pulse_can_be_turned_off(self):
        self.freeze(at(18))
        self.repo().update_settings(self.user, pulse_enabled=0)
        self.assertNotIn('id="pulse"', self.html(self.client_.get("/zehava")))
        self.repo().update_settings(self.user, pulse_enabled=1, notifications="off")
        self.assertNotIn('id="pulse"', self.html(self.client_.get("/zehava")))
        self.repo().update_settings(self.user, notifications="quiet", calm_mode=1)
        self.assertNotIn('id="pulse"', self.html(self.client_.get("/zehava")))

    def test_email_link_works_without_login_for_that_day(self):
        with self.app.app_context():
            token = security.make_token("pulse", {"uid": self.user, "day": "2026-10-28"})
        anonymous = self.client()
        self.assertEqual(anonymous.get(f"/zehava/pulse/email/{token}").status_code, 200)
        self.post(anonymous, f"/zehava/pulse/email/{token}", {"rating": "5"})
        self.assertEqual(self.repo().get_pulse(self.user, "2026-10-28")["rating"], 5)
        # הקישור לא פותח שום דף אחר
        self.assertEqual(anonymous.get("/zehava/tasks").status_code, 302)

    def test_tampered_or_wrong_purpose_token(self):
        with self.app.app_context():
            unsubscribe = security.make_token("unsubscribe", {"uid": self.user})
        anonymous = self.client()
        self.assertEqual(anonymous.get(f"/zehava/pulse/email/{unsubscribe}").status_code, 400)
        self.assertEqual(anonymous.get("/zehava/pulse/email/abc.def.ghi").status_code, 400)


class DailyEmailTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register(name="Zehava")
        self.repo().update_settings(self.user, daily_email=1, daily_email_at="20:00")
        task_id = self.repo().create_task(self.user, "להגיש את הפרויקט")
        self.post(self.client_, f"/zehava/toggle/{task_id}")

    def daily_mails(self):
        # בלי מייל האימות מההרשמה
        return [mail for mail in self.outbox() if mail[0] == texts("he")["mail_subject_daily"]]

    def run_at(self, moment):
        self.freeze(moment)
        return mailer.run_daily_emails(self.app)

    def test_sent_once_after_chosen_time(self):
        self.assertEqual(self.run_at(at(19, 59)), 0)
        self.assertEqual(self.run_at(at(20, 1)), 1)
        self.assertEqual(self.run_at(at(20, 2)), 0)
        self.assertEqual(self.run_at(at(23, 0)), 0)
        self.assertEqual(len(self.daily_mails()), 1)
        self.assertEqual(self.run_at(at(20, 1, day=30)), 1)

    def test_subject_is_neutral_and_body_has_real_data(self):
        self.run_at(at(20, 1))
        subject, body, message = self.daily_mails()[0]
        self.assertNotIn("להגיש", subject)
        self.assertIn("להגיש את הפרויקט", body)
        self.assertIn("/zehava/pulse/email/", body)
        self.assertIn("/zehava/unsubscribe/", message["List-Unsubscribe"])
        self.assertEqual(message["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    def test_not_sent_to_unverified_or_disabled(self):
        _, other = self.register(email="new@example.com", verified=False)
        self.repo().update_settings(other, daily_email=1, daily_email_at="20:00")
        self.assertEqual(self.run_at(at(20, 1)), 1)
        self.repo().update_settings(self.user, daily_email=0)
        self.assertEqual(self.run_at(at(20, 1, day=30)), 0)

    def test_failed_send_is_retried_later_with_a_limit(self):
        self.app.config["MAIL_BACKEND"] = "off"           # כל שליחה נכשלת
        self.assertEqual(self.run_at(at(20, 1)), 0)
        status = self.repo().daily_email_status(self.user, "2026-10-29")
        self.assertEqual((status["status"], status["attempts"]), ("failed", 1))
        self.run_at(at(20, 10))                           # עוד לא עברה חצי שעה
        self.assertEqual(self.repo().daily_email_status(self.user, "2026-10-29")["attempts"], 1)
        self.run_at(at(20, 35))
        self.run_at(at(21, 10))
        status = self.repo().daily_email_status(self.user, "2026-10-29")
        self.assertEqual((status["status"], status["attempts"]), ("failed", 3))
        self.app.config["MAIL_BACKEND"] = "file"
        self.assertEqual(self.run_at(at(22, 0)), 0)       # הגענו למגבלה
        self.assertEqual(self.daily_mails(), [])

    def test_failed_send_succeeds_on_retry(self):
        self.app.config["MAIL_BACKEND"] = "off"
        self.run_at(at(20, 1))
        self.app.config["MAIL_BACKEND"] = "file"
        self.assertEqual(self.run_at(at(20, 40)), 1)
        self.assertEqual(self.repo().daily_email_status(self.user, "2026-10-29")["status"], "sent")
        self.assertEqual(len(self.daily_mails()), 1)

    def test_unsubscribe_confirm_then_post(self):
        with self.app.app_context():
            token = security.make_token("unsubscribe", {"uid": self.user})
        anonymous = self.client()
        self.assertEqual(anonymous.get(f"/zehava/unsubscribe/{token}").status_code, 200)
        self.assertEqual(self.repo().get_settings(self.user)["daily_email"], 1)
        # בלחיצה אחת מתוכנת המייל אין אסימון CSRF, ולכן הנתיב פטור ממנו
        self.assertEqual(anonymous.post(f"/zehava/unsubscribe/{token}").status_code, 200)
        self.assertEqual(self.repo().get_settings(self.user)["daily_email"], 0)
        self.assertEqual(anonymous.post("/zehava/unsubscribe/forged").status_code, 400)

    def test_manual_send_needs_verified_address_and_is_limited(self):
        for _ in range(7):
            self.post(self.client_, "/zehava/mail/send")
        self.assertEqual(len(self.daily_mails()), 5)
        self.freeze(clock.now() + timedelta(days=1, minutes=1))
        self.post(self.client_, "/zehava/mail/send")
        self.assertEqual(len(self.daily_mails()), 6)
        _, other = self.register(email="new@example.com", verified=False)
        client = self.client()
        self.post(client, "/zehava/login", {"email": "new@example.com", "password": "calm-steps-2026"})
        before = len(self.outbox())
        self.post(client, "/zehava/mail/send")
        self.assertEqual(len(self.outbox()), before)

    def test_account_emails_are_limited(self):
        _, other = self.register(email="new@example.com", verified=False)
        client = self.client()
        self.post(client, "/zehava/login", {"email": "new@example.com", "password": "calm-steps-2026"})
        before = len(self.outbox())
        for _ in range(5):
            self.post(client, "/zehava/verify/resend")
        self.assertEqual(len(self.outbox()) - before, 2)   # 3 בשעה, כולל המייל מההרשמה
