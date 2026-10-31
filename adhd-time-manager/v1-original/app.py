import calendar
import json
import os
import smtplib
import threading
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, redirect, render_template, render_template_string, request, url_for

app = Flask(__name__)

# רשימת הקישורים בדף הבית (slug -> שם)
PEOPLE = {
    "zehava": "זהבה",
    "yair": "יאיר",
    "guy": "גיא",
    "hillel": "הלל",
    "harel": "הראל",
    "ariel": "אריאל",
}

BASE = """<!doctype html>
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
</head>
<body>
  <nav><a href="/">דף הבית</a></nav>
  <h1>{{ title }}</h1>
  {{ content | safe }}
</body>
</html>"""

INDEX_CONTENT = """<ul>
{% for slug, name in people.items() %}  <li><a href="/{{ slug }}">{{ name }}</a></li>
{% endfor %}</ul>"""

PERSON_CONTENT = """<p>ברוכים הבאים לדף של {{ name }}.</p>"""


def render_page(title, content_template, **ctx):
    content = render_template_string(content_template, **ctx)
    return render_template_string(BASE, title=title, content=content)


@app.route("/")
def index():
    return render_page("שלד Flask", INDEX_CONTENT, people=PEOPLE)


# ---------- הדף של זהבה: TimeFlow, ניהול זמן מותאם ADHD ----------
# כל הנתונים נשמרים בזיכרון בשלב הזה (בהמשך: קובץ או מסד נתונים)
ISRAEL = ZoneInfo("Asia/Jerusalem")

zehava_tasks = []   # {"text", "time", "tag", "done", "steps": [{"text", "done"}], "snoozed"}
zehava_notes = []   # {"text", "color"}
zehava_goal = {"text": ""}
zehava_timer = {"minutes": 25, "ends_at": None, "pomodoros": 0, "focused": 0}
# מצב מיקוד: משימה אחת וטיימר משלו. started בלי ends_at = מצב גמיש
zehava_focus = {"task": None, "minutes": 25, "started": None, "ends_at": None, "finished": False}
zehava_journey = {"shown": 0}   # התחנה שבה הכדור הפורח עמד בפעם הקודמת
zehava_mail = {"last_sent": None, "status": "", "lang": "he", "thread": None}

# קטגוריות למשימות: מפתח -> (עברית, אנגלית)
ZEHAVA_TAGS = {
    "work": ("עבודה", "Work"),
    "study": ("לימודים", "Study"),
    "personal": ("אישי", "Personal"),
    "health": ("בריאות", "Health"),
    "home": ("בית", "Home"),
    "planning": ("תכנון", "Planning"),
}

NOTE_COLORS = ["yellow", "pink", "green", "blue"]
TIMER_OPTIONS = [25, 50, 90]
SNOOZE_OPTIONS = [5, 10, 15, 30, 60]
FOCUS_OPTIONS = [15, 25, 45, 60]
SNOOZE_HINT_AFTER = 3   # אחרי כמה דחיות מציעים בעדינות לפרק משימה

# הכדור הפורח: גובה בשביל (באחוזים מגובה התמונה) לכל תחנה, מ-0 משימות ועד הפסגה
BALLOON_STATIONS = [76, 72, 66, 57.5, 51, 45, 40]

# Soundscape: מרחב -> (שם, קובץ). הצלילים נוצרו בקוד, אין בעיית זכויות יוצרים
SOUND_SPACES = {
    "deep": ("Deep Focus", "deep"),
    "calm": ("Calm", "calm"),
    "study": ("Study", "study"),
    "reading": ("Reading & Recall", "reading"),
}
zehava_sound_votes = {key: {"yes": 0, "no": 0} for key in SOUND_SPACES}

# הגדרות המייל נשמרות בקובץ נפרד שלא עולה לגיט (ראו mail_config.example.json)
MAIL_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mail_config.json")

