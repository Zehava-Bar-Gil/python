"""פנייה בעברית לפי ההגדרה "מין": נקבה, זכר או לא מוגדר (את.ה)."""
from timeflow import db
from timeflow.texts import TEXTS, Addr, texts

from .helpers import TimeFlowTestCase


class AddressTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()

    def save(self, address):
        return self.post(self.client_, "/zehava/settings", {"address": address}, content_type="multipart/form-data")

    def test_new_users_start_undefined(self):
        self.assertEqual(self.repo().get_settings(self.user)["address"], "x")
        self.assertEqual(db.LATEST_VERSION, 5)

    def test_settings_offers_three_choices(self):
        html = self.html(self.client_.get("/zehava/settings"))
        for value, label in (("m", "זכר"), ("f", "נקבה"), ("x", "לא מוגדר")):
            self.assertIn(f'value="{value}"', html)
            self.assertIn(f"<span>{label}</span>", html)

    def test_hebrew_follows_the_choice(self):
        checks = {"f": "את יכולה לצאת", "m": "אתה יכול לצאת", "x": "את.ה יכול.ה לצאת"}
        for address, words in checks.items():
            with self.subTest(address=address):
                self.save(address)
                self.assertEqual(self.repo().get_settings(self.user)["address"], address)
                self.assertIn(words, self.html(self.client_.get("/zehava/focus")))

    def test_bad_value_keeps_the_current_one(self):
        self.save("f")
        self.save("robot")
        self.assertEqual(self.repo().get_settings(self.user)["address"], "f")

    def test_english_is_the_same_for_everyone(self):
        self.assertEqual(texts("en", "f"), texts("en", "m"))
        self.assertFalse(any(isinstance(value, Addr) for value in TEXTS["en"].values()))

    def test_every_form_is_written(self):
        for key, value in TEXTS["he"].items():
            if isinstance(value, Addr):
                with self.subTest(key=key):
                    self.assertEqual(set(value), {"f", "m", "x"})
                    self.assertEqual(len(set(value.values())), 3)
                    self.assertIn(".", value["x"].replace(". ", " ").rstrip(". 🌿"))
