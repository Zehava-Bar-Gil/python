"""שכבת הנתונים: כל ה-SQL של TimeFlow נמצא כאן.

כללים:
- כל פונקציה שנוגעת בנתונים אישיים מקבלת user_id ומסננת לפיו. כך משתמשת אחת
  לא יכולה לקרוא, לשנות או למחוק נתונים של משתמשת אחרת, גם אם תנחש מזהה.
- כל הערכים עוברים כפרמטרים (?) ולא בשרשור מחרוזות, ולכן אין SQL injection.
- הפונקציות מחזירות dict רגיל, כדי שהלוגיקה לא תהיה תלויה ב-sqlite3.
"""
import json
import sqlite3

from . import clock

SETTINGS_FIELDS = {
    "lang", "theme", "reduce_motion", "sound_pref", "timer_chime", "focus_minutes",
    "short_break_minutes", "long_break_minutes", "notifications", "calm_mode",
    "pulse_enabled", "learning_enabled", "learning_consent_at", "ai_enabled",
    "daily_email", "daily_email_at", "goal_text",
}
TASK_FIELDS = {"title", "details", "tag", "priority", "due_date", "due_time"}
NOTE_FIELDS = {"body", "color", "tag"}


def _dict(row):
    return dict(row) if row is not None else None


def _dicts(rows):
    return [dict(row) for row in rows]