# כל הטקסטים של האתר בשתי שפות
ZEHAVA_TEXTS = {
    "he": {
        "dir": "rtl",
        "other_lang": "en",
        "switch": "English",
        "home": "דף הבית",
        "tagline": "צעדים קטנים. חלומות גדולים.",
        "todo": "רשימת מטלות",
        "notes": "פתקיות",
        "timer": "טיימר עגבנייה",
        "snooze": "נודניק",
        "calendar": "יומן Google",
        "today": "היום",
        "progress_nav": "התקדמות",
        "settings": "הגדרות",
        "quote": "הנוף הכי יפה מגיע אחרי הטיפוס הכי קשה.",
        "morning": "בוקר טוב",
        "afternoon": "צהריים טובים",
        "evening": "ערב טוב",
        "night": "לילה טוב",
        "subtitle": "צעדים קטנים היום, חלומות גדולים מחר.",
        "goal_label": "היעד שלי",
        "goal_default": "להגיע לפסגה",
        "goal_placeholder": "מה היעד הגדול שלך?",
        "save": "שמירה",
        "tasks_title": "המשימות של היום",
        "all": "הכול",
        "placeholder": "מה המשימה הבאה?",
        "add": "הוספה",
        "next_step": "הצעד הבא שלך",
        "all_done": "כל הכבוד! הגעת לפסגה 🎉",
        "empty_title": "היום שלך עדיין ריק",
        "empty_text": "מתחילים ממשימה אחת קטנה",
        "mark_done": "בוצע",
        "delete": "מחיקה",
        "no_tag": "קטגוריה",
        "note_placeholder": "רעיון, מחשבה, תזכורת...",
        "notes_empty": "אין פתקיות עדיין",
        "focus": "זמן ריכוז",
        "start": "התחלה",
        "reset": "איפוס",
        "min": "דק'",
        "ends_at": "מסתיים ב-",
        "snooze_for": "דחיית המשימה הבאה ב:",
        "snooze_none": "אין משימה עם שעה לדחות. הוסיפי שעה למשימה.",
        "minutes": "דקות",
        "hour": "שעה",
        "agenda": "סדר היום",
        "agenda_empty": "משימות עם שעה יופיעו כאן",
        "connect_google": "חיבור ליומן Google (בקרוב)",
        "progress_title": "ההתקדמות של היום",
        "tasks_done": "משימות הושלמו",
        "focused_time": "זמן ריכוז",
        "pomodoros": "עגבניות",
        "daily_steps": "צעדים יומיים",
        "progress": "התקדמות",
        "big_goal": "יעד גדול",
        "journey": "הדרך היא המטרה",
        "motion_off": "עצירת תנועה",
        "motion_on": "הפעלת תנועה",
        "login_title": "ברוכה הבאה ל-TimeFlow",
        "login_text": "איך לקרוא לך?",
        "login_placeholder": "השם שלך",
        "login_button": "כניסה",
        "login_google": "כניסה עם Google (בקרוב)",
        "logout": "יציאה",
        "focus_mode": "מצב מיקוד",
        "dnd": "נא לא להפריע",
        "focus_this": "להתמקד בזה",
        "focus_how_long": "כמה זמן להתמקד?",
        "flexible": "גמיש",
        "start_small": "להתחיל רק 5 דקות",
        "leave_focus": "יציאה ממצב מיקוד",
        "leave_note": "אפשר לצאת בכל רגע. שום התקדמות לא נמחקת.",
        "session_done": "סיימת סשן ריכוז! זה הזמן להפסקה קצרה 🌿",
        "task_finished": "סיימתי את המשימה",
        "focus_empty": "אין משימה פתוחה. אפשר להוסיף משימה בלוח.",
        "elapsed": "זמן שעבר",
        "steps": "צעדים קטנים",
        "split_task": "פירוק לצעדים קטנים",
        "step_placeholder": "צעד קטן אחד...",
        "tiny_step": "הצעד הקטן הבא:",
        "snooze_hint": "נדחתה {n} פעמים. אולי לפרק אותה לצעדים קטנים?",
        "summary_title": "הסיכום של היום",
        "summary_done": "הושלמו",
        "summary_postponed": "נדחו",
        "summary_none": "עוד אין",
        "times": "פעמים",
        "send_mail": "שליחת הסיכום ל-Gmail",
        "mail_sent": "הסיכום נשלח למייל ✓",
        "mail_error": "השליחה לא הצליחה. כדאי לבדוק את mail_config.json.",
        "mail_setup": "כדי לשלוח למייל, ממלאים את הקובץ mail_config.json.",
        "mail_daily": "נשלח אוטומטית כל יום ב-",
        "mail_subject": "הסיכום שלך מ-TimeFlow",
        "mail_hello": "היי",
        "mail_footer": "צעדים קטנים היום, חלומות גדולים מחר.",
        "sounds": "Soundscape",
        "sounds_title": "בחרי את המרחב שלך",
        "sounds_sub": "סביבה קולית לכל סוג משימה. הצליל מתחיל רק כשלוחצים על Play.",
        "open_sounds": "פתיחת הנגן בלשונית חדשה",
        "sounds_tip": "אפשר לנגן שני מרחבים יחד, ולכוון לכל אחד עוצמה משלו.",
        "sounds_note": "אלה הצעות ולא טיפול. כל אחת מגלה מה עובד בשבילה, ולכן אפשר לסמן מה עזר.",
        "sound_deep": "צלילים רציפים ועמוקים, בלי מילים",
        "sound_calm": "גלים ואווירה רגועה",
        "sound_study": "מוזיקה אינסטרומנטלית שקטה",
        "sound_reading": "רחש גשם עדין לקריאה ולשינון",
        "helped": "עזר לי",
        "not_helped": "פחות",
        "helped_stats": "עזר {yes} מתוך {total} פעמים",
        "favorite": "המועדף עלייך",
        "back_to_board": "חזרה ללוח",
        "weekdays": ["א", "ב", "ג", "ד", "ה", "ו", "ש"],
        "months": ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי",
                   "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"],
    },
    "en": {
        "dir": "ltr",
        "other_lang": "he",
        "switch": "עברית",
        "home": "Home",
        "tagline": "Small steps. Big dreams.",
        "todo": "To Do List",
        "notes": "Sticky Notes",
        "timer": "Pomodoro",
        "snooze": "Snooze",
        "calendar": "Google Calendar",
        "today": "Today",
        "progress_nav": "Progress",
        "settings": "Settings",
        "quote": "The best view comes after the hardest climb.",
        "morning": "Good morning",
        "afternoon": "Good afternoon",
        "evening": "Good evening",
        "night": "Good night",
        "subtitle": "Small steps today, big dreams tomorrow.",
        "goal_label": "My goal",
        "goal_default": "Reach the summit",
        "goal_placeholder": "What is your big goal?",
        "save": "Save",
        "tasks_title": "Today's Tasks",
        "all": "All",
        "placeholder": "What's next?",
        "add": "Add",
        "next_step": "Your next step",
        "all_done": "Well done! You reached the summit 🎉",
        "empty_title": "Your day is still empty",
        "empty_text": "Start with one small task",
        "mark_done": "Done",
        "delete": "Delete",
        "no_tag": "Category",
        "note_placeholder": "An idea, a thought, a reminder...",
        "notes_empty": "No notes yet",
        "focus": "Focus time",
        "start": "Start",
        "reset": "Reset",
        "min": "min",
        "ends_at": "Ends at ",
        "snooze_for": "Push the next task by:",
        "snooze_none": "No timed task to snooze. Add a time to a task.",
        "minutes": "minutes",
        "hour": "hour",
        "agenda": "Agenda",
        "agenda_empty": "Tasks with a time show up here",
        "connect_google": "Connect Google Calendar (soon)",
        "progress_title": "Today's Progress",
        "tasks_done": "tasks completed",
        "focused_time": "Focused time",
        "pomodoros": "Pomodoros",
        "daily_steps": "Daily steps",
        "progress": "Progress",
        "big_goal": "Big goal",
        "journey": "The journey is the goal",
        "motion_off": "Stop motion",
        "motion_on": "Start motion",
        "login_title": "Welcome to TimeFlow",
        "login_text": "What should we call you?",
        "login_placeholder": "Your name",
        "login_button": "Continue",
        "login_google": "Sign in with Google (soon)",
        "logout": "Log out",
        "focus_mode": "Focus mode",
        "dnd": "Do not disturb",
        "focus_this": "Focus on this",
        "focus_how_long": "How long do you want to focus?",
        "flexible": "Flexible",
        "start_small": "Start with just 5 minutes",
        "leave_focus": "Leave focus mode",
        "leave_note": "You can leave anytime. No progress is lost.",
        "session_done": "Session complete! Time for a short break 🌿",
        "task_finished": "I finished this task",
        "focus_empty": "No open task. Add one on the board.",
        "elapsed": "Elapsed",
        "steps": "Small steps",
        "split_task": "Split into small steps",
        "step_placeholder": "One small step...",
        "tiny_step": "Next tiny step:",
        "snooze_hint": "Postponed {n} times. Maybe split it into small steps?",
        "summary_title": "Today's summary",
        "summary_done": "Done",
        "summary_postponed": "Postponed",
        "summary_none": "None yet",
        "times": "times",
        "send_mail": "Email me this summary",
        "mail_sent": "Summary sent to your email ✓",
        "mail_error": "Sending failed. Please check mail_config.json.",
        "mail_setup": "To send by email, fill in mail_config.json.",
        "mail_daily": "Sent automatically every day at ",
        "mail_subject": "Your TimeFlow summary",
        "mail_hello": "Hi",
        "mail_footer": "Small steps today, big dreams tomorrow.",
        "sounds": "Soundscape",
        "sounds_title": "Choose your mental space",
        "sounds_sub": "A sound space for every kind of task. Sound starts only when you press Play.",
        "open_sounds": "Open the player in a new tab",
        "sounds_tip": "You can play two spaces together and set each one's volume.",
        "sounds_note": "These are suggestions, not a treatment. Everyone finds what works for them, so you can mark what helped.",
        "sound_deep": "Deep, continuous sound with no lyrics",
        "sound_calm": "Waves and a calm atmosphere",
        "sound_study": "Soft instrumental music",
        "sound_reading": "Gentle rain for reading and recall",
        "helped": "Helped me",
        "not_helped": "Not really",
        "helped_stats": "Helped {yes} of {total} times",
        "favorite": "Your favorite",
        "back_to_board": "Back to board",
        "weekdays": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "months": ["January", "February", "March", "April", "May", "June", "July",
                   "August", "September", "October", "November", "December"],
    },
}

