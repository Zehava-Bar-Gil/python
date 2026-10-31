"""התובנות שלי (שכבה 3), המשוב היומי (Daily Pulse), והסיכום היומי במייל."""
from datetime import timedelta

from flask import abort, current_app, g, redirect, request, url_for

from .. import clock, focus_timer, journey, mailer, personalization_engine, security, ui
from ..learning_data import build_history
from . import back, bp, page, repo, say, tr, uid

PULSE_MAX_AGE = mailer.PULSE_LINK_MAX_AGE
MAX_MANUAL_EMAILS_PER_DAY = 5


def today_summary(user_id, day):
    # מה הושלם היום, מה נדחה, וכמה זמן מיקוד נמדד. רק נתונים אמיתיים
    r = repo()
    start, end = clock.day_bounds(day)
    tasks = r.list_tasks(user_id)
    return {
        "done": [t["title"] for t in tasks if t["completed_at"] and start <= t["completed_at"] < end],
        "postponed": [t for t in tasks if t["status"] == "open" and t["snooze_count"]],
        "stats": focus_timer.day_stats(r, user_id, day),
        "points": r.journey_points(user_id, start, end),
    }


def save_pulse_from_form(user_id, day):
    t = tr()
    if request.form.get("skip") == "1":
        repo().save_pulse(user_id, day, None, "", skipped=True)
        return "pulse_skipped"
    rating = request.form.get("rating", type=int)
    if rating not in t["ratings"]:
        return None
    reasons = [reason for reason in request.form.getlist("reasons") if reason in t["reasons"]]
    repo().save_pulse(user_id, day, rating, ",".join(reasons))
    return "pulse_saved"


@bp.route("/insights")
def insights():
    r, user_id, settings, now, t = repo(), uid(), g.settings, clock.now(), tr()
    insight = overview = None
    if settings["learning_enabled"]:
        history = build_history(r, user_id, settings)
        insight = personalization_engine.choose(history)
        overview = personalization_engine.overview(history)
    pulse = r.get_pulse(user_id, now.date().isoformat())
    summary = today_summary(user_id, now.date())
    return page("zehava/insights.html", active="insights", insight=insight, overview=overview,
                pulse=pulse, pulse_open=settings["pulse_enabled"], faces=ui.PULSE_FACES,
                summary=summary, focus_label=ui.minutes_label(t, summary["stats"]["focus_seconds"]),
                journey=journey.position(r.journey_points(user_id)),
                email_verified=bool(g.user["email_verified_at"]),
                selected_reasons=(pulse["reasons"].split(",") if pulse and pulse["reasons"] else []))


@bp.route("/insights/data")
def insights_data():
    # "על מה זה מבוסס?": המספרים שהמנוע חישב, כמו שהם
    if not g.settings["learning_enabled"]:
        return redirect(url_for("zehava.insights"))
    history = build_history(repo(), uid(), g.settings)
    return page("zehava/insights_data.html", active="insights",
                found=personalization_engine.evaluate(history), chosen=personalization_engine.choose(history))


@bp.route("/insights/<rule_id>/<action>", methods=["POST"])
def insight_feedback(rule_id, action):
    status = {"accept": "accepted", "dismiss": "dismissed", "correct": "corrected"}.get(action)
    if not status or not g.settings["learning_enabled"]:
        abort(404)
    history = build_history(repo(), uid(), g.settings)
    insight = next((i for i in personalization_engine.evaluate(history) if i.rule_id == rule_id), None)
    if not insight:
        return back("zehava.insights")
    repo().record_insight(uid(), rule_id, status, insight.evidence)
    say(f"insight_{status}")
    if status != "accepted" or not insight.action:
        return back("zehava.insights")
    # "לנסות": הפעולה שההצעה מציעה. כל שינוי הגדרה אפשר לבטל בהגדרות
    kind, _, value = insight.action.partition(":")
    if kind == "set_focus":
        repo().update_settings(uid(), focus_minutes=int(value))
        return redirect(url_for("zehava.timer"))
    if kind == "calm_mode":
        repo().update_settings(uid(), calm_mode=1)
        return redirect(url_for("zehava.home"))
    if kind == "open_task":
        return redirect(url_for("zehava.tasks", open=int(value)) + f"#task-{value}")
    if kind == "start_small_session":
        return redirect(url_for("zehava.focus"))
    if kind == "try_sound":
        return redirect(url_for("zehava.sounds"))
    return back("zehava.insights")


@bp.route("/learning/consent", methods=["POST"])
def learning_consent():
    # הלמידה האישית פועלת רק אחרי הסכמה מפורשת, ואפשר לכבות אותה בכל רגע
    if request.form.get("enable") == "1":
        repo().update_settings(uid(), learning_enabled=1, learning_consent_at=clock.now_iso())
        say("learning_on")
    else:
        repo().update_settings(uid(), learning_enabled=0)
        say("learning_off")
    return back("zehava.insights")


@bp.route("/pulse", methods=["POST"])
def pulse():
    day = clock.today().isoformat()
    result = save_pulse_from_form(uid(), day)
    if result:
        say(result)
    return back("zehava.insights")


@bp.route("/pulse/email/<token>", methods=["GET", "POST"])
def pulse_from_email(token):
    # קישור מהמייל היומי: עונים על השאלה גם בלי להתחבר. האסימון חתום ותקף 3 ימים
    data = security.read_token("pulse", token, PULSE_MAX_AGE)
    user = repo().get_user(data["uid"]) if data else None
    if not user or not clock.parse_day(data.get("day")):
        return page("zehava/message.html", title_key="pulse_link_bad", ok=False), 400
    g.lang_override = repo().get_settings(user["id"])["lang"]
    saved = None
    if request.method == "POST":
        saved = save_pulse_from_form(user["id"], data["day"])
    current = repo().get_pulse(user["id"], data["day"])
    return page("zehava/pulse_email.html", token=token, saved=saved, pulse=current, faces=ui.PULSE_FACES,
                day=clock.parse_day(data["day"]),
                selected_reasons=(current["reasons"].split(",") if current and current["reasons"] else []))


@bp.route("/mail/send", methods=["POST"])
def mail_send():
    # שליחת הסיכום עכשיו. רק לכתובת מאומתת, ועד 5 פעמים ביום
    if not g.user["email_verified_at"]:
        say("mail_needs_verify", "warn")
        return back("zehava.insights")
    since = clock.to_iso(clock.now() - timedelta(days=1))
    if repo().count_emails(uid(), "manual", since) >= MAX_MANUAL_EMAILS_PER_DAY:
        say("err_too_many", "warn")
    elif mailer.send_summary_now(current_app._get_current_object(), repo(), g.user, g.settings["lang"]):
        say("mail_sent")
    else:
        say("mail_error", "warn")
    return back("zehava.insights")


@bp.route("/unsubscribe/<token>", methods=["GET", "POST"])
def unsubscribe(token):
    # הסרה מהסיכום היומי. GET מציג אישור, POST מבצע (גם בלחיצה אחת מתוכנת המייל)
    data = security.read_token("unsubscribe", token, max_age=None)
    user = repo().get_user(data["uid"]) if data else None
    if not user:
        return page("zehava/message.html", title_key="pulse_link_bad", ok=False), 400
    g.lang_override = repo().get_settings(user["id"])["lang"]
    if request.method == "POST":
        repo().update_settings(user["id"], daily_email=0)
        return page("zehava/message.html", title_key="unsubscribed", ok=True)
    return page("zehava/unsubscribe.html", token=token)
