"""זמן מסך: הדף עצמו, רישום דקות, יעדים, ושער הכוונה לפני פתיחת רשת חברתית."""
from datetime import timedelta

from flask import abort, redirect, request, url_for

from .. import clock, screen_time
from ..screen_time import APPS
from . import bp, form_text, page, repo, say, uid


def load_usage(user_id, first_day, last_day):
    r = repo()
    first, last = first_day.isoformat(), last_day.isoformat()
    visits = r.screen_visits(user_id, first, last)
    return screen_time.usage(r.screen_log(user_id, first, last), visits), visits


@bp.route("/screen")
def screen():
    user_id, today = uid(), clock.today()
    limits = repo().screen_limits(user_id)
    usage, visits = load_usage(user_id, today - timedelta(days=1), today)
    today_usage = screen_time.day_usage(usage, today)
    yesterday_usage = screen_time.day_usage(usage, today - timedelta(days=1))
    rows = screen_time.today_rows(limits, today_usage)
    return page("zehava/screen.html", active="screen", rows=rows, limits=limits, apps=APPS,
                logged_today={app: m for app, (m, source) in today_usage.items() if source == "logged"},
                logged_yesterday={app: m for app, (m, source) in yesterday_usage.items() if source == "logged"},
                visits=[dict(visit, time=clock.from_iso(visit["created_at"]).strftime("%H:%M"))
                        for visit in visits if visit["day"] == today.isoformat()][::-1],
                has_data=any(row["source"] != "none" for row in rows))


@bp.route("/screen/log", methods=["POST"])
def screen_log():
    # רישום דקות להיום או לאתמול. שדה ריק = בלי שינוי
    today = clock.today()
    day = today - timedelta(days=1) if request.form.get("day") == "yesterday" else today
    saved = bad = False
    for app in APPS:
        minutes = screen_time.parse_minutes(request.form.get(f"min_{app}"), 0, screen_time.LOG_MAX)
        if minutes == "":
            continue
        if minutes is None:
            bad = True
            continue
        repo().save_screen_log(uid(), app, day.isoformat(), minutes)
        saved = True
    if bad:
        say("screen_log_bad", "warn")
    elif saved:
        say("screen_log_saved")
    return redirect(url_for("zehava.screen") + "#log")


@bp.route("/screen/limits", methods=["POST"])
def screen_limits():
    # יעד יומי לכל רשת. ריק = להפסיק לעקוב
    bad = False
    for app in APPS:
        minutes = screen_time.parse_minutes(request.form.get(f"limit_{app}"), screen_time.LIMIT_MIN, screen_time.LIMIT_MAX)
        if minutes is None:
            bad = True
            continue
        repo().set_screen_limit(uid(), app, minutes or None)
    say("screen_goal_bad", "warn") if bad else say("screen_goals_saved")
    return redirect(url_for("zehava.screen") + "#goals")


@bp.route("/screen/open/<app>", methods=["GET", "POST"])
def screen_gate(app):
    # שער הכוונה: שתי שאלות קצרות, ורק אז מעבר לרשת. אפשר גם לבחור לא להיכנס
    if app not in APPS:
        abort(404)
    name, url = APPS[app]
    today = clock.today().isoformat()
    if request.method == "POST":
        if request.form.get("skip") == "1":
            repo().add_screen_visit(uid(), app, today, None, None, opened=False)
            say("gate_skipped")
            return redirect(url_for("zehava.screen"))
        reason = request.form.get("reason")
        minutes = request.form.get("minutes", type=int)
        if reason not in screen_time.REASONS or minutes not in screen_time.GATE_MINUTES:
            say("gate_bad", "warn")
            return redirect(url_for("zehava.screen_gate", app=app))
        repo().add_screen_visit(uid(), app, today, reason, minutes, form_text("note", screen_time.NOTE_MAX))
        # הכתובת מגיעה מהרשימה הקבועה APPS, לעולם לא מהטופס
        return redirect(url, code=303)
    limits = repo().screen_limits(uid())
    usage, _ = load_usage(uid(), clock.today(), clock.today())
    minutes, _source = screen_time.day_usage(usage, clock.today()).get(app, (0, "none"))
    return page("zehava/screen_gate.html", active="screen", app=app, app_name=name,
                used=minutes, limit=limits.get(app),
                reasons=screen_time.REASONS, choices=screen_time.GATE_MINUTES)