# אייקונים בקו דק (נתיבי SVG בגודל 24x24)
ZEHAVA_ICONS = {
    "todo": "M9 11l3 3L22 4 M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
    "notes": "M16 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8Z M15 3v4a2 2 0 0 0 2 2h4",
    "timer": "M10 2h4 M12 14l3-3 M4 14a8 8 0 1 0 16 0a8 8 0 1 0-16 0",
    "snooze": "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z",
    "calendar": "M8 2v4 M16 2v4 M3 10h18 M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
    "home": "M3 10l9-7 9 7v10a2 2 0 0 1-2 2h-4v-7H9v7H5a2 2 0 0 1-2-2z",
    "today": "M9 11l3 3L22 4 M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
    "progress_nav": "M3 3v18h18 M7 16v-4 M12 16V8 M17 16v-7",
    "settings": "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
    "mountain": "M2 20l7-12 4 6 3-4 6 10z M9 8l2 3",
    "sun": "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z M12 1v2 M12 21v2 M4.2 4.2l1.4 1.4 M18.4 18.4l1.4 1.4 M1 12h2 M21 12h2 M4.2 19.8l1.4-1.4 M18.4 5.6l1.4-1.4",
    "moon": "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z",
    "clock": "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 6v6l4 2",
    "plus": "M12 5v14 M5 12h14",
    "play": "M7 4l13 8-13 8z",
    "reset": "M3 12a9 9 0 1 0 3-6.7L3 8 M3 3v5h5",
    "flag": "M4 22V4 M4 4h13l-2 4 2 4H4",
    "focus": "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12z M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
    "headphones": "M3 18v-6a9 9 0 0 1 18 0v6 M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z",
    "mail": "M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z M22 6l-10 7L2 6",
    "steps": "M8 6h13 M8 12h13 M8 18h13 M3 6h.01 M3 12h.01 M3 18h.01",
    "exit": "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9",
    "check": "M20 6L9 17l-5-5",
}

