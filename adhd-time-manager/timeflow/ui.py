"""מה שמשותף לתצוגה: אייקונים, תפריטים, ברכה ולוח חודשי."""
import calendar

from . import clock

# אייקונים בקו דק (נתיבי SVG בגודל 24x24). הועברו מ-app.py של גרסה 1, ונוספו כמה חדשים
ICONS = {
    "todo": "M9 11l3 3L22 4 M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
    "notes": "M16 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8Z M15 3v4a2 2 0 0 0 2 2h4",
    "timer": "M10 2h4 M12 14l3-3 M4 14a8 8 0 1 0 16 0a8 8 0 1 0-16 0",
    # עגבנייה בקו דק, באותו סגנון של שאר האייקונים (שקוף, בצבע הטקסט)
    "tomato": "M12 8c-4.4 0-8 2.6-8 6.4S7.6 21 12 21s8-2.8 8-6.6S16.4 8 12 8z M12 8V4.5 M12 8c-1.2-1.6-3-2.2-4.6-1.8 M12 8c1.2-1.6 3-2.2 4.6-1.8 M12 8l-2 2.2 M12 8l2 2.2",
    "snooze": "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z",
    "calendar": "M8 2v4 M16 2v4 M3 10h18 M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
    "home": "M3 10l9-7 9 7v10a2 2 0 0 1-2 2h-4v-7H9v7H5a2 2 0 0 1-2-2z",
    "today": "M9 11l3 3L22 4 M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
    "progress_nav": "M3 3v18h18 M7 16v-4 M12 16V8 M17 16v-7",
    "settings": "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
    "mountain": "M2 20l7-12 4 6 3-4 6 10z M9 8l2 3",
    "linkedin": "M4 4h16v16H4z M8 11v5 M8 8v.01 M12 16v-5 M12 13a2 2 0 0 1 4 0v3",
    "sun": "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z M12 1v2 M12 21v2 M4.2 4.2l1.4 1.4 M18.4 18.4l1.4 1.4 M1 12h2 M21 12h2 M4.2 19.8l1.4-1.4 M18.4 5.6l1.4-1.4",
    "moon": "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z",
    "clock": "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 6v6l4 2",
    "plus": "M12 5v14 M5 12h14",
    "play": "M7 4l13 8-13 8z",
    "pause": "M7 4h3v16H7z M14 4h3v16h-3z",
    "reset": "M3 12a9 9 0 1 0 3-6.7L3 8 M3 3v5h5",
    "flag": "M4 22V4 M4 4h13l-2 4 2 4H4",
    "focus": "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12z M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
    "headphones": "M3 18v-6a9 9 0 0 1 18 0v6 M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z",
    "mail": "M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z M22 6l-10 7L2 6",
    "steps": "M8 6h13 M8 12h13 M8 18h13 M3 6h.01 M3 12h.01 M3 18h.01",
    "exit": "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9",
    "check": "M20 6L9 17l-5-5",
    "edit": "M12 20h9 M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z",
    "trash": "M3 6h18 M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2 M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6",
    "sparkle": "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z M19 16l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z",
    "send": "M22 2L11 13 M22 2l-7 20-4-9-9-4z",
    "refresh": "M21 12a9 9 0 1 1-3-6.7L21 8 M21 3v5h-5",
    "unlink": "M18.8 13.4l1.4-1.4a5 5 0 0 0-7.1-7.1l-1.4 1.4 M5.2 10.6l-1.4 1.4a5 5 0 0 0 7.1 7.1l1.4-1.4 M8 2v3 M2 8h3 M16 22v-3 M22 16h-3",
    "download": "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3",
    "lock": "M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z M7 11V7a5 5 0 0 1 10 0v4",
    "eye": "M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "heart": "M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.5 1-1.1a5.5 5.5 0 0 0 0-7.8z",
    "prev": "M15 18l-6-6 6-6",
    "next": "M9 18l6-6-6-6",
    "chevron": "M6 9l6 6 6-6",
    "pin": "M12 17v5 M9 10.8a2 2 0 0 1-1.1 1.8l-1.8.9A2 2 0 0 0 5 15.2V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.8a2 2 0 0 0-1.1-1.8l-1.8-.9a2 2 0 0 1-1.1-1.8V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z",
    "leaf": "M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.5 19 2c1 2 2 4.2 2 8 0 5.5-4.8 10-10 10z M2 21c0-3 1.9-5.4 5.1-6",
    # אייקוני הברכה לפי השעה, באותו קו דק של התפריט: שמש מבין ענן, סהר עם כוכב, ירח מלא שמחייך
    "cloud_sun": "M12 2v2 M4.9 4.9l1.4 1.4 M20 12h2 M19.1 4.9l-1.4 1.4 M15.9 12.7a4 4 0 0 0-5.9-4.1 M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6z",
    "moon_star": "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z M20 3v4 M22 5h-4",
    # ירח בלילה: סהר עם עין עצומה וחיוך, ושני כוכבים קטנים
    "moon_smile": "M13.5 3.2A9 9 0 1 0 20.8 14 7 7 0 0 1 13.5 3.2Z M5.6 12.4q.9.9 1.8 0 M6.6 16.2q1.8 1.4 3.6.2 M18 3v3 M16.5 4.5h3 M21.5 8.5v1.6 M20.7 9.3h1.6",
}

