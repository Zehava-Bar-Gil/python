"""הברכה, האייקון שלידה ומצב התצוגה "לפי השעה" נקבעים לפי שעון ישראל."""
import sqlite3
from datetime import datetime
from pathlib import Path

from timeflow import clock, db, ui

from .helpers import TimeFlowTestCase

# השעה בישראל, והברכה, האייקון ומצב התצוגה שמתאימים לה
HOURS = [
    (5, "morning", "light"), (11, "morning", "light"),
    (12, "afternoon", "light"), (16, "afternoon", "light"),
    (17, "evening", "dark"), (21, "evening", "dark"),
    (22, "night", "dark"), (2, "night", "dark"),
]


class DayPartTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()

    def at(self, hour):
        self.freeze(datetime(2026, 10, 29, hour, 0, tzinfo=clock.LOCAL_TZ))

    def test_day_part_and_clock_theme(self):
        for hour, part, theme in HOURS:
            self.assertEqual(ui.day_part(hour), part, hour)
            self.assertEqual(ui.clock_theme(hour), theme, hour)

    def test_greeting_icon_follows_israel_time(self):
        for hour, part, _ in HOURS:
            self.at(hour)
            html = self.html(self.client_.get("/zehava"))
            # האייקון אחרי הברכה, בקו דק כמו בתפריט
            self.assertIn(f'</bdi></span> <span class="day-icon day-{part}">', html, hour)
            self.assertIn(ui.ICONS[ui.DAY_ICONS[part]], html, hour)
        # בלילה: ירח מלא שמחייך, ולא שמש
        self.at(23)
        html = self.html(self.client_.get("/zehava"))
        self.assertIn("לילה טוב", html)
        self.assertIn(ui.ICONS["moon_smile"], html)
        self.assertNotIn(ui.ICONS["sun"], html)

    def test_theme_by_clock(self):
        self.post(self.client_, "/zehava/settings", {"theme": "clock"}, content_type="multipart/form-data")
        settings = self.repo().get_settings(self.user)
        self.assertEqual(settings["theme_by_clock"], 1)
        self.assertEqual(settings["theme"], "auto")  # הבחירה הקודמת נשמרת
        self.at(10)
        self.assertIn('data-theme="light"', self.html(self.client_.get("/zehava/tasks")))
        self.at(20)
        self.assertIn('data-theme="dark"', self.html(self.client_.get("/zehava/tasks")))
        self.assertIn('value="clock" checked', self.html(self.client_.get("/zehava/settings")))
        # בחירה רגילה מבטלת את "לפי השעה"
        self.post(self.client_, "/zehava/settings", {"theme": "light"}, content_type="multipart/form-data")
        self.assertEqual(self.repo().get_settings(self.user)["theme_by_clock"], 0)
        self.assertIn('data-theme="light"', self.html(self.client_.get("/zehava/tasks")))
        # ערך לא מוכר לא משנה כלום
        self.post(self.client_, "/zehava/settings", {"theme": "rainbow"}, content_type="multipart/form-data")
        self.assertEqual(self.repo().get_settings(self.user)["theme"], "light")

    def test_migration_4_keeps_the_old_theme(self):
        old = Path(self.folder) / "v3.db"
        conn = sqlite3.connect(old)
        for number in (1, 2, 3):
            conn.executescript(db.MIGRATIONS[number].read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_version (version) VALUES (3)")
        conn.execute("INSERT INTO users (email, display_name, password_hash, created_at, updated_at)"
                     " VALUES ('a@example.com', 'A', 'x', 'n', 'n')")
        conn.execute("INSERT INTO user_settings (user_id, theme, updated_at) VALUES (1, 'dark', 'n')")
        conn.commit()
        conn.close()
        self.assertEqual(db.migrate(old, Path(self.folder) / "v3-backups"), db.LATEST_VERSION)
        conn = sqlite3.connect(old)
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("SELECT theme, theme_by_clock FROM user_settings").fetchone(), ("dark", 0))
        # גרסה 5: מי שכבר רשומה מקבלת פנייה "לא מוגדר" (x), עד שתבחר אחרת
        self.assertEqual(conn.execute("SELECT address FROM user_settings").fetchone(), ("x",))