# הקישורים בתפריט העליון ובסרגל הצד: (עוגן בדף, מפתח טקסט ואייקון)
ZEHAVA_NAV = ["todo", "notes", "timer", "snooze", "calendar"]
ZEHAVA_SIDE = [("top", "home"), ("todo", "today"), ("calendar", "calendar"),
               ("progress", "progress_nav"), ("notes", "notes"), ("settings", "settings")]


def zehava_now():
    return datetime.now(ISRAEL)


def zehava_settings():
    # השפה, התנועה והשם נשמרים בעוגיות (cookies)
    lang = request.cookies.get("lang", "he")
    if lang not in ZEHAVA_TEXTS:
        lang = "he"
    motion = request.cookies.get("motion", "on") != "off"
    name = request.cookies.get("name", "")
    return lang, motion, name


def zehava_greeting(t, hour):
    if 5 <= hour < 12:
        return t["morning"]
    if 12 <= hour < 17:
        return t["afternoon"]
    if 17 <= hour < 22:
        return t["evening"]
    return t["night"]


def zehava_timer_state(now):
    # מחשב כמה זמן נשאר לטיימר. כשהזמן נגמר, סופרים עגבנייה שהושלמה
    ends_at = zehava_timer["ends_at"]
    if ends_at and now >= ends_at:
        zehava_timer["pomodoros"] += 1
        zehava_timer["focused"] += zehava_timer["minutes"]
        zehava_timer["ends_at"] = ends_at = None
    total = zehava_timer["minutes"] * 60
    remaining = int((ends_at - now).total_seconds()) if ends_at else total
    return {
        "minutes": zehava_timer["minutes"],
        "running": ends_at is not None,
        "total": total,
        "remaining": remaining,
        "ends_at": ends_at.strftime("%H:%M") if ends_at else "",
    }


