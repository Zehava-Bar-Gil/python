"""הטיימר: סשן מיקוד או הפסקה, עם השהיה, המשך, איפוס והפסקות.

השרת הוא מקור האמת לזמן. הדפדפן רק מציג ספירה לאחור ב-CSS, והדף מתרענן כשהזמן נגמר.
סשן שהזמן שלו עבר נסגר "בעצלות" בבקשה הבאה, בעדכון אטומי אחד: גם אם שתי לשוניות
מתרעננות יחד, הסשן נספר פעם אחת בלבד.
"""
from datetime import timedelta

from . import clock, journey

KINDS = ("focus", "short_break", "long_break")
QUICK_MINUTES = [5, 15, 25, 45, 60]
LONG_BREAK_EVERY = 4            # אחרי כל 4 סשנים שהושלמו מציעים הפסקה ארוכה
FLEXIBLE_MIN_POINT = 5 * 60     # סשן גמיש נספר במסע אם נמשך לפחות 5 דקות
RING = 339.3                    # היקף הטבעת ב-SVG


def elapsed_seconds(session, now):
    end = clock.from_iso(session["paused_at"]) or now
    spent = (end - clock.from_iso(session["started_at"])).total_seconds() - session["paused_seconds"]
    return max(0, int(spent))


def remaining_seconds(session, now):
    if not session["planned_seconds"]:
        return None
    return max(0, session["planned_seconds"] - elapsed_seconds(session, now))


def is_due(session, now):
    return (session["status"] == "running" and session["planned_seconds"] > 0
            and elapsed_seconds(session, now) >= session["planned_seconds"])


def state(session, now):
    # כל מה שהתבנית צריכה כדי לצייר את הטבעת והספירה
    if not session:
        return {"active": False}
    remaining = remaining_seconds(session, now)
    planned = session["planned_seconds"]
    ends = now + timedelta(seconds=remaining) if remaining is not None else None
    return {
        "active": True,
        "id": session["id"],
        "kind": session["kind"],
        "task_id": session["task_id"],
        "running": session["status"] == "running",
        "paused": session["status"] == "paused",
        "flexible": planned == 0,
        "planned": planned,
        "elapsed": elapsed_seconds(session, now),
        "remaining": remaining,
        "ends_at": ends.strftime("%H:%M") if ends and session["status"] == "running" else "",
        "ring_from": round((planned - remaining) / planned * RING, 1) if planned else 0,
    }


def start(repo, user_id, kind, minutes, task_id=None):
    # מחזיר את מזהה הסשן, או None אם כבר יש סשן פעיל
    if kind not in KINDS or not 0 <= minutes <= 180:
        return None
    if task_id is not None and not repo.get_task(user_id, task_id):
        task_id = None
    session_id = repo.create_session(user_id, kind, minutes * 60, task_id)
    if session_id and kind == "focus" and task_id:
        repo.mark_task_started(user_id, task_id)
    return session_id


def _award(repo, user_id, session):
    if session["kind"] == "focus":
        journey.record(repo, user_id, "session", session["id"])


def complete_if_due(repo, user_id, now):
    # סוגר סשן שהזמן שלו נגמר. מחזיר את הסשן שהושלם עכשיו, או None
    session = repo.active_session(user_id)
    if not session or not is_due(session, now):
        return None
    ended = clock.from_iso(session["started_at"]) + timedelta(
        seconds=session["planned_seconds"] + session["paused_seconds"])
    if repo.finish_session(user_id, session["id"], "completed", clock.to_iso(ended), session["planned_seconds"]):
        _award(repo, user_id, session)
        return session
    return None


def pause(repo, user_id, now):
    session = repo.active_session(user_id)
    return bool(session) and repo.pause_session(user_id, session["id"], clock.to_iso(now))


def resume(repo, user_id, now):
    session = repo.active_session(user_id)
    if not session or session["status"] != "paused":
        return False
    extra = int((now - clock.from_iso(session["paused_at"])).total_seconds())
    return repo.resume_session(user_id, session["id"], max(0, extra))


def stop(repo, user_id, now):
    # עצירה או איפוס: הזמן שבוצע בפועל נרשם, בלי עונש. סשן גמיש שהסתיים נחשב כהושלם
    session = repo.active_session(user_id)
    if not session:
        return None
    actual = elapsed_seconds(session, now)
    flexible_done = session["planned_seconds"] == 0 and actual >= 60
    status = "completed" if flexible_done else "stopped"
    if repo.finish_session(user_id, session["id"], status, clock.to_iso(now), actual):
        if flexible_done and actual >= FLEXIBLE_MIN_POINT:
            _award(repo, user_id, session)
        return {**session, "status": status, "actual_seconds": actual}
    return None


def day_stats(repo, user_id, day):
    # זמן מתוכנן מול זמן שנמדד בפועל, רק לסשנים של מיקוד
    start_iso, end_iso = clock.day_bounds(day)
    sessions = [s for s in repo.sessions_between(user_id, start_iso, end_iso) if s["kind"] == "focus"]
    finished = [s for s in sessions if s["status"] in ("completed", "stopped")]
    return {
        "completed": sum(1 for s in finished if s["status"] == "completed"),
        "focus_seconds": sum(s["actual_seconds"] or 0 for s in finished),
        "planned_seconds": sum(s["planned_seconds"] for s in finished if s["planned_seconds"]),
    }


def break_suggestion(repo, user_id, settings, day):
    # אחרי סשן מיקוד: הפסקה קצרה, ואחרי כל ארבעה סשנים הפסקה ארוכה. רק הצעה
    completed = day_stats(repo, user_id, day)["completed"]
    if completed and completed % LONG_BREAK_EVERY == 0:
        return "long_break", settings["long_break_minutes"]
    return "short_break", settings["short_break_minutes"]
