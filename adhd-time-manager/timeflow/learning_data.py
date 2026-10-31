"""מכין את ההיסטוריה למנוע ההתאמה האישית מתוך המסד.

זה הקובץ היחיד שמחבר בין המסד למנוע. המנוע עצמו לא יודע מה זה SQL.
"""
from datetime import timedelta

from . import clock
from .personalization_engine import DayRecord, History, SessionRecord, TaskRecord

WINDOW_DAYS = 30


def build_history(repo, user_id, settings, today=None):
    today = today or clock.today()
    first = today - timedelta(days=WINDOW_DAYS - 1)
    start_iso, _ = clock.day_bounds(first)
    _, end_iso = clock.day_bounds(today)

    sessions = repo.sessions_between(user_id, start_iso, end_iso)
    pulses = {p["day"]: p for p in repo.pulses_since(user_id, first.isoformat())}
    tasks = [t for t in repo.list_tasks(user_id) if t["created_at"] >= start_iso]
    steps = repo.steps_for_tasks(user_id, [t["id"] for t in tasks])

    days = []
    for offset in range(WINDOW_DAYS):
        day = first + timedelta(days=offset)
        day_start, day_end = clock.day_bounds(day)
        focus = [s for s in sessions if s["kind"] == "focus" and day_start <= s["started_at"] < day_end
                 and s["status"] in ("completed", "stopped")]
        planned = [s["planned_seconds"] for s in focus if s["planned_seconds"]]
        pulse = pulses.get(day.isoformat())
        planned_tasks = sum(1 for t in tasks if t["due_date"] == day.isoformat()
                            or (not t["due_date"] and day_start <= t["created_at"] < day_end))
        days.append(DayRecord(
            day=day,
            rating=pulse["rating"] if pulse and not pulse["skipped"] else None,
            reasons=tuple(r for r in (pulse["reasons"] if pulse else "").split(",") if r),
            focus_sessions=len(focus),
            small_start=bool(focus) and 0 < (focus[0]["planned_seconds"] or 0) <= 10 * 60,
            avg_planned_minutes=round(sum(planned) / len(planned) / 60, 1) if planned else None,
            planned_tasks=planned_tasks,
            focus_seconds=sum(s["actual_seconds"] or 0 for s in focus),
            planned_seconds=sum(planned),
        ))

    since_help = clock.to_iso(clock.now() - timedelta(days=14))
    return History(
        today=today,
        days=days,
        tasks=[TaskRecord(t["id"], bool(steps.get(t["id"])), bool(t["started_at"] or t["status"] == "done"),
                          t["snooze_count"], t["status"]) for t in tasks],
        sessions=[SessionRecord(s["kind"], s["planned_seconds"], s["status"], clock.from_iso(s["started_at"]),
                                clock.from_iso(s["ended_at"])) for s in sessions],
        sound_feedback=repo.sound_feedback_counts(user_id),
        start_help_requests=repo.count_ai_requests(user_id, since_help, purpose="start_help", external_only=False),
        feedback=[(f["rule_id"], f["status"], clock.from_iso(f["created_at"]).date()) for f in repo.insight_feedback(user_id)],
        settings=dict(settings),
    )
