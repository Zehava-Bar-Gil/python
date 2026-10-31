"""מנוע ההתאמה האישית (Personal Adaptation Engine).

Python טהור: מקבל היסטוריה (History) ומחזיר תובנות. בלי Flask ובלי מסד נתונים,
ולכן אפשר לבדוק אותו עם נתונים סינתטיים בלבד.

שלושה שלבים:
1. כללים שקופים: תנאי פשוט + מספר תצפיות מינימלי.
2. דפוסים אישיים: השוואה בין שתי קבוצות של ימים, משימות או סשנים. מוצג כקשר ולא כסיבה.
3. בחירה: לכל היותר תובנה אחת בכל פעם, עם השהיה להצעות שנדחו.

אין כאן אבחנות, אין ניחוש של מצב נפשי, ואין מודל Machine Learning: עם מעט נתונים
כללים שקופים מדויקים יותר, ואפשר להסביר כל תוצאה.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import mean

# כמה תצפיות צריך לפני שמציעים משהו
MIN_SHORT_SESSIONS = 4
MIN_LONG_SESSIONS = 3
MIN_POSTPONED_TASKS = 2
MIN_START_HELP = 3
MIN_OVERLOAD_DAYS = 2
OVERLOAD_WINDOW = 5
MIN_DAYS_PER_GROUP = 3
MIN_TASKS_PER_GROUP = 5
MIN_SESSIONS_PER_GROUP = 4
MIN_SOUND_VOTES = 3

# השהיה אחרי תגובה: הצעה שנדחתה לא חוזרת 21 יום, ו"לא מדויק" לא חוזר לעולם
COOLDOWN_DAYS = {"dismissed": 21, "accepted": 14}

SMALL_START_SECONDS = 10 * 60
SHORT_SESSION_SECONDS = 15 * 60
LONG_SESSION_SECONDS = 25 * 60
HEAVY_PLAN = 5


@dataclass
class DayRecord:
    day: date
    rating: int = None                  # דיווח עצמי 1-5, או None
    reasons: tuple = ()                 # דיווח עצמי
    focus_sessions: int = 0             # נמדד
    small_start: bool = False           # נמדד: הסשן הראשון ביום היה עד 10 דקות
    avg_planned_minutes: float = None   # נמדד
    planned_tasks: int = 0              # נמדד: משימות שנוספו או תוכננו ליום הזה
    focus_seconds: int = 0
    planned_seconds: int = 0


@dataclass
class TaskRecord:
    id: int
    has_steps: bool
    started: bool
    snooze_count: int
    status: str


@dataclass
class SessionRecord:
    kind: str
    planned_seconds: int
    status: str
    started_at: object      # datetime
    ended_at: object        # datetime או None


@dataclass
class History:
    today: date
    days: list = field(default_factory=list)
    tasks: list = field(default_factory=list)
    sessions: list = field(default_factory=list)
    sound_feedback: dict = field(default_factory=dict)   # space -> {"yes", "no", "total"}
    start_help_requests: int = 0
    feedback: list = field(default_factory=list)          # [(rule_id, status, date)]
    settings: dict = field(default_factory=dict)


@dataclass
class Insight:
    rule_id: str
    kind: str               # "rule" או "pattern"
    params: dict
    evidence: dict          # {"measured": {...}, "self_reported": {...}}
    action: str = None      # מה קורה כשלוחצים "לנסות"
    strength: float = 0.5   # לסדר בין כמה תובנות
    correlation: bool = False

    @property
    def message_key(self):
        return f"insight_{self.rule_id}"


def _rate(part, whole):
    return round(100 * part / whole) if whole else 0


def _avg(values):
    return round(mean(values), 1) if values else None


# ---------- שלב 1: כללים שקופים ----------
def rule_short_sessions(h):
    planned = [s for s in h.sessions if s.kind == "focus" and s.planned_seconds and s.status in ("completed", "stopped")]
    short = [s for s in planned if s.planned_seconds <= SHORT_SESSION_SECONDS]
    long = [s for s in planned if s.planned_seconds >= LONG_SESSION_SECONDS]
    if len(short) < MIN_SHORT_SESSIONS or len(long) < MIN_LONG_SESSIONS:
        return None
    if h.settings.get("focus_minutes", 25) <= 15:
        return None
    short_rate = _rate(sum(s.status == "completed" for s in short), len(short))
    long_rate = _rate(sum(s.status == "completed" for s in long), len(long))
    if short_rate < 70 or long_rate > 50 or short_rate - long_rate < 25:
        return None
    return Insight("short_sessions", "rule",
                   {"limit": 15, "short_rate": short_rate, "long_rate": long_rate, "suggest": 15},
                   {"measured": {"short_sessions": len(short), "short_completed_pct": short_rate,
                                 "long_sessions": len(long), "long_completed_pct": long_rate}},
                   action="set_focus:15", strength=(short_rate - long_rate) / 100)


def rule_split_postponed(h):
    stuck = [t for t in h.tasks if t.status == "open" and t.snooze_count >= 2 and not t.has_steps]
    if len(stuck) < MIN_POSTPONED_TASKS:
        return None
    first = max(stuck, key=lambda t: t.snooze_count)
    return Insight("split_postponed", "rule", {"n": len(stuck)},
                   {"measured": {"postponed_tasks_without_steps": len(stuck), "most_postponed": first.snooze_count}},
                   action=f"open_task:{first.id}", strength=0.6)


def rule_hard_start(h):
    if h.start_help_requests < MIN_START_HELP or h.settings.get("focus_minutes", 25) <= 10:
        return None
    return Insight("hard_start", "rule", {"n": h.start_help_requests, "suggest": 10},
                   {"measured": {"start_help_requests_14_days": h.start_help_requests}},
                   action="set_focus:10", strength=0.5)


def rule_overloaded(h):
    answered = [d for d in sorted(h.days, key=lambda d: d.day) if d.rating is not None][-OVERLOAD_WINDOW:]
    heavy = sum("tired" in d.reasons for d in answered)
    if heavy < MIN_OVERLOAD_DAYS or h.settings.get("calm_mode"):
        return None
    return Insight("overloaded", "rule", {"n": heavy, "total": len(answered)},
                   {"self_reported": {"days_answered": len(answered), "days_tired_or_overloaded": heavy}},
                   action="calm_mode", strength=0.7)


# ---------- שלב 2: דפוסים אישיים ----------
def pattern_small_start(h):
    rated = [d for d in h.days if d.rating is not None and d.focus_sessions]
    with_small = [d.rating for d in rated if d.small_start]
    without = [d.rating for d in rated if not d.small_start]
    if len(with_small) < MIN_DAYS_PER_GROUP or len(without) < MIN_DAYS_PER_GROUP:
        return None
    a, b = _avg(with_small), _avg(without)
    if a - b < 0.5:
        return None
    return Insight("small_start", "pattern",
                   {"limit": SMALL_START_SECONDS // 60, "with_avg": a, "without_avg": b, "days": len(rated)},
                   {"measured": {"days_with_small_start": len(with_small), "days_without": len(without)},
                    "self_reported": {"avg_rating_with": a, "avg_rating_without": b}},
                   action="start_small_session", strength=min(1.0, (a - b) / 2), correlation=True)


def pattern_focus_length(h):
    rated = [d for d in h.days if d.rating is not None and d.avg_planned_minutes]
    short = [d.rating for d in rated if d.avg_planned_minutes <= 20]
    long = [d.rating for d in rated if d.avg_planned_minutes > 20]
    if len(short) < MIN_DAYS_PER_GROUP or len(long) < MIN_DAYS_PER_GROUP:
        return None
    a, b = _avg(short), _avg(long)
    if abs(a - b) < 0.5:
        return None
    current = h.settings.get("focus_minutes", 25)
    action = "set_focus:15" if a > b and current > 20 else ("set_focus:25" if b > a and current <= 20 else None)
    return Insight("focus_length", "pattern", {"limit": 20, "short_avg": a, "long_avg": b, "days": len(rated)},
                   {"measured": {"days_short_sessions": len(short), "days_long_sessions": len(long)},
                    "self_reported": {"avg_rating_short": a, "avg_rating_long": b}},
                   action=action, strength=min(1.0, abs(a - b) / 2) * 0.9, correlation=True)


def pattern_steps_start(h):
    with_steps = [t for t in h.tasks if t.has_steps]
    without = [t for t in h.tasks if not t.has_steps]
    if len(with_steps) < MIN_TASKS_PER_GROUP or len(without) < MIN_TASKS_PER_GROUP:
        return None
    a = _rate(sum(t.started for t in with_steps), len(with_steps))
    b = _rate(sum(t.started for t in without), len(without))
    if a - b < 20:
        return None
    target = next((t for t in h.tasks if t.status == "open" and not t.has_steps), None)
    return Insight("steps_start", "pattern",
                   {"with_rate": a, "without_rate": b, "n": len(with_steps) + len(without)},
                   {"measured": {"tasks_with_steps": len(with_steps), "started_pct_with": a,
                                 "tasks_without_steps": len(without), "started_pct_without": b}},
                   action=f"open_task:{target.id}" if target else None, strength=min(1.0, (a - b) / 100 + 0.3),
                   correlation=True)


def pattern_breaks_return(h):
    focus = sorted((s for s in h.sessions if s.kind == "focus" and s.status == "completed" and s.ended_at),
                   key=lambda s: s.started_at)
    groups = {True: [], False: []}
    for session in focus:
        took_break = any(b.kind != "focus" and session.ended_at <= b.started_at <= session.ended_at + timedelta(minutes=15)
                         for b in h.sessions)
        returned = any(f.kind == "focus" and session.ended_at < f.started_at <= session.ended_at + timedelta(minutes=60)
                       for f in h.sessions)
        groups[took_break].append(returned)
    if len(groups[True]) < MIN_SESSIONS_PER_GROUP or len(groups[False]) < MIN_SESSIONS_PER_GROUP:
        return None
    a, b = _rate(sum(groups[True]), len(groups[True])), _rate(sum(groups[False]), len(groups[False]))
    if a - b < 20:
        return None
    return Insight("breaks_return", "pattern", {"with_rate": a, "without_rate": b, "n": len(focus)},
                   {"measured": {"sessions_with_break": len(groups[True]), "returned_pct_with": a,
                                 "sessions_without_break": len(groups[False]), "returned_pct_without": b}},
                   strength=min(1.0, (a - b) / 100 + 0.2), correlation=True)


def pattern_sound_helped(h):
    if not should_offer_sounds(h):
        return None
    good = [(space, c) for space, c in h.sound_feedback.items()
            if c["total"] >= MIN_SOUND_VOTES and c["yes"] / c["total"] >= 0.7]
    if not good:
        return None
    space, counts = max(good, key=lambda pair: (pair[1]["yes"] / pair[1]["total"], pair[1]["total"]))
    return Insight("sound_helped", "pattern", {"space": space, "yes": counts["yes"], "total": counts["total"]},
                   {"self_reported": {"space": space, "helped": counts["yes"], "votes": counts["total"]}},
                   action=f"try_sound:{space}", strength=0.4)


def pattern_planning_load(h):
    answered = [d for d in h.days if d.rating is not None]
    heavy = [d for d in answered if d.planned_tasks > HEAVY_PLAN]
    light = [d for d in answered if d.planned_tasks <= HEAVY_PLAN]
    if len(heavy) < MIN_DAYS_PER_GROUP or len(light) < MIN_DAYS_PER_GROUP:
        return None
    a = _rate(sum("tired" in d.reasons for d in heavy), len(heavy))
    b = _rate(sum("tired" in d.reasons for d in light), len(light))
    if a - b < 30:
        return None
    return Insight("planning_load", "pattern", {"limit": HEAVY_PLAN, "heavy_rate": a, "light_rate": b},
                   {"measured": {"heavy_days": len(heavy), "light_days": len(light)},
                    "self_reported": {"overload_pct_heavy": a, "overload_pct_light": b}},
                   strength=min(1.0, (a - b) / 100 + 0.2), correlation=True)


RULES = [rule_overloaded, rule_short_sessions, rule_split_postponed, rule_hard_start]
PATTERNS = [pattern_small_start, pattern_focus_length, pattern_steps_start, pattern_breaks_return,
            pattern_sound_helped, pattern_planning_load]


def should_offer_sounds(h):
    # מי שבחרה "בלי צלילים", או סימנה כמה פעמים "פחות" בלי אף "עזר", לא מקבלת הצעות צליל
    if h.settings.get("sound_pref") == "none":
        return False
    yes = sum(c["yes"] for c in h.sound_feedback.values())
    no = sum(c["no"] for c in h.sound_feedback.values())
    return not (yes == 0 and no >= MIN_SOUND_VOTES)


def evaluate(history):
    # כל התובנות האפשריות, מהחזקה לחלשה
    found = [check(history) for check in RULES + PATTERNS]
    return sorted((i for i in found if i), key=lambda i: i.strength, reverse=True)


def in_cooldown(rule_id, feedback, today):
    for fb_rule, status, day in feedback:
        if fb_rule != rule_id:
            continue
        if status == "corrected":
            return True
        days = COOLDOWN_DAYS.get(status)
        if days and today - day < timedelta(days=days):
            return True
    return False


def choose(history):
    # שלב 3: תובנה אחת בלבד, או None
    for insight in evaluate(history):
        if not in_cooldown(insight.rule_id, history.feedback, history.today):
            return insight
    return None


def overview(history, days=14):
    # הפירוט באזור התובנות: מעט מדדים, כל אחד עם המקור שלו
    first = history.today - timedelta(days=days - 1)
    recent = sorted((d for d in history.days if d.day >= first), key=lambda d: d.day)
    by_day = {d.day: d for d in recent}
    series = []
    for offset in range(days):
        day = first + timedelta(days=offset)
        record = by_day.get(day)
        series.append({"day": day, "focus_minutes": (record.focus_seconds // 60) if record else 0,
                       "rating": record.rating if record else None})
    peak = max((point["focus_minutes"] for point in series), default=0) or 1
    for point in series:
        point["height"] = round(100 * point["focus_minutes"] / peak)
    started = sum(t.started for t in history.tasks)
    feedback_counts = {status: sum(1 for _, s, _ in history.feedback if s == status)
                       for status in ("accepted", "dismissed", "corrected")}
    return {
        "series": series,
        "start_rate": {"started": started, "total": len(history.tasks)},
        "planned_minutes": sum(d.planned_seconds for d in recent) // 60,
        "actual_minutes": sum(d.focus_seconds for d in recent) // 60,
        "sounds": {space: c for space, c in history.sound_feedback.items() if c["total"]},
        "feedback": feedback_counts,
    }
