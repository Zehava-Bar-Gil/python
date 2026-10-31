"""מסע הכדור הפורח: התקדמות מצטברת לפי פעילות אמיתית בלבד.

- נקודות על משימה שהושלמה, צעד שהושלם וסשן מיקוד שהושלם. כניסה לאתר לא נותנת נקודות.
- הנקודות לא יורדות כשמוסיפים משימות, ואין "ימים רעים". רק ביטול סימון מתקן את הספירה.
- כל פריט נספר פעם אחת (UNIQUE במסד).
"""
from . import clock

POINTS = {"task": 3, "step": 1, "session": 1}
POINTS_PER_STATION = 4
STATIONS = 6                                   # 6 נקודות על השביל, האחרונה היא הפסגה
POINTS_PER_CLIMB = POINTS_PER_STATION * STATIONS
# גובה הכדור בשביל (אחוז מגובה התמונה) בכל תחנה, מתחתית השביל ועד הפסגה
BALLOON_TOPS = [76, 72, 66, 57.5, 51, 45, 40]


def record(repo, user_id, kind, ref_id):
    return repo.add_journey_event(user_id, kind, ref_id, POINTS[kind])


def unrecord(repo, user_id, kind, ref_id):
    repo.remove_journey_event(user_id, kind, ref_id)


def balloon_top(stations_float):
    # מיקום רציף בין שתי תחנות, כך שכל נקודה מזיזה את הכדור קצת
    stations_float = max(0.0, min(float(STATIONS), stations_float))
    low = int(stations_float)
    if low >= STATIONS:
        return BALLOON_TOPS[STATIONS]
    frac = stations_float - low
    return round(BALLOON_TOPS[low] + (BALLOON_TOPS[low + 1] - BALLOON_TOPS[low]) * frac, 2)


def position(points):
    climb_index, in_climb = divmod(points, POINTS_PER_CLIMB)
    return {
        "points": points,
        "climb": climb_index + 1,
        "lit": in_climb // POINTS_PER_STATION,
        "to_next": POINTS_PER_STATION - in_climb % POINTS_PER_STATION,
        "top": balloon_top(in_climb / POINTS_PER_STATION),
    }


def view(repo, user_id):
    # מה להציג: מאיפה הכדור טס ולאן. כשעוברים פסגה, הכדור עולה לפסגה וחוגגים
    points = repo.journey_points(user_id)
    shown = min(repo.get_shown_points(user_id), points)
    now_pos, before = position(points), position(shown)
    summit = now_pos["climb"] > before["climb"]
    if summit:
        now_pos = {**now_pos, "lit": STATIONS, "top": BALLOON_TOPS[STATIONS]}
    if shown != points:
        repo.set_shown_points(user_id, points)
    return {**now_pos, "from_top": before["top"], "summit_reached": summit}


def stations_reached(repo, user_id, day):
    # כמה תחנות חדשות נכבשו ביום מסוים (לסיכום היומי)
    start, end = clock.day_bounds(day)
    before = repo.journey_points(user_id, "0000", start)
    during = repo.journey_points(user_id, start, end)
    return (before + during) // POINTS_PER_STATION - before // POINTS_PER_STATION