def zehava_calendar(now, t):
    # חודש נוכחי, שבוע מתחיל ביום ראשון
    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(now.year, now.month)
    return {"title": f"{t['months'][now.month - 1]} {now.year}", "weeks": weeks, "today": now.day}


def zehava_back_to(anchor):
    # חזרה ללוח, ישר לחלק הנכון
    return redirect(url_for("zehava") + "#" + anchor)


def zehava_tiny_step(task):
    # ADHD: הצעד הקטן הבא בתוך משימה, אם פירקו אותה לצעדים
    if not task:
        return None
    return next((step["text"] for step in task["steps"] if not step["done"]), None)


def zehava_focus_task():
    # המשימה של מצב המיקוד. אם היא נמחקה או הושלמה, עוברים לבאה בתור
    i = zehava_focus["task"]
    if i is None or not 0 <= i < len(zehava_tasks) or zehava_tasks[i]["done"]:
        i = next((j for j, task in enumerate(zehava_tasks) if not task["done"]), None)
        zehava_focus["task"] = i
    return i


def zehava_focus_state(now):
    # כמה זמן נשאר לסשן הריכוז. סשן שהסתיים נספר כעגבנייה וכזמן ריכוז
    focus = zehava_focus
    if focus["ends_at"] and now >= focus["ends_at"]:
        zehava_timer["pomodoros"] += 1
        zehava_timer["focused"] += focus["minutes"]
        focus["started"] = focus["ends_at"] = None
        focus["finished"] = True
    running = focus["started"] is not None
    total = focus["minutes"] * 60
    return {
        "running": running,
        "flexible": running and focus["ends_at"] is None,
        "minutes": focus["minutes"],
        "total": total,
        "remaining": int((focus["ends_at"] - now).total_seconds()) if focus["ends_at"] else total,
        "elapsed": int((now - focus["started"]).total_seconds()) if running else 0,
        "ends_at": focus["ends_at"].strftime("%H:%M") if focus["ends_at"] else "",
        "finished": focus["finished"],
    }


def zehava_summary():
    # הסיכום היומי: מה הושלם, מה נדחה ומה הצעד הבא. משמש גם לכרטיס וגם למייל
    next_task = next((task for task in zehava_tasks if not task["done"]), None)
    return {
        "done": [task["text"] for task in zehava_tasks if task["done"]],
        "postponed": [task for task in zehava_tasks if task["snoozed"] and not task["done"]],
        "next": next_task,
        "tiny_step": zehava_tiny_step(next_task),
        "focused": zehava_timer["focused"],
        "pomodoros": zehava_timer["pomodoros"],
    }


# ---------- מייל: סיכום יומי ל-Gmail דרך סיסמת אפליקציה ----------
def zehava_mail_settings():
    # {"gmail", "app_password", "send_to", "daily_at"}. בלי קובץ אין שליחה
    try:
        with open(MAIL_CONFIG, encoding="utf-8") as f:
            settings = json.load(f)
    except (OSError, ValueError):
        return None
    if not settings.get("gmail") or not settings.get("app_password") or "@" not in settings["gmail"]:
        return None
    settings.setdefault("send_to", settings["gmail"])
    settings.setdefault("daily_at", "21:00")
    return settings


def zehava_send_summary():
    settings = zehava_mail_settings()
    lang = zehava_mail["lang"]
    t = ZEHAVA_TEXTS[lang]
    if not settings:
        zehava_mail["status"] = "setup"
        return False
    now = zehava_now()
    with app.app_context():
        html = render_template("zehava/email.html", t=t, lang=lang, summary=zehava_summary(),
                               today_label=f"{now.day} {t['months'][now.month - 1]} {now.year}")
    message = EmailMessage()
    message["Subject"] = f"{t['mail_subject']} · {now.strftime('%d/%m')}"
    message["From"] = settings["gmail"]
    message["To"] = settings["send_to"]
    message.set_content(t["summary_title"])
    message.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(settings["gmail"], settings["app_password"].replace(" ", ""))
            server.send_message(message)
    except (OSError, smtplib.SMTPException):
        zehava_mail["status"] = "error"
        return False
    zehava_mail["status"] = "sent"
    return True


def zehava_mail_loop():
    # רץ ברקע: פעם בדקה בודק אם הגיעה השעה של הסיכום היומי
    while True:
        settings = zehava_mail_settings()
        now = zehava_now()
        if settings and now.strftime("%H:%M") >= settings["daily_at"] and zehava_mail["last_sent"] != now.date():
            zehava_mail["last_sent"] = now.date()
            zehava_send_summary()
        time.sleep(60)


