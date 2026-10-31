"""ממשק, נגישות ומסד הנתונים: ניווט, בלי JavaScript, ערכות צבע, כיוון, XSS, גיבוי ושחזור ותקלות במסד."""
import re
import sqlite3
from pathlib import Path

from timeflow import db
from timeflow.ui import NAV

from .helpers import TimeFlowTestCase

PAGES = ("/zehava", "/zehava/tasks", "/zehava/notes", "/zehava/timer", "/zehava/focus", "/zehava/snooze",
         "/zehava/calendar", "/zehava/insights", "/zehava/settings", "/zehava/sounds", "/zehava/privacy")
PUBLIC_PAGES = ("/zehava/login", "/zehava/register", "/zehava/forgot", "/zehava/privacy")


class InterfaceTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()

    def test_exactly_five_items_in_top_nav(self):
        self.assertEqual([key for key, _, _ in NAV], ["todo", "notes", "timer", "snooze", "calendar"])
        html = self.html(self.client_.get("/zehava/tasks"))
        top = re.search(r'<ul class="nav-links">(.*?)</ul>', html, re.S).group(1)
        self.assertEqual(top.count("<li>"), 5)
        self.assertNotIn("insights", top)
        self.assertNotIn("settings", top)
        self.assertIn('href="/zehava/tasks" aria-current="page"', top)

    def test_no_javascript_on_any_page(self):
        for path in PAGES:
            html = self.html(self.client_.get(path))
            self.assertNotIn("<script", html.lower(), path)
            self.assertNotRegex(html, r"\son[a-z]+=", path)
        anonymous = self.client()
        for path in PUBLIC_PAGES:
            response = anonymous.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertNotIn("<script", self.html(response).lower(), path)

    def test_every_page_has_skip_link_and_main(self):
        for path in PAGES:
            html = self.html(self.client_.get(path))
            self.assertIn('href="#content"', html, path)
            self.assertIn('id="content"', html, path)

    def test_inputs_have_labels(self):
        for path in ("/zehava/tasks", "/zehava/notes", "/zehava/settings", "/zehava/snooze", "/zehava/timer"):
            html = self.html(self.client_.get(path))
            for field in re.findall(r"<(?:input|select|textarea)\b[^>]*>", html):
                if 'type="hidden"' in field or "aria-label=" in field:
                    continue
                # כל שדה גלוי נמצא בתוך <label> או מקושר אליו ב-id
                field_id = re.search(r'id="([^"]+)"', field)
                position = html.index(field)
                opened, closed = html.rfind("<label", 0, position), html.rfind("</label>", 0, position)
                inside = opened > closed
                linked = field_id and f'for="{field_id.group(1)}"' in html
                self.assertTrue(inside or linked, f"{path}: {field}")

    def test_theme_language_and_motion(self):
        html = self.html(self.client_.get("/zehava"))
        self.assertIn('<html lang="he" dir="rtl" data-theme="auto"', html)
        self.repo().update_settings(self.user, theme="dark", lang="en", reduce_motion=1)
        html = self.html(self.client_.get("/zehava"))
        self.assertIn('<html lang="en" dir="ltr" data-theme="dark" class="no-motion"', html)

    def test_settings_form_saves_and_validates(self):
        self.post(self.client_, "/zehava/settings", {
            "theme": "light", "lang": "en", "sound_pref": "none", "notifications": "normal",
            "focus_minutes": "500", "short_break_minutes": "3", "long_break_minutes": "20",
            "daily_email_at": "07:30", "timer_chime": "1", "display_name": "Zee"})
        settings = self.repo().get_settings(self.user)
        self.assertEqual((settings["theme"], settings["lang"], settings["focus_minutes"], settings["timer_chime"]),
                         ("light", "en", 120, 1))
        self.assertEqual(self.repo().get_user(self.user)["display_name"], "Zee")
        self.post(self.client_, "/zehava/settings", {"theme": "neon", "daily_email_at": "99:99"})
        settings = self.repo().get_settings(self.user)
        self.assertEqual((settings["theme"], settings["daily_email_at"]), ("light", "07:30"))

    def test_user_text_is_escaped(self):
        attack = '<img src=x onerror=alert(1)>"\'<script>alert(2)</script>'
        self.post(self.client_, "/zehava/add", {"title": attack})
        self.post(self.client_, "/zehava/notes/add", {"text": attack})
        self.post(self.client_, "/zehava/snooze/write", {"text": attack})
        for path in ("/zehava", "/zehava/tasks", "/zehava/notes", "/zehava/snooze", "/zehava/focus"):
            html = self.html(self.client_.get(path))
            self.assertNotIn("<img src=x", html, path)
            self.assertNotIn("<script>alert", html, path)

    def test_calm_mode_hides_the_planning_board(self):
        self.repo().create_task(self.user, "משימה אחת")
        self.assertIn('class="board"', self.html(self.client_.get("/zehava")))
        self.post(self.client_, "/zehava/calm")
        html = self.html(self.client_.get("/zehava"))
        self.assertNotIn('class="board"', html)
        self.assertIn("משימה אחת", html)          # הצעד הבא עדיין מוצג ב"עכשיו"

    def test_goal_text(self):
        self.post(self.client_, "/zehava/goal", {"goal": "x" * 100})
        self.assertEqual(len(self.repo().get_settings(self.user)["goal_text"]), 60)

    def test_language_switch(self):
        self.post(self.client_, "/zehava/lang/en", {"back": "/zehava/tasks"})
        self.assertIn('lang="en"', self.html(self.client_.get("/zehava/tasks")))
        response = self.post(self.client_, "/zehava/lang/he", {"back": "https://evil.example/"})
        self.assertFalse(response.headers["Location"].startswith("https://evil"))

    def test_not_found_page(self):
        response = self.client_.get("/zehava/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertIn("<html", self.html(response))


class DatabaseTests(TimeFlowTestCase):
    def test_migrate_is_idempotent(self):
        path = self.app.config["DATABASE"]
        self.assertEqual(db.migrate(path, self.app.config["BACKUP_DIR"]), db.LATEST_VERSION)
        self.assertEqual(db.migrate(path, self.app.config["BACKUP_DIR"]), db.LATEST_VERSION)
        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        self.assertEqual(self.repo().conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ("users", "tasks", "task_steps", "notes", "focus_sessions", "journey_events", "daily_pulse",
                      "insights", "snooze_entries", "email_log", "google_accounts", "calendar_events"):
            self.assertIn(table, tables)

    def test_backup_and_restore(self):
        _, user = self.register()
        self.repo().create_task(user, "לפני הגיבוי")
        backup = db.backup(self.app.config["DATABASE"], self.app.config["BACKUP_DIR"])
        self.assertTrue(Path(backup).exists())
        self.repo().create_task(user, "אחרי הגיבוי")
        db.restore(backup, self.app.config["DATABASE"])
        self.assertEqual([t["title"] for t in self.repo().list_tasks(user)], ["לפני הגיבוי"])

    def test_constraints_protect_data(self):
        _, user = self.register()
        conn = self.repo().conn
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO tasks (user_id, title, priority, created_at, updated_at)"
                         " VALUES (?, 'x', 'mega', 'now', 'now')", (user,))
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO tasks (user_id, title, created_at, updated_at) VALUES (999, 'x', 'n', 'n')")

    def test_database_error_shows_calm_page(self):
        def broken():
            raise sqlite3.OperationalError("disk I/O error")

        self.app.add_url_rule("/zehava/broken-for-test", "broken_for_test", broken)
        client, _ = self.register()
        response = client.get("/zehava/broken-for-test")
        self.assertEqual(response.status_code, 500)
        html = self.html(response)
        self.assertNotIn("disk I/O", html)
        self.assertNotIn("Traceback", html)
        self.assertIn("<html", html)
