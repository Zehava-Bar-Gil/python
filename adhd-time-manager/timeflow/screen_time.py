"""זמן מסך: שער כוונה, יעד יומי לכל רשת, ותמונת שבוע.

אתר לא יכול לראות או לחסום אפליקציות אחרות בטלפון. לכן כל המספרים כאן הם דיווח עצמי:
מה שנבחר בשער ("לכמה זמן?") או מה שנרשם ידנית (למשל מזמן מסך באייפון).
דקות שנרשמו גוברות על הזמן שתוכנן בשער באותו יום. אין ציון ואין עונש, רק מידע.
"""
from collections import defaultdict
from datetime import timedelta
from urllib.parse import urlsplit

# הרשתות: מפתח, שם (שם מוצר, לא מתורגם) וכתובת. השער מעביר רק לכתובות האלה, ולכן אין הפניה פתוחה
# WhatsApp: הגרסה לדפדפן (WhatsApp Web). בטלפון אפשר לפתוח משם את האפליקציה
APPS = {
    "whatsapp": ("WhatsApp", "https://web.whatsapp.com/"),
    "instagram": ("Instagram", "https://www.instagram.com/"),
    "facebook": ("Facebook", "https://www.facebook.com/"),
    "tiktok": ("TikTok", "https://www.tiktok.com/"),
    "youtube": ("YouTube", "https://www.youtube.com/"),
    "x": ("X", "https://x.com/"),
}
REASONS = ("message", "check", "break", "habit", "other")
GATE_MINUTES = (5, 10, 15, 30)
LIMIT_MIN, LIMIT_MAX = 5, 600
LOG_MAX = 24 * 60
NOTE_MAX = 100
# הפרש קטן מזה (בדקות לשבוע) נחשב "בערך אותו דבר"
SAME_WEEK_MARGIN = 15


def app_origins():
    # הכתובות שהשער רשאי להעביר אליהן אחרי שליחת הטופס (CSP form-action)
    return sorted({"{0.scheme}://{0.netloc}".format(urlsplit(url)) for _, url in APPS.values()})


def parse_minutes(text, low, high):
    # מספר שלם בטווח, או None. ריק מחזיר "" כדי להבדיל בין "לא מולא" לבין "לא תקין"
    text = (text or "").strip()
    if not text:
        return ""
    if not text.isdigit():
        return None
    value = int(text)
    return value if low <= value <= high else None


def usage(log_rows, visit_rows):
    # {(יום, רשת): (דקות, מקור)}. מקור: logged (נרשם) או planned (לפי השער)
    planned = defaultdict(int)
    for visit in visit_rows:
        if visit["opened"] and visit["minutes"]:
            planned[(visit["day"], visit["app"])] += visit["minutes"]
    result = {key: (minutes, "planned") for key, minutes in planned.items()}
    for row in log_rows:
        result[(row["day"], row["app"])] = (row["minutes"], "logged")
    return result


def shown_apps(limits, used_today):
    # רשתות במעקב, ועוד כל רשת שיש לה נתונים היום. אם אין כלום עדיין: כל הרשתות
    keys = [key for key in APPS if key in limits or key in used_today]
    return keys or list(APPS)


def today_rows(limits, day_usage):
    # שורה לכל רשת שמוצגת היום: כמה, מתוך כמה, ומה המקור
    used_today = {app: value for app, value in day_usage.items()}
    rows = []
    for key in shown_apps(limits, used_today):
        minutes, source = used_today.get(key, (0, "none"))
        limit = limits.get(key)
        rows.append({
            "app": key, "name": APPS[key][0], "minutes": minutes, "source": source, "limit": limit,
            "percent": min(100, round(minutes * 100 / limit)) if limit else 0,
            "over": bool(limit) and minutes > limit,
        })
    return rows


def day_usage(all_usage, day):
    # {רשת: (דקות, מקור)} ליום אחד
    day = day.isoformat()
    return {app: value for (row_day, app), value in all_usage.items() if row_day == day}


def week_summary(all_usage, limits, visit_rows, today):
    # שבעת הימים האחרונים (כולל היום) מול שבעת הימים שלפניהם
    totals = defaultdict(int)
    for (day, _app), (minutes, _source) in all_usage.items():
        totals[day] += minutes
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    this_week = sum(totals[day.isoformat()] for day in days)
    last_week = sum(totals[(day - timedelta(days=7)).isoformat()] for day in days)
    goal = sum(limits.values())
    top = max([goal] + [totals[day.isoformat()] for day in days]) or 1
    bars = [{
        "day": day,
        "minutes": totals[day.isoformat()],
        "height": round(totals[day.isoformat()] * 100 / top),
        "over": bool(goal) and totals[day.isoformat()] > goal,
        "weekday": (day.weekday() + 1) % 7,   # 0 = יום ראשון, כמו ברשימת weekdays בטקסטים
    } for day in days]
    first_day = days[0].isoformat()
    skipped = sum(1 for visit in visit_rows if not visit["opened"] and visit["day"] >= first_day)
    diff = this_week - last_week
    if not this_week and not last_week:
        trend = "empty"
    elif not last_week:
        trend = "first"
    elif abs(diff) <= SAME_WEEK_MARGIN:
        trend = "same"
    else:
        trend = "less" if diff < 0 else "more"
    return {
        "bars": bars, "total": this_week, "previous": last_week, "diff": abs(diff), "trend": trend,
        "average": round(this_week / 7), "goal": goal, "goal_height": round(goal * 100 / top) if goal else 0,
        "skipped": skipped,
    }