def zehava_start_mail_loop():
    # מתחיל פעם אחת, בתהליך שמגיש את הדפים
    if zehava_mail["thread"] is None:
        zehava_mail["thread"] = threading.Thread(target=zehava_mail_loop, daemon=True)
        zehava_mail["thread"].start()


@app.route("/zehava")
def zehava():
    lang, motion, name = zehava_settings()
    if not name:
        return redirect(url_for("zehava_login"))
    t = ZEHAVA_TEXTS[lang]
    now = zehava_now()
    zehava_mail["lang"] = lang
    zehava_start_mail_loop()
    focus = zehava_focus_state(now)   # קודם, כדי שסשן שהסתיים ייספר בסטטיסטיקה

    tag_filter = request.args.get("tag", "")
    shown = [(i, task) for i, task in enumerate(zehava_tasks)
             if not tag_filter or task["tag"] == tag_filter]
    done_count = sum(task["done"] for task in zehava_tasks)
    total = len(zehava_tasks)
    percent = round(done_count / total * 100) if total else 0
    next_index = next((i for i, task in enumerate(zehava_tasks) if not task["done"]), None)
    next_task = zehava_tasks[next_index] if next_index is not None else None
    agenda = sorted((task for task in zehava_tasks if task["time"]), key=lambda task: task["time"])

    # אבני הדרך על השביל: 5 נקודות ופסגה, נדלקות לפי אחוז ההתקדמות
    lit = round(percent / 100 * 6)
    # הכדור הפורח טס מהתחנה הקודמת לתחנה החדשה
    climb_from, climb_to = BALLOON_STATIONS[zehava_journey["shown"]], BALLOON_STATIONS[lit]
    zehava_journey["shown"] = lit
    mail_settings = zehava_mail_settings()

    return render_template(
        "zehava/index.html",
        lang=lang, t=t, motion=motion, name=name,
        icons=ZEHAVA_ICONS, nav=ZEHAVA_NAV, side=ZEHAVA_SIDE,
        tags=ZEHAVA_TAGS, tag_filter=tag_filter, lang_index=0 if lang == "he" else 1,
        greeting=zehava_greeting(t, now.hour),
        today_label=f"{now.day} {t['months'][now.month - 1]} {now.year}",
        tasks=shown, total=total, done_count=done_count, percent=percent,
        next_task=next_task, next_index=next_index, tiny_step=zehava_tiny_step(next_task), agenda=agenda, lit=lit,
        climb_from=climb_from, climb_to=climb_to, focus=focus,
        open_task=request.args.get("open", type=int), snooze_hint_after=SNOOZE_HINT_AFTER,
        summary=zehava_summary(), mail_ready=mail_settings is not None,
        mail_daily_at=mail_settings["daily_at"] if mail_settings else "", mail_status=zehava_mail.pop("status", ""),
        goal=zehava_goal["text"] or t["goal_default"],
        notes=zehava_notes, note_colors=NOTE_COLORS,
        timer=zehava_timer_state(now), timer_options=TIMER_OPTIONS,
        pomodoros=zehava_timer["pomodoros"], focused=zehava_timer["focused"],
        snooze_options=SNOOZE_OPTIONS,
        month=zehava_calendar(now, t),
    )


@app.route("/zehava/login", methods=["GET", "POST"])
def zehava_login():
    lang, motion, name = zehava_settings()
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:30]
        if name:
            response = redirect(url_for("zehava"))
            response.set_cookie("name", name, max_age=60 * 60 * 24 * 365)
            return response
    return render_template("zehava/login.html", lang=lang, t=ZEHAVA_TEXTS[lang], motion=motion)


@app.route("/zehava/logout")
def zehava_logout():
    response = redirect(url_for("zehava_login"))
    response.delete_cookie("name")
    return response


@app.route("/zehava/lang/<code>")
def zehava_lang(code):
    back = request.args.get("next", "")
    response = redirect(back if back.startswith("/zehava") else url_for("zehava"))
    if code in ZEHAVA_TEXTS:
        response.set_cookie("lang", code)
    return response


@app.route("/zehava/motion/<state>")
def zehava_motion(state):
    # מי שהתנועה ברקע מסיחה אותה יכולה לעצור אותה
    response = redirect(url_for("zehava"))
    if state in ("on", "off"):
        response.set_cookie("motion", state)
    return response


# ---------- משימות ----------
@app.route("/zehava/add", methods=["POST"])
def zehava_add():
    text = request.form.get("text", "").strip()
    tag = request.form.get("tag", "")
    if text:
        zehava_tasks.append({
            "text": text,
            "time": request.form.get("time", ""),
            "tag": tag if tag in ZEHAVA_TAGS else "",
            "done": False,
            "steps": [],
            "snoozed": 0,
        })
    return zehava_back_to("todo")


