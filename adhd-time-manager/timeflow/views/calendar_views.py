"""היומן: לוח חודשי עם המשימות, וחיבור אופציונלי ל-Google Calendar (קריאה בלבד)."""
from datetime import date

from flask import abort, current_app, redirect, request, session, url_for

from .. import clock, google_calendar, ui
from . import back, bp, page, repo, say, tr, uid

OAUTH_STATE = "google_oauth_state"


def parse_month(text, today):
    try:
        year, month = (int(part) for part in (text or "").split("-"))
        return date(year, month, 1)
    except ValueError:
        return today.replace(day=1)


@bp.route("/calendar")
def calendar():
    r, user_id, today, t = repo(), uid(), clock.today(), tr()
    first = parse_month(request.args.get("month"), today)
    selected = clock.parse_day(request.args.get("day")) or (today if first.month == today.month
                                                           and first.year == today.year else first)
    next_year, next_month = ui.shift_month(first.year, first.month, 1)
    month_start, _ = clock.day_bounds(first)
    month_end, _ = clock.day_bounds(date(next_year, next_month, 1))

    tasks = [task for task in r.list_tasks(user_id) if task["due_date"]]
    events = r.calendar_events_between(user_id, month_start, month_end)
    marks = {}
    for task in tasks:
        day = clock.parse_day(task["due_date"])
        if day and (day.year, day.month) == (first.year, first.month):
            marks[day.day] = marks.get(day.day, 0) + 1
    for event in events:
        day = clock.from_iso(event["starts_at"]).date()
        marks[day.day] = marks.get(day.day, 0) + 1

    agenda = [{"time": task["due_time"] or "", "title": task["title"], "tag": task["tag"],
               "done": task["status"] == "done", "kind": "task", "id": task["id"]}
              for task in tasks if task["due_date"] == selected.isoformat()]
    day_start, day_end = clock.day_bounds(selected)
    for event in r.calendar_events_between(user_id, day_start, day_end):
        agenda.append({"time": "" if event["all_day"] else clock.from_iso(event["starts_at"]).strftime("%H:%M"),
                       "title": event["summary"], "tag": "", "done": False, "kind": "google", "id": event["id"],
                       "linked": event["task_id"] is not None})
    agenda.sort(key=lambda item: item["time"] or "00:00")

    prev_year, prev_month = ui.shift_month(first.year, first.month, -1)
    return page("zehava/calendar.html", active="calendar",
                month_title=f"{t['months'][first.month - 1]} {first.year}",
                weeks=ui.month_grid(first.year, first.month, marks),
                month=first, today=today, selected=selected, agenda=agenda,
                prev_month=f"{prev_year}-{prev_month:02d}", next_month=f"{next_year}-{next_month:02d}",
                status=google_calendar.status(repo(), current_app.config, user_id))


@bp.route("/calendar/connect", methods=["GET", "POST"])
def calendar_connect():
    config = current_app.config
    if not google_calendar.is_configured(config):
        say("not_configured", "warn")
        return redirect(url_for("zehava.calendar"))
    if request.method == "GET":
        return page("zehava/calendar_connect.html", active="calendar")
    if request.form.get("consent") != "1":
        say("consent_required", "warn")
        return redirect(url_for("zehava.calendar_connect"))
    session[OAUTH_STATE] = google_calendar.new_state()
    return redirect(google_calendar.authorization_url(config, session[OAUTH_STATE]))


@bp.route("/calendar/oauth/callback")
def calendar_callback():
    # Google מחזיר לכאן. בודקים שה-state הוא זה ששמרנו, כדי שאתר זר לא יחבר חשבון אחר
    expected = session.pop(OAUTH_STATE, None)
    code = request.args.get("code")
    if not expected or request.args.get("state") != expected or not code or request.args.get("error"):
        say("connect_failed", "warn")
        return redirect(url_for("zehava.calendar"))
    try:
        google_calendar.exchange_code(repo(), current_app.config, uid(), code)
        google_calendar.sync(repo(), current_app.config, uid())
    except google_calendar.GoogleError:
        say("connect_failed", "warn")
        return redirect(url_for("zehava.calendar"))
    say("connected_ok")
    return redirect(url_for("zehava.calendar"))


@bp.route("/calendar/sync", methods=["POST"])
def calendar_sync():
    try:
        google_calendar.sync(repo(), current_app.config, uid())
        say("saved")
    except google_calendar.GoogleError as error:
        say("google_error" if error.kind == "auth" else "sync_failed", "warn")
    return redirect(url_for("zehava.calendar"))


@bp.route("/calendar/disconnect", methods=["POST"])
def calendar_disconnect():
    google_calendar.disconnect(repo(), current_app.config, uid())
    say("disconnected")
    return back("zehava.calendar")


@bp.route("/calendar/event/<int:event_id>/to-task", methods=["POST"])
def event_to_task(event_id):
    r, user_id = repo(), uid()
    event = r.get_calendar_event(user_id, event_id)
    if not event:
        abort(404)
    if event["task_id"]:
        say("event_linked", "warn")
        return redirect(url_for("zehava.calendar"))
    start = clock.from_iso(event["starts_at"])
    task_id = r.create_task(user_id, (event["summary"] or "Google")[:200], due_date=start.date().isoformat(),
                            due_time=None if event["all_day"] else start.strftime("%H:%M"), source="calendar")
    if not r.link_event_to_task(user_id, event_id, task_id):
        # מישהו כבר קישר את האירוע בינתיים (למשל בלשונית אחרת): לא משאירים משימה כפולה
        r.delete_task(user_id, task_id)
        say("event_linked", "warn")
    else:
        say("task_added")
    return redirect(url_for("zehava.calendar", day=start.date().isoformat()))
