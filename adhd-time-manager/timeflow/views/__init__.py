"""הנתיבים של TimeFlow: Blueprint אחד תחת /zehava, מחולק לקבצים לפי אזור באתר.

כל קובץ כאן רק מקבל בקשה, קורא לפונקציות הלוגיקה (planner, focus_timer, journey...)
ומחזיר תבנית או הפניה. ה-SQL נמצא רק ב-repository.py.
"""
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for

from .. import accounts, clock, security, ui
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


def current_address():
    # איך פונים בעברית: f נקבה, m זכר, x לא מוגדר (את.ה). לפני הכניסה לחשבון: x
    settings = g.get("settings")
    return settings["address"] if settings else "x"


def tr():
    return texts(current_lang(), current_address())


def say(key, kind="ok", **params):
    # הודעה קצרה בראש הדף הבא. נשמר רק מפתח הטקסט, כך שהיא מוצגת בשפה של המשתמשת
    flash([key, params], kind)


def say_password_level(password, email=""):
    # אחרי שסיסמה חדשה נשמרה: הודעה קצרה אם היא בינונית או חזקה (חלשה לא נשמרת בכלל)
    say(f"password_level_{accounts.password_strength(password, email)}")


def mark_just(kind, item_id, task_id=None):
    # מיקרו-אינטראקציה: הדף הבא יודע מה השתנה עכשיו (משימה, צעד או פתק), ומדגיש בעדינות רק אותו.
    # בצעד שומרים גם את המשימה שלו, כדי שרשימת הצעדים תישאר פתוחה אחרי הלחיצה
    session["just"] = [kind, item_id, task_id]


def back(default="zehava.home", **values):
    # חזרה לדף שממנו נשלח הטופס (שדה back), רק אם זו כתובת פנימית של האתר
    target = request.form.get("back") or request.args.get("back")
    if target and security.safe_next(target) == target:
        return redirect(target)
    return redirect(url_for(default, **values))


def form_text(name, limit):
    return " ".join((request.form.get(name) or "").split())[:limit]


def form_date(name):
    # תאריך משלוש רשימות בחירה: {name}_year, {name}_month, {name}_day.
    # מחזיר (תאריך, האם נבחר משהו). שלוש רשימות ריקות = (None, False),
    # ותאריך שלא קיים (31 ביוני) או בחירה חלקית = (None, True)
    parts = [request.form.get(f"{name}_{key}", "").strip() for key in ("year", "month", "day")]
    if not any(parts):
        return None, False
    day = None
    if all(part.isdigit() for part in parts):
        day = clock.parse_day("{:0>4}-{:0>2}-{:0>2}".format(*parts))
    return day, True


def form_int(name, default, low, high):
    try:
        value = int(request.form.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def is_framed():
    # הדף נפתח בתוך הנגן (iframe), כך שהמוזיקה ממשיכה בזמן שעוברים בין דפים.
    # הדפדפן אומר זאת בכותרת Sec-Fetch-Dest, בלי JavaScript
    return request.headers.get("Sec-Fetch-Dest") == "iframe"


def current_theme(settings):
    # מצב "לפי השעה": השרת בוחר בהיר או כהה לפי שעון ישראל, בכל טעינה של דף
    if not settings:
        return "auto"
    return ui.clock_theme(clock.now().hour) if settings["theme_by_clock"] else settings["theme"]


def common_context():
    # מה שכל תבנית צריכה: טקסטים, שפה, משתמשת, הגדרות תצוגה ואייקונים
    lang = current_lang()
    settings = g.get("settings")
    return {
        "t": texts(lang, current_address()),
        "lang": lang,
        "lang_index": 0 if lang == "he" else 1,
        "user": g.get("user"),
        "name": ui.first_name(g.user, lang) if g.get("user") else "",
        "full_name": ui.full_name(g.user, lang) if g.get("user") else "",
        "framed": is_framed(),
        "playing": session.get("playing"),
        "sound_spaces": ui.SOUND_SPACES,
        "settings": settings,
        "theme": current_theme(settings),
        "motion": not (settings and settings["reduce_motion"]),
        "icons": ui.ICONS,
        "est_label": lambda minutes: ui.estimate_label(texts(lang), minutes),
        "nav": ui.NAV,
        "side": ui.SIDE,
        "tags": TAGS,
        "csrf_token": security.csrf_token,
        "csrf_field": security.CSRF_FIELD,
        "dev_mail": current_app.config["MAIL_BACKEND"] == "file",
        "chime": g.get("chime", False),
    }


def page(template, active=None, **ctx):
    # "just" מוצג פעם אחת בלבד: בטעינה הבאה הוא כבר לא קיים, והאנימציה לא חוזרת
    just = session.pop("just", None)
    ctx.setdefault("just", just[:2] if just else None)
    ctx.setdefault("just_task", just[2] if just else None)
    return render_template(template, active=active, **ctx)


# הקבצים נטענים בסוף, אחרי ש-bp כבר קיים, כדי שהנתיבים שלהם יירשמו עליו
from . import (auth_views, calendar_views, home_views, insight_views, note_views,  # noqa: E402,F401
               settings_views, snooze_views, task_views, timer_views)