@app.route("/zehava/toggle/<int:task_id>", methods=["POST"])
def zehava_toggle(task_id):
    if 0 <= task_id < len(zehava_tasks):
        zehava_tasks[task_id]["done"] = not zehava_tasks[task_id]["done"]
    return zehava_back_to("todo")


@app.route("/zehava/delete/<int:task_id>", methods=["POST"])
def zehava_delete(task_id):
    if 0 <= task_id < len(zehava_tasks):
        zehava_tasks.pop(task_id)
        focus_task = zehava_focus["task"]
        if focus_task is not None and focus_task >= task_id:
            zehava_focus["task"] = None if focus_task == task_id else focus_task - 1
    return zehava_back_to("todo")


# ---------- צעדים קטנים בתוך משימה ----------
def zehava_back_from_steps(task_id):
    # חוזרים למקום שממנו הגיעו: מצב מיקוד, או המשימה בלוח כשהצעדים פתוחים
    if request.form.get("back") == "focus":
        return redirect(url_for("zehava_focus_page"))
    return redirect(url_for("zehava", open=task_id) + f"#task-{task_id}")


@app.route("/zehava/steps/add/<int:task_id>", methods=["POST"])
def zehava_step_add(task_id):
    text = request.form.get("text", "").strip()
    if text and 0 <= task_id < len(zehava_tasks):
        zehava_tasks[task_id]["steps"].append({"text": text[:80], "done": False})
    return zehava_back_from_steps(task_id)


@app.route("/zehava/steps/toggle/<int:task_id>/<int:step_id>", methods=["POST"])
def zehava_step_toggle(task_id, step_id):
    if 0 <= task_id < len(zehava_tasks) and 0 <= step_id < len(zehava_tasks[task_id]["steps"]):
        step = zehava_tasks[task_id]["steps"][step_id]
        step["done"] = not step["done"]
    return zehava_back_from_steps(task_id)


@app.route("/zehava/steps/delete/<int:task_id>/<int:step_id>", methods=["POST"])
def zehava_step_delete(task_id, step_id):
    if 0 <= task_id < len(zehava_tasks) and 0 <= step_id < len(zehava_tasks[task_id]["steps"]):
        zehava_tasks[task_id]["steps"].pop(step_id)
    return zehava_back_from_steps(task_id)


@app.route("/zehava/goal", methods=["POST"])
def zehava_set_goal():
    zehava_goal["text"] = request.form.get("goal", "").strip()[:60]
    return zehava_back_to("top")


# ---------- פתקיות ----------
@app.route("/zehava/notes/add", methods=["POST"])
def zehava_note_add():
    text = request.form.get("text", "").strip()
    color = request.form.get("color", "yellow")
    if text:
        zehava_notes.append({"text": text[:120], "color": color if color in NOTE_COLORS else "yellow"})
    return zehava_back_to("notes")


@app.route("/zehava/notes/delete/<int:note_id>", methods=["POST"])
def zehava_note_delete(note_id):
    if 0 <= note_id < len(zehava_notes):
        zehava_notes.pop(note_id)
    return zehava_back_to("notes")


# ---------- טיימר עגבנייה ----------
@app.route("/zehava/timer/<int:minutes>", methods=["POST"])
def zehava_timer_set(minutes):
    if minutes in TIMER_OPTIONS:
        zehava_timer["minutes"] = minutes
        zehava_timer["ends_at"] = None
    return zehava_back_to("timer")


@app.route("/zehava/timer/start", methods=["POST"])
def zehava_timer_start():
    zehava_timer["ends_at"] = zehava_now() + timedelta(minutes=zehava_timer["minutes"])
    return zehava_back_to("timer")


@app.route("/zehava/timer/reset", methods=["POST"])
def zehava_timer_reset():
    zehava_timer["ends_at"] = None
    return zehava_back_to("timer")


# ---------- נודניק: דוחה את המשימה הבאה שיש לה שעה ----------
@app.route("/zehava/snooze/<int:minutes>", methods=["POST"])
def zehava_snooze(minutes):
    timed = sorted((task for task in zehava_tasks if task["time"] and not task["done"]),
                   key=lambda task: task["time"])
    if timed and minutes in SNOOZE_OPTIONS:
        task = timed[0]
        now = zehava_now()
        hour, minute = map(int, task["time"].split(":"))
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        start = max(due, now)   # אם השעה כבר עברה, דוחים מעכשיו
        task["time"] = (start + timedelta(minutes=minutes)).strftime("%H:%M")
        task["snoozed"] += 1    # למידה עדינה: סופרים דחיות, בלי עונש
    return zehava_back_to("snooze")


