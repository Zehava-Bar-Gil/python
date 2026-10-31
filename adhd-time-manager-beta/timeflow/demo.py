"""משתמשת הדגמה עם נתונים סינתטיים, להצגה בכיתה ולבדיקה ידנית. אין כאן נתונים אמיתיים."""
import random
from datetime import datetime, time, timedelta

from werkzeug.security import generate_password_hash

from . import clock, journey
from .db import connect
from .repository import Repository

DEMO_EMAIL = "demo@timeflow.local"
DEMO_PASSWORD = "timeflow-demo"
DAYS = 21
KEEP_OPEN_DAYS = 3      # משימות פתוחות מימים ישנים יותר "הושלמו" יום אחרי, כמו שקורה בחיים

TASKS = ["לסכם את פרק 3", "לשלוח מייל למרצה", "לקנות מתנה לאמא", "להכין מצגת לפרויקט", "לסדר את השולחן",
         "לקבוע תור לרופא", "לתרגל SQL", "לקרוא מאמר על Flask", "לכבס", "לתכנן את השבוע הבא"]
STEPS = ["לפתוח את הקובץ", "לכתוב משפט ראשון", "לעבור על ההערות"]


def seed_demo(app, seed=7):
    rng = random.Random(seed)
    conn = connect(app.config["DATABASE"])
    repo = Repository(conn)
    try:
        old = repo.get_user_by_email(DEMO_EMAIL)
        if old:
            repo.delete_user(old["id"])
        user_id = repo.create_user(DEMO_EMAIL, "Demo", generate_password_hash(DEMO_PASSWORD))
        conn.execute("UPDATE users SET email_verified_at = ? WHERE id = ?", (clock.now_iso(), user_id))
        conn.commit()
        repo.update_settings(user_id, learning_enabled=1, learning_consent_at=clock.now_iso(), goal_text="לסיים את הקורס")
        today = clock.today()
        for offset in range(DAYS, 0, -1):
            day = today - timedelta(days=offset)
            _seed_day(repo, user_id, day, rng)
        _finish_old_tasks(repo, user_id, today)
        clock.freeze(None)
        # להיום: שתי משימות עם שעה, כדי שסדר היום לא יהיה ריק בהדגמה
        for title, at_time in (("שיחה עם המנחה", "11:30"), ("ללכת לחדר כושר", "18:00")):
            repo.create_task(user_id, title, tag="personal" if at_time == "18:00" else "study",
                             due_date=today.isoformat(), due_time=at_time)
        for text, color in (("רעיון: לנסות ללמוד בספרייה", "yellow"), ("לא לשכוח מטען", "pink")):
            repo.create_note(user_id, text, color)
        repo.create_snooze_entry(user_id, "יש לי מלא דברים בראש, המבחן, העבודה והכביסה")
        return DEMO_EMAIL, DEMO_PASSWORD
    finally:
        clock.freeze(None)
        conn.close()


def _seed_day(repo, user_id, day, rng):
    def at(hour, minute=0):
        clock.freeze(datetime.combine(day, time(hour, minute), clock.LOCAL_TZ))

    at(9)
    small_day = rng.random() < 0.5
    task_ids = []
    for title in rng.sample(TASKS, rng.randint(2, 7)):
        task_ids.append(repo.create_task(user_id, title, tag=rng.choice(["work", "study", "home", ""]),
                                         due_date=day.isoformat()))
    if rng.random() < 0.6:
        for title in STEPS[:rng.randint(1, 3)]:
            repo.add_step(user_id, task_ids[0], title)
    # סשנים: ביום "קטן" הסשן הראשון קצר (10 דק'), אחרת ארוך
    hour = 10
    for index in range(rng.randint(1, 4)):
        at(hour)
        minutes = 10 if small_day and index == 0 else rng.choice([15, 25, 45])
        session_id = repo.create_session(user_id, "focus", minutes * 60, task_ids[0])
        finished = rng.random() < (0.85 if minutes <= 15 else 0.5)
        end = clock.now() + timedelta(minutes=minutes if finished else minutes // 2)
        repo.finish_session(user_id, session_id, "completed" if finished else "stopped", clock.to_iso(end),
                            minutes * 60 if finished else minutes * 30)
        if finished:
            journey.record(repo, user_id, "session", session_id)
        hour += 2
    at(18)
    for task_id in task_ids[:rng.randint(0, len(task_ids))]:
        if repo.set_task_done(user_id, task_id, True):
            journey.record(repo, user_id, "task", task_id)
    rating = min(5, max(1, rng.randint(2, 4) + (1 if small_day else 0)))
    reasons = ["tired"] if len(task_ids) > 5 and rng.random() < 0.7 else (["focused"] if small_day else [])
    repo.save_pulse(user_id, day.isoformat(), rating, ",".join(reasons))
    if rng.random() < 0.3:
        repo.add_sound_feedback(user_id, "calm", rng.random() < 0.8)


def _finish_old_tasks(repo, user_id, today):
    # מה שנשאר פתוח מלפני יותר מ-3 ימים הושלם למחרת. שתי משימות נדחו כמה פעמים ונשארו פתוחות
    cutoff = (today - timedelta(days=KEEP_OPEN_DAYS)).isoformat()
    old = [t for t in repo.list_tasks(user_id, status="open") if t["due_date"] < cutoff]
    for task in old[:-2]:
        next_day = clock.parse_day(task["due_date"]) + timedelta(days=1)
        clock.freeze(datetime.combine(next_day, time(12), clock.LOCAL_TZ))
        if repo.set_task_done(user_id, task["id"], True):
            journey.record(repo, user_id, "task", task["id"])
    clock.freeze(datetime.combine(today, time(8), clock.LOCAL_TZ))
    for task in old[-2:]:
        for _ in range(3):
            repo.snooze_task(user_id, task["id"], today.isoformat(), None)