# התפריט העליון: בדיוק חמשת הכלים (מפתח, נתיב, אייקון). הטקסט: nav_<מפתח>
NAV = [
    ("todo", "zehava.tasks", "todo"),
    ("notes", "zehava.notes", "notes"),
    ("timer", "zehava.timer", "timer"),
    ("snooze", "zehava.snooze", "snooze"),
    ("calendar", "zehava.calendar", "calendar"),
]

# סרגל הצד: רק מה שלא נמצא בתפריט העליון (הבית, התובנות וההגדרות), בלי כפילויות
SIDE = [
    ("home", "zehava.home", "home"),
    ("insights", "zehava.insights", "progress_nav"),
    ("settings", "zehava.settings", "settings"),
]

PULSE_FACES = {1: "😣", 2: "😕", 3: "😐", 4: "🙂", 5: "😄"}
PULSE_AFTER_HOUR = 17


def day_part(hour):
    # חלק היום לפי שעון ישראל: קובע את הברכה, את האייקון שלידה ואת מצב התצוגה "לפי השעה"
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


# האייקון שליד הברכה, לכל חלק של היום
def due_years(current=None):
    # השנים ברשימה של תאריך משימה: משנה שעברה ועד חמש שנים קדימה.
    # אם למשימה כבר יש תאריך בשנה אחרת, גם השנה שלה מופיעה
    this_year = clock.today().year
    years = list(range(this_year - 1, this_year + 6))
    year = int(current[:4]) if current else None
    if year and year not in years:
        years = sorted(years + [year])
    return years


DAY_ICONS = {"morning": "cloud_sun", "afternoon": "sun", "evening": "moon_star", "night": "moon_smile"}


def greeting(t, hour):
    return t[day_part(hour)]


def clock_theme(hour):
    # בבוקר ובצהריים בהיר, בערב ובלילה כהה
    return "light" if day_part(hour) in ("morning", "afternoon") else "dark"


# המרחבים הקוליים (Soundscape): מפתח ושם. הקבצים: static/sounds/<מפתח>.ogg ו-.mp3
SOUND_SPACES = {
    "deep": "Deep Focus",
    "calm": "Calm",
    "study": "Study",
    "reading": "Reading & Recall",
}

# אווטארים מוכנים: ארבע דמויות (לפי סוג שיער) ושני סמלים מהנוף של האתר. "letter" = האות הראשונה של השם
AVATARS = ["curls", "long", "bun", "short", "balloon", "mountain"]
AVATAR_CHOICES = ["letter", "photo", *AVATARS]


def first_name(user, lang):
    # השם בשפה של האתר עכשיו. אם הוא חסר, השם בשפה השנייה, ואם גם הוא חסר, השם הכללי
    other = "en" if lang == "he" else "he"
    return user.get(f"first_name_{lang}") or user.get(f"first_name_{other}") or user["display_name"]


def full_name(user, lang):
    other = "en" if lang == "he" else "he"
    last = user.get(f"last_name_{lang}") or user.get(f"last_name_{other}") or ""
    return f"{first_name(user, lang)} {last}".strip()


def is_birthday(birthday, today):
    # יום ההולדת לפי שעון ישראל. מי שנולדה ב-29 בפברואר חוגגת ב-28 בשנה שאינה מעוברת
    if not birthday:
        return False
    month, day = int(birthday[5:7]), int(birthday[8:10])
    if (month, day) == (2, 29) and not calendar.isleap(today.year):
        day = 28
    return (today.month, today.day) == (month, day)


def minutes_label(t, seconds):
    hours, minutes = divmod(int(seconds) // 60, 60)
    return t["hours_minutes"].format(h=hours, m=minutes) if hours else f"{minutes} {t['min']}"


def estimate_label(t, minutes):
    # "כ-15 דק'", ובשעות שלמות או חצאי שעה משפט טבעי: "כשעה", "כשעה וחצי", "כשעתיים"
    return t.get(f"est_{minutes}") or t["est_min"].format(n=minutes)


def month_grid(year, month, marks=None):
    # שבוע מתחיל ביום ראשון. marks: {day_number: מספר פריטים} לנקודות בלוח
    marks = marks or {}
    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(year, month)
    return [[{"day": day, "marks": marks.get(day, 0)} for day in week] for week in weeks]


def shift_month(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1
