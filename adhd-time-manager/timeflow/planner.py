"""תכנון: סדר המשימות, הצעד הבא, ודחייה של משימה עם שעה."""
from datetime import datetime, timedelta

from . import clock

PRIORITY_ORDER = {"important": 0, "normal": 1, "later": 2}
PRIORITIES = list(PRIORITY_ORDER)
SNOOZE_HINT_AFTER = 3   # אחרי כמה דחיות מציעים בעדינות לפרק משימה
SNOOZE_OPTIONS = [5, 10, 15, 30, 60]


def sort_key(task):
    # "חשוב לי" קודם, אחר כך מה שקרוב בזמן, ואחר כך לפי סדר ההוספה
    return (PRIORITY_ORDER.get(task["priority"], 1), task["due_date"] or "9999-12-31",
            task["due_time"] or "99:99", task["id"])


def open_tasks(tasks):
    return sorted((task for task in tasks if task["status"] == "open"), key=sort_key)


def attach_steps(tasks, steps_by_task):
    # מוסיף לכל משימה את הצעדים שלה ואת הצעד הקטן הבא
    for task in tasks:
        steps = steps_by_task.get(task["id"], [])
        task["steps"] = steps
        task["steps_done"] = sum(1 for step in steps if step["done_at"])
        task["next_step"] = next((step for step in steps if not step["done_at"]), None)
    return tasks


def next_task(tasks):
    ordered = open_tasks(tasks)
    return ordered[0] if ordered else None


def needs_split_hint(task):
    # למידה עדינה: משימה שנדחתה כמה פעמים ועדיין אין לה צעדים
    return task["status"] == "open" and task["snooze_count"] >= SNOOZE_HINT_AFTER and not task.get("steps")


def waiting_since(task, today):
    # במקום "באיחור": ניסוח ניטרלי למשימה שהתאריך שלה עבר
    day = clock.parse_day(task["due_date"])
    return day if day and day < today and task["status"] == "open" else None


def task_moment(task, now):
    # התאריך והשעה של משימה כ-datetime בשעון ישראל. בלי תאריך = היום
    day = clock.parse_day(task["due_date"]) or now.date()
    at = clock.parse_hhmm(task["due_time"])
    return datetime.combine(day, at, clock.LOCAL_TZ) if at else None


def next_timed_task(tasks, now):
    timed = [(task_moment(task, now), task) for task in open_tasks(tasks) if task["due_time"]]
    timed = [(moment, task) for moment, task in timed if moment]
    return min(timed, key=lambda pair: (pair[0], pair[1]["id"]))[1] if timed else None


def postpone(task, minutes, now):
    # דוחים מהשעה של המשימה, או מעכשיו אם היא כבר עברה. התאריך מתעדכן גם אחרי חצות
    start = max(task_moment(task, now) or now, now)
    moved = start + timedelta(minutes=minutes)
    return moved.date().isoformat(), moved.strftime("%H:%M")


def clean_due(date_text, time_text):
    # מאמת תאריך ושעה מטופס. ערך לא תקין פשוט לא נשמר
    day = clock.parse_day(date_text)
    at = clock.parse_hhmm(time_text)
    return (day.isoformat() if day else None), (at.strftime("%H:%M") if at else None)
