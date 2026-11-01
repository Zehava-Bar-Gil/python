"""הודעות מוטיבציה לפי מצב: משפט אחד, חם וקצר, שמתאים למה שקורה עכשיו.

- כללים קבועים ופשוטים, בלי למידה ובלי שיפוט. אין הודעה שמאשימה או סופרת מה לא נעשה.
- לכל מצב יש שני ניסוחים שמתחלפים מיום ליום, כדי שההודעה לא תהפוך לרעש קבוע.
- אם אף מצב לא מתאים, מוצגת ההבטחה הרגילה של האתר.
"""
from datetime import timedelta

from . import clock, journey

BUSY_DAY_TASKS = 5        # מכמה משימות להיום היום נחשב עמוס
BREAK_AFTER_TASKS = 3     # אחרי כמה משימות שהושלמו היום מציעים הפסקה
EVENING_HOUR = 21
AWAY_DAYS = 2             # כמה ימים בלי פעילות נחשבים "חזרה"


def _done_today(tasks, start, end):
    return sum(1 for task in tasks if task["completed_at"] and start <= task["completed_at"] < end)


def pick(repo, user_id, now, tasks):
    """מחזיר מפתח טקסט (למשל "mot_busy_1"), או None כשאין מצב מיוחד."""
    today = now.date()
    start, end = clock.day_bounds(today)
    points_today = repo.journey_points(user_id, start, end)
    state = None
    if now.hour >= EVENING_HOUR:
        state = "evening"
    elif _done_today(tasks, start, end) >= BREAK_AFTER_TASKS:
        state = "break"
    elif points_today == 0:
        # עוד לא התחלנו היום: חזרה אחרי הפסקה, או המשך ליום טוב של אתמול
        last_at = repo.last_journey_at(user_id)
        yesterday = repo.journey_points(user_id, *clock.day_bounds(today - timedelta(days=1)))
        if last_at and last_at < clock.day_bounds(today - timedelta(days=AWAY_DAYS - 1))[0]:
            state = "back"
        elif yesterday >= journey.DAILY_POINTS:
            state = "after_good_day"
    if state is None:
        due_today = sum(1 for task in tasks if task["status"] == "open" and task["due_date"] == today.isoformat())
        if due_today >= BUSY_DAY_TASKS:
            state = "busy"
    if state is None:
        return None
    return f"mot_{state}_{today.toordinal() % 2}"