class Repository:
    def __init__(self, conn):
        self.conn = conn

    def _one(self, sql, params=()):
        return _dict(self.conn.execute(sql, params).fetchone())

    def _all(self, sql, params=()):
        return _dicts(self.conn.execute(sql, params).fetchall())

    def _write(self, sql, params=()):
        with self.conn:
            return self.conn.execute(sql, params)

    # ---------- משתמשות ----------
    def create_user(self, email, display_name, password_hash, lang="he"):
        now = clock.now_iso()
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO users (email, display_name, password_hash, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?)", (email, display_name, password_hash, now, now))
            user_id = cur.lastrowid
            self.conn.execute("INSERT INTO user_settings (user_id, lang, updated_at) VALUES (?, ?, ?)",
                              (user_id, lang, now))
            self.conn.execute("INSERT INTO journey_state (user_id) VALUES (?)", (user_id,))
        return user_id

    def get_user(self, user_id):
        return self._one("SELECT * FROM users WHERE id = ?", (user_id,))

    def get_user_by_email(self, email):
        return self._one("SELECT * FROM users WHERE email = ?", (email,))

    def set_password(self, user_id, password_hash):
        self._write("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                    (password_hash, clock.now_iso(), user_id))

    def mark_email_verified(self, user_id, email):
        # מאמתים רק אם המייל לא השתנה מאז ששלחנו את הקישור
        cur = self._write("UPDATE users SET email_verified_at = ?, updated_at = ? WHERE id = ? AND email = ?",
                          (clock.now_iso(), clock.now_iso(), user_id, email))
        return cur.rowcount == 1

    def update_display_name(self, user_id, display_name):
        self._write("UPDATE users SET display_name = ?, updated_at = ? WHERE id = ?",
                    (display_name, clock.now_iso(), user_id))

    def delete_user(self, user_id):
        # כל הנתונים האישיים נמחקים יחד עם המשתמשת (ON DELETE CASCADE)
        self._write("DELETE FROM users WHERE id = ?", (user_id,))

    # ---------- הגדרות ----------
    def get_settings(self, user_id):
        return self._one("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))

    def update_settings(self, user_id, **fields):
        fields = {key: value for key, value in fields.items() if key in SETTINGS_FIELDS}
        if not fields:
            return
        columns = ", ".join(f"{key} = ?" for key in fields)
        self._write(f"UPDATE user_settings SET {columns}, updated_at = ? WHERE user_id = ?",
                    (*fields.values(), clock.now_iso(), user_id))

    # ---------- משימות ----------
    def list_tasks(self, user_id, status=None, tag=None):
        sql = "SELECT * FROM tasks WHERE user_id = ?"
        params = [user_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        if tag:
            sql += " AND tag = ?"
            params.append(tag)
        return self._all(sql + " ORDER BY id", params)

    def get_task(self, user_id, task_id):
        return self._one("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))

    def create_task(self, user_id, title, tag="", priority="normal", due_date=None, due_time=None,
                    details="", source="manual"):
        now = clock.now_iso()
        cur = self._write(
            "INSERT INTO tasks (user_id, title, details, tag, priority, due_date, due_time, source,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, title, details, tag, priority, due_date, due_time, source, now, now))
        return cur.lastrowid

    def update_task(self, user_id, task_id, **fields):
        fields = {key: value for key, value in fields.items() if key in TASK_FIELDS}
        if not fields:
            return False
        columns = ", ".join(f"{key} = ?" for key in fields)
        cur = self._write(f"UPDATE tasks SET {columns}, updated_at = ? WHERE id = ? AND user_id = ?",
                          (*fields.values(), clock.now_iso(), task_id, user_id))
        return cur.rowcount == 1

    def set_task_done(self, user_id, task_id, done):
        now = clock.now_iso()
        if done:
            cur = self._write(
                "UPDATE tasks SET status = 'done', completed_at = ?, started_at = COALESCE(started_at, ?),"
                " updated_at = ? WHERE id = ? AND user_id = ? AND status = 'open'",
                (now, now, now, task_id, user_id))
        else:
            cur = self._write(
                "UPDATE tasks SET status = 'open', completed_at = NULL, updated_at = ?"
                " WHERE id = ? AND user_id = ? AND status = 'done'", (now, task_id, user_id))
        return cur.rowcount == 1

    def mark_task_started(self, user_id, task_id):
        # "התחלה" = הצעד הראשון הושלם או שהתחיל סשן מיקוד. משמש למדד "שיעור התחלת משימות"
        self._write("UPDATE tasks SET started_at = ? WHERE id = ? AND user_id = ? AND started_at IS NULL",
                    (clock.now_iso(), task_id, user_id))

    def snooze_task(self, user_id, task_id, due_date, due_time):
        cur = self._write(
            "UPDATE tasks SET due_date = ?, due_time = ?, snooze_count = snooze_count + 1, updated_at = ?"
            " WHERE id = ? AND user_id = ?", (due_date, due_time, clock.now_iso(), task_id, user_id))
        return cur.rowcount == 1

    def delete_task(self, user_id, task_id):
        cur = self._write("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
        return cur.rowcount == 1

    def task_tags_in_use(self, user_id):
        return [row["tag"] for row in self._all(
            "SELECT DISTINCT tag FROM tasks WHERE user_id = ? AND tag != '' ORDER BY tag", (user_id,))]

    # ---------- צעדים ----------
    def steps_for_tasks(self, user_id, task_ids):
        # מחזיר {task_id: [צעדים]} בשאילתה אחת
        result = {task_id: [] for task_id in task_ids}
        if not task_ids:
            return result
        marks = ",".join("?" * len(task_ids))
        for step in self._all(f"SELECT * FROM task_steps WHERE user_id = ? AND task_id IN ({marks}) ORDER BY id",
                              (user_id, *task_ids)):
            result[step["task_id"]].append(step)
        return result

    def get_step(self, user_id, task_id, step_id):
        return self._one("SELECT * FROM task_steps WHERE id = ? AND task_id = ? AND user_id = ?",
                         (step_id, task_id, user_id))

    def add_step(self, user_id, task_id, title):
        if not self.get_task(user_id, task_id):
            return None
        now = clock.now_iso()
        cur = self._write("INSERT INTO task_steps (task_id, user_id, title, created_at, updated_at)"
                          " VALUES (?, ?, ?, ?, ?)", (task_id, user_id, title, now, now))
        return cur.lastrowid

    def set_step_done(self, user_id, task_id, step_id, done):
        now = clock.now_iso()
        cur = self._write("UPDATE task_steps SET done_at = ?, updated_at = ? WHERE id = ? AND task_id = ? AND user_id = ?",
                          (now if done else None, now, step_id, task_id, user_id))
        return cur.rowcount == 1

    def delete_step(self, user_id, task_id, step_id):
        cur = self._write("DELETE FROM task_steps WHERE id = ? AND task_id = ? AND user_id = ?",
                          (step_id, task_id, user_id))
        return cur.rowcount == 1

    # ---------- פתקים ----------
    def list_notes(self, user_id, tag=None):
        if tag:
            return self._all("SELECT * FROM notes WHERE user_id = ? AND tag = ? ORDER BY id DESC", (user_id, tag))
        return self._all("SELECT * FROM notes WHERE user_id = ? ORDER BY id DESC", (user_id,))

    def get_note(self, user_id, note_id):
        return self._one("SELECT * FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))

    def create_note(self, user_id, body, color="yellow", tag=""):
        now = clock.now_iso()
        cur = self._write("INSERT INTO notes (user_id, body, color, tag, created_at, updated_at)"
                          " VALUES (?, ?, ?, ?, ?, ?)", (user_id, body, color, tag, now, now))
        return cur.lastrowid

    def update_note(self, user_id, note_id, **fields):
        fields = {key: value for key, value in fields.items() if key in NOTE_FIELDS}
        if not fields:
            return False
        columns = ", ".join(f"{key} = ?" for key in fields)
        cur = self._write(f"UPDATE notes SET {columns}, updated_at = ? WHERE id = ? AND user_id = ?",
                          (*fields.values(), clock.now_iso(), note_id, user_id))
        return cur.rowcount == 1

    def delete_note(self, user_id, note_id):
        cur = self._write("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
        return cur.rowcount == 1

    def note_tags(self, user_id):
        return [row["tag"] for row in self._all(
            "SELECT DISTINCT tag FROM notes WHERE user_id = ? AND tag != '' ORDER BY tag", (user_id,))]

    # ---------- סשנים של מיקוד והפסקה ----------
    def active_session(self, user_id):
        return self._one("SELECT * FROM focus_sessions WHERE user_id = ? AND status IN ('running', 'paused')",
                         (user_id,))

    def get_session(self, user_id, session_id):
        return self._one("SELECT * FROM focus_sessions WHERE id = ? AND user_id = ?", (session_id, user_id))

    def create_session(self, user_id, kind, planned_seconds, task_id=None):
        # האינדקס הייחודי במסד מונע סשן פעיל שני (מחזיר None במקרה כזה)
        now = clock.now_iso()
        try:
            cur = self._write(
                "INSERT INTO focus_sessions (user_id, task_id, kind, planned_seconds, started_at, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)", (user_id, task_id, kind, planned_seconds, now, now, now))
        except sqlite3.IntegrityError:
            return None
        return cur.lastrowid

    def pause_session(self, user_id, session_id, paused_at):
        cur = self._write("UPDATE focus_sessions SET status = 'paused', paused_at = ?, updated_at = ?"
                          " WHERE id = ? AND user_id = ? AND status = 'running'",
                          (paused_at, clock.now_iso(), session_id, user_id))
        return cur.rowcount == 1

    def resume_session(self, user_id, session_id, extra_paused_seconds):
        cur = self._write("UPDATE focus_sessions SET status = 'running', paused_at = NULL,"
                          " paused_seconds = paused_seconds + ?, updated_at = ?"
                          " WHERE id = ? AND user_id = ? AND status = 'paused'",
                          (extra_paused_seconds, clock.now_iso(), session_id, user_id))
        return cur.rowcount == 1

    def finish_session(self, user_id, session_id, status, ended_at, actual_seconds):
        # מעבר מ"פעיל" ל"הסתיים" קורה פעם אחת בלבד. קריאה שנייה מחזירה False ולא סופרת שוב
        cur = self._write("UPDATE focus_sessions SET status = ?, ended_at = ?, actual_seconds = ?, paused_at = NULL,"
                          " updated_at = ? WHERE id = ? AND user_id = ? AND status IN ('running', 'paused')",
                          (status, ended_at, actual_seconds, clock.now_iso(), session_id, user_id))
        return cur.rowcount == 1

    def set_session_task(self, user_id, session_id, task_id):
        self._write("UPDATE focus_sessions SET task_id = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                    (task_id, clock.now_iso(), session_id, user_id))

    def sessions_between(self, user_id, start_iso, end_iso):
        return self._all("SELECT * FROM focus_sessions WHERE user_id = ? AND started_at >= ? AND started_at < ?"
                         " ORDER BY started_at", (user_id, start_iso, end_iso))

    def last_finished_session(self, user_id):
        return self._one("SELECT * FROM focus_sessions WHERE user_id = ? AND status IN ('completed', 'stopped')"
                         " ORDER BY id DESC LIMIT 1", (user_id,))

    # ---------- מסע הכדור הפורח ----------
    def add_journey_event(self, user_id, kind, ref_id, points):
        # INSERT OR IGNORE + UNIQUE: אותו פריט לא נספר פעמיים
        cur = self._write("INSERT OR IGNORE INTO journey_events (user_id, kind, ref_id, points, created_at)"
                          " VALUES (?, ?, ?, ?, ?)", (user_id, kind, ref_id, points, clock.now_iso()))
        return cur.rowcount == 1

    def remove_journey_event(self, user_id, kind, ref_id):
        self._write("DELETE FROM journey_events WHERE user_id = ? AND kind = ? AND ref_id = ?",
                    (user_id, kind, ref_id))

    def journey_points(self, user_id, start_iso=None, end_iso=None):
        sql = "SELECT COALESCE(SUM(points), 0) AS total FROM journey_events WHERE user_id = ?"
        params = [user_id]
        if start_iso:
            sql += " AND created_at >= ? AND created_at < ?"
            params += [start_iso, end_iso]
        return self._one(sql, params)["total"]

    def get_shown_points(self, user_id):
        row = self._one("SELECT shown_points FROM journey_state WHERE user_id = ?", (user_id,))
        return row["shown_points"] if row else 0

    def set_shown_points(self, user_id, points):
        self._write("INSERT INTO journey_state (user_id, shown_points) VALUES (?, ?)"
                    " ON CONFLICT(user_id) DO UPDATE SET shown_points = excluded.shown_points", (user_id, points))

    # ---------- Daily Pulse ----------
    def get_pulse(self, user_id, day):
        return self._one("SELECT * FROM daily_pulse WHERE user_id = ? AND day = ?", (user_id, day))

    def save_pulse(self, user_id, day, rating, reasons, skipped=False):
        now = clock.now_iso()
        self._write(
            "INSERT INTO daily_pulse (user_id, day, rating, reasons, skipped, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(user_id, day) DO UPDATE SET rating = excluded.rating,"
            " reasons = excluded.reasons, skipped = excluded.skipped, updated_at = excluded.updated_at",
            (user_id, day, rating, reasons, int(skipped), now, now))

    def pulses_since(self, user_id, first_day):
        return self._all("SELECT * FROM daily_pulse WHERE user_id = ? AND day >= ? ORDER BY day",
                         (user_id, first_day))

    # ---------- תובנות ----------
    def record_insight(self, user_id, rule_id, status, evidence):
        now = clock.now_iso()
        self._write("INSERT INTO insights (user_id, rule_id, evidence, status, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, rule_id, json.dumps(evidence, ensure_ascii=False), status, now, now))

    def insight_feedback(self, user_id):
        return self._all("SELECT rule_id, status, created_at FROM insights WHERE user_id = ? ORDER BY id",
                         (user_id,))

    # ---------- צלילים ----------
    def add_sound_feedback(self, user_id, space, helped):
        self._write("INSERT INTO sound_feedback (user_id, space, helped, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, space, int(helped), clock.now_iso()))

    def sound_feedback_counts(self, user_id):
        counts = {}
        for row in self._all("SELECT space, SUM(helped) AS yes, COUNT(*) AS total FROM sound_feedback"
                             " WHERE user_id = ? GROUP BY space", (user_id,)):
            counts[row["space"]] = {"yes": row["yes"], "no": row["total"] - row["yes"], "total": row["total"]}
        return counts

    # ---------- Snooze ----------
    def list_snooze_entries(self, user_id):
        return self._all("SELECT * FROM snooze_entries WHERE user_id = ? ORDER BY id DESC", (user_id,))

    def get_snooze_entry(self, user_id, entry_id):
        return self._one("SELECT * FROM snooze_entries WHERE id = ? AND user_id = ?", (entry_id, user_id))

    def create_snooze_entry(self, user_id, body):
        now = clock.now_iso()
        cur = self._write("INSERT INTO snooze_entries (user_id, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
                          (user_id, body, now, now))
        return cur.lastrowid

    def update_snooze_entry(self, user_id, entry_id, **fields):
        allowed = {key: value for key, value in fields.items() if key in {"bucket", "task_id", "ai_reply"}}
        if not allowed:
            return False
        columns = ", ".join(f"{key} = ?" for key in allowed)
        cur = self._write(f"UPDATE snooze_entries SET {columns}, updated_at = ? WHERE id = ? AND user_id = ?",
                          (*allowed.values(), clock.now_iso(), entry_id, user_id))
        return cur.rowcount == 1

    def delete_snooze_entry(self, user_id, entry_id):
        cur = self._write("DELETE FROM snooze_entries WHERE id = ? AND user_id = ?", (entry_id, user_id))
        return cur.rowcount == 1

    # ---------- AI ----------
    def log_ai_request(self, user_id, purpose, provider, status):
        self._write("INSERT INTO ai_requests (user_id, purpose, provider, status, created_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, purpose, provider, status, clock.now_iso()))

    def count_ai_requests(self, user_id, since_iso, purpose=None, external_only=True):
        # להגבלת השימוש סופרים רק קריאות שבאמת יצאו לספק (לא הצעות בסיסיות)
        sql = "SELECT COUNT(*) AS n FROM ai_requests WHERE user_id = ? AND created_at >= ?"
        params = [user_id, since_iso]
        if external_only:
            sql += " AND status IN ('ok', 'error', 'refused')"
        if purpose:
            sql += " AND purpose = ?"
            params.append(purpose)
        return self._one(sql, params)["n"]

    # ---------- מיילים ----------
    def claim_daily_email(self, user_id, day):
        # "תופסים" את השליחה במסד לפני השליחה עצמה. אם כבר יש רשומה להיום, לא שולחים שוב
        now = clock.now_iso()
        cur = self._write("INSERT OR IGNORE INTO email_log (user_id, kind, day, status, created_at, updated_at)"
                          " VALUES (?, 'daily', ?, 'sending', ?, ?)", (user_id, day, now, now))
        if cur.rowcount == 1:
            return cur.lastrowid
        return None

    def retry_daily_email(self, user_id, day, max_attempts):
        # ניסיון חוזר רק לשליחה שנכשלה, ורק עד מספר ניסיונות מוגבל
        cur = self._write("UPDATE email_log SET status = 'sending', attempts = attempts + 1, updated_at = ?"
                          " WHERE user_id = ? AND kind = 'daily' AND day = ? AND status = 'failed' AND attempts < ?",
                          (clock.now_iso(), user_id, day, max_attempts))
        if cur.rowcount != 1:
            return None
        return self._one("SELECT id FROM email_log WHERE user_id = ? AND kind = 'daily' AND day = ?",
                         (user_id, day))["id"]

    def log_email(self, user_id, kind, status, error=""):
        now = clock.now_iso()
        cur = self._write("INSERT INTO email_log (user_id, kind, status, error, created_at, updated_at)"
                          " VALUES (?, ?, ?, ?, ?, ?)", (user_id, kind, status, error[:200], now, now))
        return cur.lastrowid

    def finish_email(self, log_id, status, error=""):
        self._write("UPDATE email_log SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                    (status, error[:200], clock.now_iso(), log_id))

    def daily_email_status(self, user_id, day):
        return self._one("SELECT * FROM email_log WHERE user_id = ? AND kind = 'daily' AND day = ?", (user_id, day))

    def users_with_daily_email(self):
        return self._all("SELECT u.id, u.email, u.display_name, s.lang, s.daily_email_at FROM users u"
                         " JOIN user_settings s ON s.user_id = u.id"
                         " WHERE s.daily_email = 1 AND u.email_verified_at IS NOT NULL")

    def count_emails(self, user_id, kind, since_iso):
        return self._one("SELECT COUNT(*) AS n FROM email_log WHERE user_id = ? AND kind = ? AND created_at >= ?",
                         (user_id, kind, since_iso))["n"]

    # ---------- ניסיונות התחברות ----------
    def record_login_attempt(self, email, ip, success):
        self._write("INSERT INTO login_attempts (email, ip, success, created_at) VALUES (?, ?, ?, ?)",
                    (email.lower(), ip, int(success), clock.now_iso()))

    def failed_logins(self, since_iso, email=None, ip=None):
        if email is not None:
            return self._one("SELECT COUNT(*) AS n FROM login_attempts WHERE email = ? AND success = 0 AND created_at >= ?",
                             (email.lower(), since_iso))["n"]
        return self._one("SELECT COUNT(*) AS n FROM login_attempts WHERE ip = ? AND success = 0 AND created_at >= ?",
                         (ip, since_iso))["n"]

    def clear_old_login_attempts(self, before_iso):
        self._write("DELETE FROM login_attempts WHERE created_at < ?", (before_iso,))

    # ---------- Google Calendar ----------
    def get_google_account(self, user_id):
        return self._one("SELECT * FROM google_accounts WHERE user_id = ?", (user_id,))

    def save_google_account(self, user_id, access_token, refresh_token, expires_at, scope):
        now = clock.now_iso()
        self._write(
            "INSERT INTO google_accounts (user_id, access_token, refresh_token, expires_at, scope, connected_at)"
            " VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET access_token = excluded.access_token,"
            " refresh_token = COALESCE(excluded.refresh_token, google_accounts.refresh_token),"
            " expires_at = excluded.expires_at, scope = excluded.scope, last_error = ''",
            (user_id, access_token, refresh_token, expires_at, scope, now))

    def update_google_sync(self, user_id, last_sync_at=None, last_error=""):
        if last_sync_at:
            self._write("UPDATE google_accounts SET last_sync_at = ?, last_error = '' WHERE user_id = ?",
                        (last_sync_at, user_id))
        else:
            self._write("UPDATE google_accounts SET last_error = ? WHERE user_id = ?", (last_error[:200], user_id))

    def delete_google_account(self, user_id):
        with self.conn:
            self.conn.execute("DELETE FROM google_accounts WHERE user_id = ?", (user_id,))
            self.conn.execute("DELETE FROM calendar_events WHERE user_id = ?", (user_id,))

    def upsert_calendar_event(self, user_id, google_id, summary, starts_at, ends_at, all_day):
        # UNIQUE(user_id, google_id): סנכרון חוזר מעדכן את האירוע ולא יוצר כפילות
        self._write(
            "INSERT INTO calendar_events (user_id, google_id, summary, starts_at, ends_at, all_day, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(user_id, google_id) DO UPDATE SET summary = excluded.summary,"
            " starts_at = excluded.starts_at, ends_at = excluded.ends_at, all_day = excluded.all_day,"
            " updated_at = excluded.updated_at",
            (user_id, google_id, summary, starts_at, ends_at, int(all_day), clock.now_iso()))

    def remove_calendar_events_not_in(self, user_id, start_iso, end_iso, keep_ids):
        # אירוע שנמחק ב-Google נמחק גם כאן (רק בטווח שסונכרן)
        rows = self._all("SELECT id, google_id FROM calendar_events WHERE user_id = ? AND starts_at >= ? AND starts_at < ?",
                         (user_id, start_iso, end_iso))
        for row in rows:
            if row["google_id"] not in keep_ids:
                self._write("DELETE FROM calendar_events WHERE id = ? AND user_id = ?", (row["id"], user_id))

    def calendar_events_between(self, user_id, start_iso, end_iso):
        return self._all("SELECT * FROM calendar_events WHERE user_id = ? AND starts_at >= ? AND starts_at < ?"
                         " ORDER BY starts_at", (user_id, start_iso, end_iso))

    def get_calendar_event(self, user_id, event_id):
        return self._one("SELECT * FROM calendar_events WHERE id = ? AND user_id = ?", (event_id, user_id))

    def link_event_to_task(self, user_id, event_id, task_id):
        # רק אירוע שעוד לא קושר. כך אותו אירוע לא הופך למשימה פעמיים
        cur = self._write("UPDATE calendar_events SET task_id = ? WHERE id = ? AND user_id = ? AND task_id IS NULL",
                          (task_id, event_id, user_id))
        return cur.rowcount == 1

    # ---------- פרטיות: ייצוא ומחיקה ----------
    def export_user_data(self, user_id):
        user = self.get_user(user_id)
        user.pop("password_hash", None)
        data = {"user": user, "settings": self.get_settings(user_id)}
        for table in ("tasks", "task_steps", "notes", "focus_sessions", "journey_events", "daily_pulse",
                      "insights", "sound_feedback", "snooze_entries", "ai_requests", "email_log", "calendar_events"):
            data[table] = self._all(f"SELECT * FROM {table} WHERE user_id = ? ORDER BY id", (user_id,))
        account = self.get_google_account(user_id)
        data["google_calendar"] = {"connected": bool(account),
                                   "scope": account["scope"] if account else None,
                                   "connected_at": account["connected_at"] if account else None}
        return data

    def delete_learning_data(self, user_id):
        # נתוני הלמידה: משוב יומי, תובנות, משוב על צלילים. המשימות והסשנים נשארים
        with self.conn:
            for table in ("daily_pulse", "insights", "sound_feedback"):
                self.conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
