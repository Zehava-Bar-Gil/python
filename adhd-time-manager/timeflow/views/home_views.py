"""מסך הבית: "עכשיו" (צעד אחד ופעולה אחת), "התכנון שלי" מתחת, והמסע על ההר."""
from flask import g

from .. import clock, focus_timer, journey, personalization_engine, planner, ui
from ..learning_data import build_history
from . import back, bp, form_text, page, repo, say, tr, uid

HOME_TASKS = 5
HOME_NOTES = 4


def todays_agenda(user_id, day, tasks):
    # משימות עם שעה להיום, ואירועי Google של היום (אם היומן מחובר)
    start, end = clock.day_bounds(day)
    items = [{"time": t["due_time"], "title": t["title"], "tag": t["tag"], "done": t["status"] == "done",
              "kind": "task"} for t in tasks if t["due_time"] and (t["due_date"] or day.isoformat()) == day.isoformat()]
    for event in repo().calendar_events_between(user_id, start, end):
        items.append({"time": "" if event["all_day"] else clock.from_iso(event["starts_at"]).strftime("%H:%M"),
                      "title": event["summary"], "tag": "", "done": False, "kind": "google"})
    return sorted(items, key=lambda item: item["time"] or "00:00")


def pulse_prompt(settings, user_id, now):
    # השאלה היומית מוצגת רק אם היא פעילה, אחרי 17:00, ורק אם עוד לא נענתה היום
    if not settings["pulse_enabled"] or now.hour < ui.PULSE_AFTER_HOUR:
        return None
    if repo().get_pulse(user_id, now.date().isoformat()):
        return None
    return {"day": now.date().isoformat()}


def current_insight(settings, user_id):
    if not settings["learning_enabled"]:
        return None
    return personalization_engine.choose(build_history(repo(), user_id, settings))


@bp.route("")
def home():
    r, user_id, settings, now = repo(), uid(), g.settings, clock.now()
    t = tr()
    tasks = r.list_tasks(user_id)
    open_list = planner.open_tasks(tasks)
    shown = open_list[:HOME_TASKS]
    planner.attach_steps(shown, r.steps_for_tasks(user_id, [task["id"] for task in shown]))
    session_state = focus_timer.state(r.active_session(user_id), now)
    active_task = r.get_task(user_id, session_state["task_id"]) if session_state.get("task_id") else None

    # התראות שקטות: "שקט" = לכל היותר פריט אחד שמבקש תשומת לב, "כבוי" = אף אחד
    notify = settings["notifications"]
    pulse = insight = None
    if notify != "off" and not settings["calm_mode"]:
        pulse = pulse_prompt(settings, user_id, now)
        if notify == "normal" or not pulse:
            insight = current_insight(settings, user_id)

    stats = focus_timer.day_stats(r, user_id, now.date())
    trip = journey.view(r, user_id)
    in_climb = trip["points"] % journey.POINTS_PER_CLIMB
    return page(
        "zehava/index.html", active="home",
        greeting=ui.greeting(t, now.hour),
        next_task=shown[0] if shown else None,
        tasks=shown,
        more_open=max(0, len(open_list) - HOME_TASKS),
        has_tasks=bool(tasks),
        timer=session_state,
        active_task=active_task,
        journey=trip,
        climb_pct=100 if trip["summit_reached"] else in_climb * 100 // journey.POINTS_PER_CLIMB,
        today_points=r.journey_points(user_id, *clock.day_bounds(now.date())),
        agenda=todays_agenda(user_id, now.date(), tasks),
        notes=r.list_notes(user_id)[:HOME_NOTES],
        stats=stats,
        focus_label=ui.minutes_label(t, stats["focus_seconds"]),
        pulse=pulse,
        insight=insight,
        faces=ui.PULSE_FACES,
        today_label=f"{now.day} {t['months'][now.month - 1]} {now.year}",
    )


@bp.route("/calm", methods=["POST"])
def calm():
    # מצב רגוע: רק הצעד הבא על המסך. אותו כפתור מחזיר את התכנון
    repo().update_settings(uid(), calm_mode=0 if g.settings["calm_mode"] else 1)
    return back("zehava.home")


@bp.route("/goal", methods=["POST"])
def set_goal():
    repo().update_settings(uid(), goal_text=form_text("goal", 60))
    say("saved")
    return back("zehava.home")
