"""חשבונות ואבטחה: הרשמה, כניסה, הגבלת ניסיונות, CSRF, איפוס, אימות וכותרות."""
import re
import sqlite3
from datetime import timedelta

from timeflow import accounts, clock

from .helpers import TimeFlowTestCase


class RegistrationTests(TimeFlowTestCase):
    def test_register_logs_in_and_hashes_password(self):
        client, user_id = self.register(password="calm-steps-2026")
        user = self.repo().get_user(user_id)
        self.assertNotIn("calm-steps-2026", user["password_hash"])
        self.assertTrue(user["password_hash"].startswith("scrypt:"))
        self.assertEqual(client.get("/zehava").status_code, 200)

    def test_register_rejects_bad_input(self):
        client = self.client()
        response = self.post(client, "/zehava/register", {"email": "not-an-email", "name": "", "password": "short"})
        self.assertEqual(response.status_code, 200)
        html = self.html(response)
        self.assertIn("form-error", html)
        self.assertIsNone(self.repo().get_user_by_email("not-an-email"))

    def test_duplicate_email_is_rejected_case_insensitive(self):
        self.register(email="dup@example.com")
        client = self.client()
        response = self.post(client, "/zehava/register",
                              {"email": "DUP@example.com", "name": "Other", "password": "another-pass-1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("form-error", self.html(response))

    def test_verification_email_written_to_outbox(self):
        self.register(verified=False)
        mails = self.outbox()
        self.assertEqual(len(mails), 1)
        self.assertIn("http://localhost/zehava/verify/", mails[0][1])


class LoginTests(TimeFlowTestCase):
    def test_login_and_logout(self):
        self.register(email="a@example.com", password="calm-steps-2026")
        client = self.client()
        response = self.post(client, "/zehava/login", {"email": "a@example.com", "password": "calm-steps-2026"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.get("/zehava/tasks").status_code, 200)
        self.post(client, "/zehava/logout")
        self.assertEqual(client.get("/zehava/tasks").status_code, 302)

    def test_wrong_password_same_message_as_unknown_email(self):
        self.register(email="a@example.com")
        client = self.client()
        wrong = self.html(self.post(client, "/zehava/login", {"email": "a@example.com", "password": "nope-nope-1"}))
        unknown = self.html(self.post(client, "/zehava/login", {"email": "zz@example.com", "password": "nope-nope-1"}))
        self.assertIn("form-error", wrong)
        self.assertEqual(re.findall(r'class="form-error"[^>]*>([^<]+)', wrong),
                         re.findall(r'class="form-error"[^>]*>([^<]+)', unknown))

    def test_rate_limit_after_five_failures(self):
        self.register(email="a@example.com", password="calm-steps-2026")
        client = self.client()
        for _ in range(5):
            self.post(client, "/zehava/login", {"email": "a@example.com", "password": "wrong-pass-1"})
        # גם הסיסמה הנכונה נחסמת לרבע שעה
        response = self.post(client, "/zehava/login", {"email": "a@example.com", "password": "calm-steps-2026"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get("/zehava/tasks").status_code, 302)
        self.freeze(clock.now() + timedelta(minutes=16))
        response = self.post(client, "/zehava/login", {"email": "a@example.com", "password": "calm-steps-2026"})
        self.assertEqual(response.status_code, 302)

    def test_old_login_attempts_are_deleted(self):
        self.register(email="a@example.com")
        client = self.client()
        self.post(client, "/zehava/login", {"email": "a@example.com", "password": "wrong-pass-1"})
        self.freeze(clock.now() + timedelta(days=31))
        self.post(client, "/zehava/login", {"email": "a@example.com", "password": "wrong-pass-2"})
        rows = self.repo().conn.execute("SELECT COUNT(*) FROM login_attempts").fetchone()[0]
        self.assertEqual(rows, 1)

    def test_next_parameter_cannot_redirect_outside(self):
        self.register(email="a@example.com", password="calm-steps-2026")
        client = self.client()
        response = self.post(client, "/zehava/login", {"email": "a@example.com", "password": "calm-steps-2026",
                                                       "next": "https://evil.example/"})
        self.assertEqual(response.headers["Location"], "/zehava")

    def test_pages_require_login(self):
        client = self.client()
        for path in ("/zehava", "/zehava/tasks", "/zehava/notes", "/zehava/timer", "/zehava/snooze",
                     "/zehava/calendar", "/zehava/insights", "/zehava/settings", "/zehava/settings/export"):
            response = client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertIn("/zehava/login", response.headers["Location"])


class CsrfAndHeadersTests(TimeFlowTestCase):
    def test_post_without_csrf_token_is_rejected(self):
        client, user_id = self.register()
        response = client.post("/zehava/add", data={"title": "x"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.repo().list_tasks(user_id), [])

    def test_security_headers(self):
        client, _ = self.register()
        response = client.get("/zehava/tasks")
        self.assertIn("script-src 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_session_cookie_flags(self):
        client = self.client()
        response = self.post(client, "/zehava/register",
                             {"email": "c@example.com", "name": "C", "password": "calm-steps-2026"})
        cookie = response.headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_other_paths_get_json_errors(self):
        # דפי השגיאה של TimeFlow חלים רק על /zehava. שאר השלד מקבל JSON כמו קודם
        response = self.client().get("/not-timeflow")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "not found"})


class PasswordAndTokenTests(TimeFlowTestCase):
    def test_change_password_logs_out_other_sessions(self):
        client, user_id = self.register(email="a@example.com", password="calm-steps-2026")
        other = self.client()
        self.post(other, "/zehava/login", {"email": "a@example.com", "password": "calm-steps-2026"})
        self.assertEqual(other.get("/zehava/tasks").status_code, 200)
        self.post(client, "/zehava/settings/password",
                  {"current_password": "calm-steps-2026", "new_password": "new-calm-2027"})
        self.assertEqual(client.get("/zehava/tasks").status_code, 200)
        self.assertEqual(other.get("/zehava/tasks").status_code, 302)

    def test_reset_token_works_once(self):
        self.register(email="a@example.com", password="calm-steps-2026")
        with self.app.app_context():
            token = accounts.reset_token(self.repo().get_user_by_email("a@example.com"))
        client = self.client()
        self.assertEqual(client.get(f"/zehava/reset/{token}").status_code, 200)
        response = self.post(client, f"/zehava/reset/{token}", {"password": "brand-new-pass"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.get(f"/zehava/reset/{token}").status_code, 400)
        response = self.post(self.client(), "/zehava/login", {"email": "a@example.com", "password": "brand-new-pass"})
        self.assertEqual(response.status_code, 302)

    def test_reset_token_expires(self):
        self.register(email="a@example.com")
        with self.app.app_context():
            token = accounts.reset_token(self.repo().get_user_by_email("a@example.com"))
            self.assertIsNotNone(accounts.user_for_reset(self.repo(), token))
        # itsdangerous בודק תוקף לפי השעון האמיתי, ולכן בודקים עם max_age שלילי
        with self.app.app_context():
            from timeflow import security
            self.assertIsNone(security.read_token("reset", token, -1))

    def test_forgot_does_not_reveal_accounts(self):
        self.register(email="a@example.com")
        client = self.client()
        known = self.html(self.post(client, "/zehava/forgot", {"email": "a@example.com"}))
        unknown = self.html(self.post(client, "/zehava/forgot", {"email": "nobody@example.com"}))
        self.assertIn("form-ok", known)
        self.assertEqual(known.count("form-ok"), unknown.count("form-ok"))

    def test_verify_email_link(self):
        client, user_id = self.register(verified=False)
        with self.app.app_context():
            token = accounts.verification_token(self.repo().get_user(user_id))
        self.assertEqual(client.get(f"/zehava/verify/{token}").status_code, 200)
        self.assertIsNotNone(self.repo().get_user(user_id)["email_verified_at"])
        self.assertIn("msg-warn", self.html(client.get("/zehava/verify/garbage")))


class AccountDeletionTests(TimeFlowTestCase):
    def test_delete_account_removes_all_data(self):
        client, user_id = self.register(password="calm-steps-2026")
        self.post(client, "/zehava/add", {"title": "Task"})
        self.post(client, "/zehava/notes/add", {"text": "Note"})
        response = self.post(client, "/zehava/settings/delete-account", {"password": "wrong", "confirm": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(self.repo().get_user(user_id))
        response = self.post(client, "/zehava/settings/delete-account", {"password": "calm-steps-2026", "confirm": "1"})
        self.assertEqual(response.status_code, 200)
        conn = sqlite3.connect(self.app.config["DATABASE"])
        for table in ("users", "tasks", "notes", "user_settings", "journey_state"):
            self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0, table)
        conn.close()
