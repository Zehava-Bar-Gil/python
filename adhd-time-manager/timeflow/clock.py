"""שעון אחד לכל האתר: זמן ישראל, שמירה ב-UTC, ואפשרות "להקפיא" זמן בבדיקות."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Jerusalem")
_frozen = None   # בבדיקות: זמן קבוע במקום השעון האמיתי


def now():
    return _frozen if _frozen is not None else datetime.now(LOCAL_TZ)


def freeze(moment):
    # משמש רק בבדיקות. None מחזיר את השעון האמיתי
    global _frozen
    _frozen = moment.astimezone(LOCAL_TZ) if moment else None


def to_iso(moment):
    # כל הזמנים נשמרים במסד ב-UTC, בפורמט ISO
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def from_iso(text):
    return datetime.fromisoformat(text).astimezone(LOCAL_TZ) if text else None


def now_iso():
    return to_iso(now())


def today():
    return now().date()


def day_bounds(day):
    # תחילת היום וסופו בשעון ישראל, כמחרוזות UTC לשאילתות
    start = datetime.combine(day, time.min, LOCAL_TZ)
    return to_iso(start), to_iso(start + timedelta(days=1))


def parse_day(text):
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def parse_hhmm(text):
    # "21:00" -> time(21, 0). ערך לא תקין מחזיר None
    try:
        hour, minute = (int(part) for part in text.split(":"))
        return time(hour, minute)
    except (AttributeError, TypeError, ValueError):
        return None
