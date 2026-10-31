"""הגדרות: מראה, מיקוד, צלילים, התראות, מייל, פרטיות, ייצוא ומחיקה."""
import json

from flask import Response, abort, current_app, g, redirect, request, url_for
from werkzeug.security import check_password_hash

from .. import accounts, clock, google_calendar, security
from . import back, bp, form_int, form_text, page, repo, say, uid

CHOICES = {
    "theme": ("auto", "light", "dark"),
    "lang": ("he", "en"),
    "sound_pref": ("ask", "none", "deep", "calm", "study", "reading"),
    "notifications": ("off", "quiet", "normal"),
}
SWITCHES = ("reduce_motion", "timer_chime", "pulse_enabled", "ai_enabled", "daily_email", "learning_enabled")


def settings_from_form(current):
    # כל ערך נבדק מול רשימה סגורה או טווח. ערך לא תקין משאיר את הקיים
    values = {}
    for name, allowed in CHOICES.items():
        chosen = request.form.get(name)
        values[name] = chosen if chosen in allowed else current[name]
    for name in SWITCHES:
        values[name] = 1 if request.form.get(name) == "1" else 0
    values["focus_minutes"] = form_int("focus_minutes", current["focus_minutes"], 2, 120)
    values["short_break_minutes"] = form_int("short_break_minutes", current["short_break_minutes"], 1, 30)
    values["long_break_minutes"] = form_int("long_break_minutes", current["long_break_minutes"], 5, 60)
    at = clock.parse_hhmm(request.form.get("daily_email_at"))
    values["daily_email_at"] = at.strftime("%H:%M") if at else current["daily_email_at"]
    if values["learning_enabled"] and not current["learning_enabled"]:
        values["learning_consent_at"] = clock.now_iso()
    return values


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        repo().update_settings(uid(), **settings_from_form(g.settings))
        name = form_text("display_name", 40)
        if name:
            repo().update_display_name(uid(), name)
        say("settings_saved")
        return redirect(url_for("zehava.settings"))
    return page("zehava/settings.html", active="settings", choices=CHOICES,
                google=google_calendar.status(repo(), current_app.config, uid()),
                email_verified=bool(g.user["email_verified_at"]), password_errors=[])


@bp.route("/settings/password", methods=["POST"])
def change_password():
    errors = accounts.change_password(repo(), g.user, request.form.get("current_password"),
                                      request.form.get("new_password"))
    if errors:
        for error in errors:
            say(error, "warn")
        return redirect(url_for("zehava.settings") + "#account")
    # הסיסמה השתנתה: כל ההתחברויות האחרות מתבטלות, וכאן מתחברים מחדש עם הסיסמה החדשה
    security.login_user(repo().get_user(uid()))
    say("password_changed")
    return redirect(url_for("zehava.settings") + "#account")


@bp.route("/settings/export")
def export_data():
    data = repo().export_user_data(uid())
    body = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    return Response(body, mimetype="application/json",
                    headers={"Content-Disposition": f"attachment; filename=timeflow-{clock.today()}.json"})


@bp.route("/settings/delete-learning", methods=["POST"])
def delete_learning():
    repo().delete_learning_data(uid())
    say("learning_deleted")
    return back("zehava.settings")


@bp.route("/settings/delete-account", methods=["POST"])
def delete_account():
    # מחיקה לצמיתות: דורשת סיסמה וסימון אישור. Google מנותק קודם, כדי לבטל את ההרשאה שם
    if request.form.get("confirm") != "1" or \
            not check_password_hash(g.user["password_hash"], request.form.get("password") or ""):
        say("err_current_password", "warn")
        return redirect(url_for("zehava.settings") + "#danger")
    google_calendar.disconnect(repo(), current_app.config, uid())
    repo().delete_user(uid())
    security.logout_user()
    g.user = g.settings = None
    return page("zehava/message.html", title_key="account_deleted", ok=True)


@bp.route("/motion/<state>", methods=["POST"])
def motion(state):
    # כתובת מגרסה 1: עצירה והפעלה של התנועה ברקע
    if state not in ("on", "off"):
        abort(404)
    repo().update_settings(uid(), reduce_motion=1 if state == "off" else 0)
    return back("zehava.home")
