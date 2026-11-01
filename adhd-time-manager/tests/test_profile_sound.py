"""פרופיל אישי (שם בשתי שפות, יום הולדת ומשאלה, תמונה או אווטאר) והנגן שממשיך בין הדפים."""
import sqlite3
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from PIL import Image

from timeflow import clock, db, ui

from .helpers import PROJECT_DIR, TimeFlowTestCase

FRAMED = {"Sec-Fetch-Dest": "iframe"}


def bday(text):
    # יום ההולדת נשלח בשלוש רשימות: שנה, חודש ויום
    year, month, day = text.split("-")
    return {"birthday_year": year, "birthday_month": month, "birthday_day": day}


def image_file(fmt="PNG", size=(600, 400)):
    data = BytesIO()
    Image.new("RGB", size, (141, 185, 220)).save(data, fmt)
    data.seek(0)
    return data


class ProfileTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()

    def save_profile(self, **fields):
        return self.post(self.client_, "/zehava/settings", fields, content_type="multipart/form-data")

    def test_migration_3_moves_the_name_to_its_language(self):
        old = Path(self.folder) / "v2.db"
        conn = sqlite3.connect(old)
        for number in (1, 2):
            conn.executescript(db.MIGRATIONS[number].read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_version (version) VALUES (2)")
        for email, name in (("he@example.com", "זהבה"), ("en@example.com", "Old")):
            conn.execute("INSERT INTO users (email, display_name, password_hash, created_at, updated_at)"
                         " VALUES (?, ?, 'x', 'n', 'n')", (email, name))
        conn.commit()
        conn.close()
        self.assertEqual(db.migrate(old, Path(self.folder) / "v2-backups"), db.LATEST_VERSION)
        conn = sqlite3.connect(old)
        self.addCleanup(conn.close)
        rows = conn.execute("SELECT display_name, first_name_he, first_name_en, avatar FROM users ORDER BY id").fetchall()
        self.assertEqual(rows, [("זהבה", "זהבה", None, "letter"), ("Old", None, "Old", "letter")])

    def test_name_follows_the_site_language(self):
        self.save_profile(first_name_he="זהבה", first_name_en="Zehava", last_name_he="בר גיל", last_name_en="Bar Gil")
        html = self.html(self.client_.get("/zehava"))
        self.assertIn("<bdi>זהבה</bdi>", html)
        self.assertIn('title="זהבה בר גיל"', html)
        self.repo().update_settings(self.user, lang="en")
        html = self.html(self.client_.get("/zehava"))
        self.assertIn("<bdi>Zehava</bdi>", html)
        self.assertIn('title="Zehava Bar Gil"', html)
        # שם חסר בשפה אחת: מופיע השם מהשפה השנייה
        self.save_profile(first_name_he="זהבה", first_name_en="")
        self.assertIn("<bdi>זהבה</bdi>", self.html(self.client_.get("/zehava")))

    def test_birthday_is_validated(self):
        self.save_profile(**bday("2030-01-01"))
        self.assertIsNone(self.repo().get_user(self.user)["birthday"])
        self.save_profile(**bday("1990-06-31"))
        self.assertIsNone(self.repo().get_user(self.user)["birthday"])
        self.save_profile(birthday_year="x1990", birthday_month="1", birthday_day="1")
        self.assertIsNone(self.repo().get_user(self.user)["birthday"])
        self.save_profile(**bday("1990-10-29"))
        self.assertEqual(self.repo().get_user(self.user)["birthday"], "1990-10-29")
        # שלוש רשימות ריקות: מוחקים את יום ההולדת, בלי הודעת שגיאה
        self.save_profile()
        self.assertIsNone(self.repo().get_user(self.user)["birthday"])

    def test_birthday_is_three_lists_in_the_site_language(self):
        self.save_profile(**bday("1990-10-29"))
        html = self.html(self.client_.get("/zehava/settings"))
        self.assertNotIn('type="date" name="birthday"', html)
        self.assertIn('<option value="29" selected>29</option>', html)
        self.assertIn('<option value="10" selected>אוקטובר</option>', html)
        self.assertIn('<option value="1990" selected>1990</option>', html)

    def test_birthday_offers_a_wish_that_can_become_the_goal(self):
        self.save_profile(first_name_he="זהבה", **bday("1990-10-29"))
        html = self.html(self.client_.get("/zehava"))
        self.assertIn("יום הולדת שמח, <bdi>זהבה</bdi>", html)
        self.assertIn('class="birthday glass"', html)
        self.post(self.client_, "/zehava/wish", {"wish": "  לסיים את הקורס בהצטיינות  ", "make_goal": "1"})
        self.assertEqual(self.repo().get_wish(self.user, 2026)["body"], "לסיים את הקורס בהצטיינות")
        self.assertEqual(self.repo().get_settings(self.user)["goal_text"], "לסיים את הקורס בהצטיינות")
        html = self.html(self.client_.get("/zehava"))
        self.assertIn('<p class="bday-wish" dir="auto">לסיים את הקורס בהצטיינות</p>', html)
        # כתיבה נוספת באותה שנה מעדכנת את אותה משאלה
        self.post(self.client_, "/zehava/wish", {"wish": "ללמוד לנגן"})
        self.assertEqual([w["body"] for w in self.repo().list_wishes(self.user)], ["ללמוד לנגן"])
        self.assertIn("ללמוד לנגן", self.html(self.client_.get("/zehava/settings")))
        # למחרת: אין כרטיס, ומשאלה חדשה לא נשמרת
        self.freeze(datetime(2026, 10, 30, 10, 0, tzinfo=clock.LOCAL_TZ))
        self.assertNotIn('class="birthday glass"', self.html(self.client_.get("/zehava")))
        self.post(self.client_, "/zehava/wish", {"wish": "עוד משאלה"})
        self.assertEqual([w["body"] for w in self.repo().list_wishes(self.user)], ["ללמוד לנגן"])

    def test_february_29_celebrates_on_the_28th_in_common_years(self):
        self.assertTrue(ui.is_birthday("2000-02-29", date(2027, 2, 28)))
        self.assertFalse(ui.is_birthday("2000-02-29", date(2028, 2, 28)))
        self.assertTrue(ui.is_birthday("2000-02-29", date(2028, 2, 29)))
        self.assertFalse(ui.is_birthday(None, date(2028, 2, 29)))

    def test_avatar_choice(self):
        self.save_profile(avatar="balloon")
        self.assertEqual(self.repo().get_user(self.user)["avatar"], "balloon")
        self.assertIn("avatar avatar-balloon", self.html(self.client_.get("/zehava")))
        # בחירה לא מוכרת, או "תמונה" בלי תמונה שמורה, לא משנה כלום
        self.save_profile(avatar="dragon")
        self.save_profile(avatar="photo")
        self.assertEqual(self.repo().get_user(self.user)["avatar"], "balloon")

    def test_photo_upload_is_resized_and_private(self):
        self.save_profile(photo=(image_file(), "me.png"))
        self.assertEqual(self.repo().get_user(self.user)["avatar"], "photo")
        response = self.client_.get("/zehava/avatar.jpg")
        self.assertEqual(response.mimetype, "image/jpeg")
        with Image.open(BytesIO(response.data)) as saved:
            self.assertEqual((saved.format, saved.size), ("JPEG", (256, 256)))
        self.assertIn('src="/zehava/avatar.jpg"', self.html(self.client_.get("/zehava")))
        # משתמשת אחרת לא רואה את התמונה
        other, _ = self.register(email="other@example.com", name="Other")
        self.assertEqual(other.get("/zehava/avatar.jpg").status_code, 404)
        # מחיקה: חוזרים לאות הראשונה
        self.post(self.client_, "/zehava/settings/photo/delete")
        self.assertEqual(self.repo().get_user(self.user)["avatar"], "letter")
        self.assertEqual(self.client_.get("/zehava/avatar.jpg").status_code, 404)

    def test_bad_or_huge_photo_is_refused(self):
        self.save_profile(photo=(BytesIO(b"<svg onload=alert(1)>"), "x.png"))
        self.assertIsNone(self.repo().get_avatar_photo(self.user))
        self.save_profile(photo=(BytesIO(b"\0" * (3 * 1024 * 1024 + 10)), "big.jpg"))
        self.assertIsNone(self.repo().get_avatar_photo(self.user))
        with self.client_.session_transaction() as session:
            keys = [message[1][0] for message in session.get("_flashes", [])]
        self.assertIn("photo_too_big", keys)
        self.assertEqual(self.repo().get_user(self.user)["avatar"], "letter")

    def test_export_includes_profile_and_wishes(self):
        self.save_profile(photo=(image_file("JPEG"), "me.jpg"), **bday("1990-10-29"))
        self.post(self.client_, "/zehava/wish", {"wish": "שנה רגועה"})
        data = self.client_.get("/zehava/settings/export").get_json()
        self.assertEqual(data["user"]["birthday"], "1990-10-29")
        self.assertEqual(data["birthday_wishes"][0]["body"], "שנה רגועה")
        self.assertEqual(data["avatar_photo"], {"saved": True})


    def test_calm_mode_is_a_switch_in_settings(self):
        html = self.html(self.client_.get("/zehava/settings"))
        self.assertIn('name="calm_mode"', html)
        self.save_profile(calm_mode="1")
        self.assertEqual(self.repo().get_settings(self.user)["calm_mode"], 1)
        home = self.html(self.client_.get("/zehava"))
        self.assertIn('class="calm-note', home)
        self.save_profile()
        self.assertEqual(self.repo().get_settings(self.user)["calm_mode"], 0)

    def test_data_card_speaks_plainly(self):
        html = self.html(self.client_.get("/zehava/settings"))
        self.assertNotIn("JSON", html)
        self.assertIn("הורדת כל הנתונים שלי", html)


class SoundPlayerTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()

    def test_sounds_page_plays_through_the_player(self):
        html = self.html(self.client_.get("/zehava/sounds"))
        self.assertNotIn("make_sounds.py", html)
        self.assertNotIn("<audio", html)
        self.assertIn('href="/zehava/listen/deep?next=/zehava/sounds" target="_top"', html)

    def test_player_frames_the_site_and_keeps_the_music(self):
        html = self.html(self.client_.get("/zehava/listen/calm?next=/zehava/tasks"))
        self.assertIn('<iframe class="listen-frame" name="app" src="/zehava/tasks"', html)
        self.assertIn("<audio controls autoplay loop", html)
        self.assertIn("sounds/calm.ogg", html)
        with self.client_.session_transaction() as session:
            self.assertEqual(session["playing"], "calm")
        # רק דפים של האתר נכנסים למסגרת, ולא נגן בתוך נגן
        for target in ("https://evil.example/", "//evil.example", "/zehava/listen/deep"):
            html = self.html(self.client_.get(f"/zehava/listen/calm?next={target}"))
            self.assertIn('src="/zehava/sounds"', html)
        self.assertEqual(self.client_.get("/zehava/listen/disco").status_code, 404)

    def test_pages_inside_the_player_show_what_is_playing(self):
        self.client_.get("/zehava/listen/deep")
        framed = self.html(self.client_.get("/zehava/tasks", headers=FRAMED))
        self.assertIn('class="inline-form now-playing"', framed)
        self.assertIn('target="_top"', framed)
        self.assertIn('name="next" value="/zehava/tasks"', framed)
        self.assertIn("is-playing", self.html(self.client_.get("/zehava/sounds", headers=FRAMED)))
        # דף רגיל (לא בתוך הנגן) לא מציג את הכפתור
        self.assertNotIn("now-playing", self.html(self.client_.get("/zehava/tasks")))
        # בתוך המסגרת לא נפתח נגן נוסף
        self.assertEqual(self.client_.get("/zehava/listen/calm", headers=FRAMED).status_code, 302)

    def test_stop_returns_to_the_same_page(self):
        self.client_.get("/zehava/listen/deep")
        response = self.post(self.client_, "/zehava/listen/stop", {"next": "/zehava/notes"})
        self.assertEqual(response.headers["Location"], "/zehava/notes")
        with self.client_.session_transaction() as session:
            self.assertNotIn("playing", session)
        response = self.post(self.client_, "/zehava/listen/stop", {"next": "https://evil.example/"})
        self.assertEqual(response.headers["Location"], "/zehava/sounds")

    def test_bars_step_aside_while_scrolling(self):
        css = (PROJECT_DIR / "static" / "css" / "zehava.css").read_text(encoding="utf-8")
        self.assertIn("animation-timeline: scroll(root block)", css)
        self.assertIn(".top-nav:hover", css)
        self.assertIn(".site-footer:hover", css)


class BirthdayPopupTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()
        today = clock.today()
        self.post(self.client_, "/zehava/settings", bday(f"1990-{today.month}-{today.day}"),
                  content_type="multipart/form-data")

    def test_popup_on_the_birthday_with_wish_list(self):
        html = self.html(self.client_.get("/zehava"))
        self.assertIn('<dialog open class="bday-pop', html)
        self.assertIn("מזל טוב, <bdi>", html)
        self.assertIn("רשימת המשאלות", html)
        self.assertIn('id="pop-wish"', html)

    def test_popup_in_english_says_happy_birthday(self):
        self.post(self.client_, "/zehava/lang/en")
        html = self.html(self.client_.get("/zehava"))
        self.assertIn("Happy Birthday, <bdi>", html)
        self.assertIn("Wish List", html)

    def test_closing_or_saving_a_wish_hides_it_for_today(self):
        self.post(self.client_, "/zehava/birthday/seen")
        self.assertNotIn("bday-pop", self.html(self.client_.get("/zehava")))
        client, user = self.register(email="b@example.com")
        today = clock.today()
        self.post(client, "/zehava/settings", bday(f"1991-{today.month}-{today.day}"), content_type="multipart/form-data")
        self.post(client, "/zehava/wish", {"wish": "שנה של שקט"})
        html = self.html(client.get("/zehava"))
        self.assertNotIn("bday-pop", html)
        self.assertIn("שנה של שקט", html)

    def test_no_popup_on_other_days(self):
        self.post(self.client_, "/zehava/settings", bday("1990-01-01" if clock.today().month != 1 else "1990-06-15"),
                  content_type="multipart/form-data")
        self.assertNotIn("bday-pop", self.html(self.client_.get("/zehava")))