# ---------- מצב מיקוד: נא לא להפריע ----------
@app.route("/zehava/focus")
def zehava_focus_page():
    lang, motion, name = zehava_settings()
    if not name:
        return redirect(url_for("zehava_login"))
    chosen = request.args.get("task", type=int)
    if chosen is not None and 0 <= chosen < len(zehava_tasks):
        zehava_focus["task"] = chosen
    i = zehava_focus_task()
    return render_template(
        "zehava/focus.html",
        lang=lang, t=ZEHAVA_TEXTS[lang], motion=motion, name=name, icons=ZEHAVA_ICONS,
        task_id=i, task=zehava_tasks[i] if i is not None else None,
        tags=ZEHAVA_TAGS, lang_index=0 if lang == "he" else 1,
        focus=zehava_focus_state(zehava_now()), focus_options=FOCUS_OPTIONS,
    )


@app.route("/zehava/focus/start/<int:minutes>", methods=["POST"])
def zehava_focus_start(minutes):
    # 0 = מצב גמיש, בלי שעת סיום
    if minutes in FOCUS_OPTIONS or minutes in (0, 5):
        now = zehava_now()
        zehava_focus["minutes"] = minutes
        zehava_focus["started"] = now
        zehava_focus["ends_at"] = now + timedelta(minutes=minutes) if minutes else None
        zehava_focus["finished"] = False
    return redirect(url_for("zehava_focus_page"))


@app.route("/zehava/focus/done", methods=["POST"])
def zehava_focus_done():
    # סיימתי את המשימה: מסמנים אותה, והטיימר ממשיך עם המשימה הבאה
    i = zehava_focus_task()
    if i is not None:
        zehava_tasks[i]["done"] = True
    return redirect(url_for("zehava_focus_page"))


@app.route("/zehava/focus/leave", methods=["POST"])
def zehava_focus_leave():
    # יוצאים בלי עונש: הדקות שכבר עברו נספרות כזמן ריכוז
    if zehava_focus["started"]:
        zehava_timer["focused"] += int((zehava_now() - zehava_focus["started"]).total_seconds() // 60)
    zehava_focus.update(started=None, ends_at=None, finished=False)
    return zehava_back_to("top")


# ---------- Soundscape ----------
@app.route("/zehava/sounds")
def zehava_sounds():
    lang, motion, name = zehava_settings()
    if not name:
        return redirect(url_for("zehava_login"))
    # המועדף: המרחב שהכי הרבה פעמים "עזר לי"
    scores = {key: votes["yes"] - votes["no"] for key, votes in zehava_sound_votes.items()}
    favorite = max(scores, key=scores.get) if any(v["yes"] for v in zehava_sound_votes.values()) else None
    return render_template(
        "zehava/sounds.html",
        lang=lang, t=ZEHAVA_TEXTS[lang], motion=motion, name=name, icons=ZEHAVA_ICONS,
        spaces=SOUND_SPACES, votes=zehava_sound_votes, favorite=favorite,
    )


@app.route("/zehava/sounds/vote/<space>/<answer>", methods=["POST"])
def zehava_sound_vote(space, answer):
    # 204 = הדף לא נטען מחדש, אז המוזיקה ממשיכה לנגן
    if space in zehava_sound_votes and answer in ("yes", "no"):
        zehava_sound_votes[space][answer] += 1
    return "", 204


# ---------- שליחת הסיכום היומי למייל בלחיצה ----------
@app.route("/zehava/mail/send", methods=["POST"])
def zehava_mail_send():
    zehava_send_summary()
    return zehava_back_to("summary")


@app.route("/yair")
def yair():
    return render_page("יאיר", PERSON_CONTENT, name="יאיר", slug="yair")


@app.route("/guy")
def guy():
    return render_page("גיא", PERSON_CONTENT, name="גיא", slug="guy")


@app.route("/hillel")
def hillel():
    return render_page("הלל", PERSON_CONTENT, name="הלל", slug="hillel")


@app.route("/harel")
def harel():
    return render_page("הראל", PERSON_CONTENT, name="הראל", slug="harel")


@app.route("/ariel")
def ariel():
    return render_page("אריאל", PERSON_CONTENT, name="אריאל", slug="ariel")


@app.route("/api/health")
def health():
    return jsonify(status="ok")


@app.route("/api/echo", methods=["POST"])
def echo():
    return jsonify(received=request.get_json(silent=True))


@app.errorhandler(404)
def not_found(e):
    return jsonify(error="not found"), 404


if __name__ == "__main__":
    app.run(debug=True)
