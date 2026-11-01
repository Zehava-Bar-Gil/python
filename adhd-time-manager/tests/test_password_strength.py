"""חוזק סיסמה: חלשה (לא נשמרת), בינונית או חזקה, ומד חוזק בטופס בלי JavaScript."""
from timeflow.accounts import password_strength

from .helpers import TimeFlowTestCase


class PasswordStrengthTests(TimeFlowTestCase):
    def test_levels(self):
        email = "zehava@example.com"
        for password in ("1234567", "12345678", "abcdefgh", "aaaaaaaa", "Password123!", "qwerty12", "zehava2026"):
            with self.subTest(password=password):
                self.assertEqual(password_strength(password, email), "weak")
        for password in ("Kfar-Saba7", "ab12cd34", "גשם בחורף 9"):
            with self.subTest(password=password):
                self.assertEqual(password_strength(password, email), "medium")
        for password in ("sunflower-tea", "calm-steps-2026", "צעד קטן כל בוקר"):
            with self.subTest(password=password):
                self.assertEqual(password_strength(password, email), "strong")

    def test_weak_password_is_refused_with_a_reason(self):
        client = self.client()
        html = self.html(self.post(client, "/zehava/register",
                                   {"email": "a@example.com", "name": "A", "password": "12345678"}))
        self.assertIn("הסיסמה חלשה", html)
        self.assertIsNone(self.repo().get_user_by_email("a@example.com"))

    def test_medium_and_strong_are_saved_and_named(self):
        client, _ = self.register(email="m@example.com", password="Kfar-Saba7")
        self.assertIn("חוזק הסיסמה: בינונית", self.html(client.get("/zehava")))
        client, _ = self.register(email="s@example.com", password="sunflower-tea")
        self.assertIn("חוזק הסיסמה: חזקה", self.html(client.get("/zehava")))

    def test_forms_show_a_live_meter(self):
        html = self.html(self.client().get("/zehava/register"))
        self.assertIn('class="pw-meter"', html)
        self.assertIn('pattern=".{12,}"', html)
        self.assertIn("novalidate", html)
        client, _ = self.register()
        self.assertIn('id="new-password"', self.html(client.get("/zehava/settings")))

    def test_change_password_reports_the_level(self):
        client, _ = self.register()
        self.post(client, "/zehava/settings/password",
                  {"current_password": "calm-steps-2026", "new_password": "Kfar-Saba7"})
        self.assertIn("חוזק הסיסמה: בינונית", self.html(client.get("/zehava/settings")))
