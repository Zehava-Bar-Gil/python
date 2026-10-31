"""הנתיבים של TimeFlow: Blueprint אחד תחת /zehava, מחולק לקבצים לפי אזור באתר.

כל קובץ כאן רק מקבל בקשה, קורא לפונקציות הלוגיקה (planner, focus_timer, journey...)
ומחזיר תבנית או הפניה. ה-SQL נמצא רק ב-repository.py.
"""
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for

from .. import security, ui
from ..db import get_db
from ..repository import Repository
from ..texts import TAGS, texts

bp = Blueprint("zehava", __name__, url_prefix="/zehava")

# הדפים היחידים שפתוחים בלי התחברות. כל דף אחר דורש משתמשת מחוברת
PUBLIC = {
    "zehava.login", "zehava.register", "zehava.forgot", "zehava.reset", "zehava.verify",
    "zehava.lang", "zehava.unsubscribe", "zehava.pulse_from_email", "zehava.privacy",
}


def repo():
    if "repo" not in g:
        g.repo = Repository(get_db())
    return g.repo


def uid():
    return g.user["id"]


def current_lang():
    # דפים שנפתחים מקישור במייל (בלי התחברות) מוצגים בשפה של בעלת החשבון
    if g.get("lang_override"):
        return g.lang_override
    if g.get("settings"):
        return g.settings["lang"]
    return session.get("lang") if session.get("lang") in ("he", "en") else "he"


def tr():
    return texts(current_lang())


def say(key, kind="ok", **params):
    # הודעה קצרה בראש הדף הבא. נשמר רק מפתח הטקסט, כך שהיא מוצגת בשפה של המשתמשת
    flash([key, params], kind)


def back(default="zehava.home", **values):
    # חזרה לדף שממנו נשלח הטופס (שדה back), רק אם זו כתובת פנימית של האתר
    target = request.form.get("back") or request.args.get("back")
    if target and security.safe_next(target) == target:
        return redirect(target)
    return redirect(url_for(default, **values))


def form_text(name, limit):
    return " ".join((request.form.get(name) or "").split())[:limit]


def form_int(name, default, low, high):
    try:
        value = int(request.form.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def common_context():
    # מה שכל תבנית צריכה: טקסטים, שפה, משתמשת, הגדרות תצוגה ואייקונים
    lang = current_lang()
    settings = g.get("settings")
    return {
        "t": texts(lang),
        "lang": lang,
        "lang_index": 0 if lang == "he" else 1,
        "user": g.get("user"),
        "settings": settings,
        "theme": settings["theme"] if settings else "auto",
        "motion": not (settings and settings["reduce_motion"]),
        "icons": ui.ICONS,
        "nav": ui.NAV,
        "side": ui.SIDE,
        "tags": TAGS,
        "csrf_token": security.csrf_token,
        "csrf_field": security.CSRF_FIELD,
        "dev_mail": current_app.config["MAIL_BACKEND"] == "file",
        "chime": g.get("chime", False),
    }


def page(template, active=None, **ctx):
    return render_template(template, active=active, **ctx)


# הקבצים נטענים בסוף, אחרי ש-bp כבר קיים, כדי שהנתיבים שלהם יירשמו עליו
from . import (auth_views, calendar_views, home_views, insight_views, note_views,  # noqa: E402,F401
               settings_views, snooze_views, task_views, timer_views)
