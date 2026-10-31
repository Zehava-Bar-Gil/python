"""מנוע ההתאמה האישית: כללים, דפוסים ובחירה, עם היסטוריות סינתטיות בלבד.

כל בדיקה בונה History קטנה ביד. אין כאן מסד ואין Flask, חוץ מהבדיקות של הנתיבים בסוף.
"""
import unittest
from datetime import date, datetime, timedelta

from timeflow import clock
from timeflow import personalization_engine as pe
from timeflow.learning_data import build_history

from .helpers import TimeFlowTestCase

TODAY = date(2026, 10, 29)


def history(**fields):
    fields.setdefault("settings", {"focus_minutes": 25, "sound_pref": "ask", "calm_mode": 0})
    return pe.History(today=TODAY, **fields)


def session(kind="focus", minutes=25, status="completed", start=None, length=None):
    start = start or datetime(2026, 10, 20, 9, 0, tzinfo=clock.LOCAL_TZ)
    end = start + timedelta(minutes=length if length is not None else minutes)
    return pe.SessionRecord(kind, minutes * 60, status, start, end)


def day(offset, **fields):
    return pe.DayRecord(day=TODAY - timedelta(days=offset), **fields)


def task(task_id, has_steps=False, started=False, snooze_count=0, status="open"):
    return pe.TaskRecord(task_id, has_steps, started, snooze_count, status)


class RuleTests(unittest.TestCase):
    def test_empty_history_gives_nothing(self):
        self.assertEqual(pe.evaluate(history()), [])
        self.assertIsNone(pe.choose(history()))

    def test_short_sessions_rule(self):
        sessions = [session(minutes=15) for _ in range(4)] + [session(minutes=25, status="stopped") for _ in range(3)]
        insight = pe.rule_short_sessions(history(sessions=sessions))
        self.assertEqual(insight.action, "set_focus:15")
        self.assertEqual(insight.evidence["measured"]["short_completed_pct"], 100)
        self.assertEqual(insight.evidence["measured"]["long_completed_pct"], 0)
        self.assertFalse(insight.correlation)

    def test_short_sessions_needs_enough_observations(self):
        sessions = [session(minutes=15) for _ in range(3)] + [session(minutes=25, status="stopped") for _ in range(3)]
        self.assertIsNone(pe.rule_short_sessions(history(sessions=sessions)))

    def test_short_sessions_skipped_when_already_short(self):
        sessions = [session(minutes=15) for _ in range(4)] + [session(minutes=25, status="stopped") for _ in range(3)]
        h = history(sessions=sessions, settings={"focus_minutes": 15})
        self.assertIsNone(pe.rule_short_sessions(h))

    def test_split_postponed_points_to_most_postponed(self):
        tasks = [task(1, snooze_count=2), task(2, snooze_count=5), task(3, snooze_count=4, has_steps=True)]
        insight = pe.rule_split_postponed(history(tasks=tasks))
        self.assertEqual(insight.action, "open_task:2")
        self.assertEqual(insight.params["n"], 2)
        self.assertIsNone(pe.rule_split_postponed(history(tasks=tasks[:1])))

    def test_hard_start(self):
        self.assertEqual(pe.rule_hard_start(history(start_help_requests=3)).action, "set_focus:10")
        self.assertIsNone(pe.rule_hard_start(history(start_help_requests=2)))

    def test_overloaded_uses_last_five_answers(self):
        days = [day(i, rating=2, reasons=("tired",)) for i in (6, 7)] + [day(i, rating=4) for i in range(5)]
        self.assertIsNone(pe.rule_overloaded(history(days=days)))
        days = [day(i, rating=2, reasons=("tired",)) for i in (0, 1)] + [day(i, rating=4) for i in (2, 3)]
        insight = pe.rule_overloaded(history(days=days))
        self.assertEqual(insight.action, "calm_mode")
        self.assertIn("self_reported", insight.evidence)
        self.assertIsNone(pe.rule_overloaded(history(days=days, settings={"calm_mode": 1})))


class PatternTests(unittest.TestCase):
    def test_small_start(self):
        days = [day(i, rating=4, focus_sessions=2, small_start=True) for i in range(3)] + \
               [day(i, rating=2, focus_sessions=2) for i in range(3, 6)]
        insight = pe.pattern_small_start(history(days=days))
        self.assertTrue(insight.correlation)
        self.assertEqual((insight.params["with_avg"], insight.params["without_avg"]), (4, 2))
        # הבדל קטן מדי לא נחשב
        days = [day(i, rating=3, focus_sessions=1, small_start=True) for i in range(3)] + \
               [day(i, rating=3, focus_sessions=1) for i in range(3, 6)]
        self.assertIsNone(pe.pattern_small_start(history(days=days)))

    def test_focus_length_suggests_direction(self):
        days = [day(i, rating=4, avg_planned_minutes=15) for i in range(3)] + \
               [day(i, rating=2, avg_planned_minutes=45) for i in range(3, 6)]
        self.assertEqual(pe.pattern_focus_length(history(days=days)).action, "set_focus:15")
        h = history(days=days, settings={"focus_minutes": 15})
        self.assertIsNone(pe.pattern_focus_length(h).action)

    def test_steps_start(self):
        tasks = [task(i, has_steps=True, started=True) for i in range(5)] + [task(i) for i in range(5, 10)]
        insight = pe.pattern_steps_start(history(tasks=tasks))
        self.assertEqual((insight.params["with_rate"], insight.params["without_rate"]), (100, 0))
        self.assertEqual(insight.action, "open_task:5")
        self.assertIsNone(pe.pattern_steps_start(history(tasks=tasks[:4] + tasks[5:])))

    def test_breaks_return(self):
        base = datetime(2026, 10, 20, 9, 0, tzinfo=clock.LOCAL_TZ)
        sessions = []
        for i in range(4):     # עם הפסקה: חוזרת למיקוד
            start = base + timedelta(days=i)
            sessions += [session(start=start), session("short_break", 5, start=start + timedelta(minutes=26)),
                         session(start=start + timedelta(minutes=35), status="stopped")]
        for i in range(4, 8):  # בלי הפסקה: לא חוזרת
            sessions.append(session(start=base + timedelta(days=i)))
        insight = pe.pattern_breaks_return(history(sessions=sessions))
        self.assertEqual((insight.params["with_rate"], insight.params["without_rate"]), (100, 0))

    def test_sound_helped_and_opt_out(self):
        feedback = {"calm": {"yes": 3, "no": 0, "total": 3}, "deep": {"yes": 1, "no": 2, "total": 3}}
        self.assertEqual(pe.pattern_sound_helped(history(sound_feedback=feedback)).action, "try_sound:calm")
        self.assertIsNone(pe.pattern_sound_helped(history(sound_feedback=feedback, settings={"sound_pref": "none"})))
        disliked = {"calm": {"yes": 0, "no": 3, "total": 3}}
        self.assertFalse(pe.should_offer_sounds(history(sound_feedback=disliked)))

    def test_planning_load(self):
        days = [day(i, rating=2, reasons=("tired",), planned_tasks=8) for i in range(3)] + \
               [day(i, rating=4, planned_tasks=2) for i in range(3, 6)]
        insight = pe.pattern_planning_load(history(days=days))
        self.assertEqual((insight.params["heavy_rate"], insight.params["light_rate"]), (100, 0))
        self.assertIsNone(insight.action)


class ChoiceTests(unittest.TestCase):
    def rich_history(self, feedback=()):
        sessions = [session(minutes=15) for _ in range(4)] + [session(minutes=25, status="stopped") for _ in range(3)]
        return history(sessions=sessions, start_help_requests=3, feedback=list(feedback))

    def test_one_insight_strongest_first(self):
        h = self.rich_history()
        found = pe.evaluate(h)
        self.assertEqual([i.rule_id for i in found], ["short_sessions", "hard_start"])
        self.assertEqual(pe.choose(h).rule_id, "short_sessions")

    def test_dismissed_waits_21_days(self):
        h = self.rich_history([("short_sessions", "dismissed", TODAY - timedelta(days=3))])
        self.assertEqual(pe.choose(h).rule_id, "hard_start")
        h = self.rich_history([("short_sessions", "dismissed", TODAY - timedelta(days=22))])
        self.assertEqual(pe.choose(h).rule_id, "short_sessions")

    def test_corrected_never_returns(self):
        h = self.rich_history([("short_sessions", "corrected", TODAY - timedelta(days=200)),
                               ("hard_start", "accepted", TODAY - timedelta(days=1))])
        self.assertIsNone(pe.choose(h))

    def test_overview(self):
        days = [day(i, rating=4, focus_seconds=1800, planned_seconds=1500) for i in range(3)]
        h = history(days=days, tasks=[task(1, started=True), task(2)], feedback=[("x", "dismissed", TODAY)])
        result = pe.overview(h)
        self.assertEqual(len(result["series"]), 14)
        self.assertEqual(result["series"][-1]["height"], 100)
        self.assertEqual(result["series"][0]["height"], 0)
        self.assertEqual(result["start_rate"], {"started": 1, "total": 2})
        self.assertEqual((result["planned_minutes"], result["actual_minutes"]), (75, 90))
        self.assertEqual(result["feedback"]["dismissed"], 1)


class LearningRouteTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()

    def make_short_session_history(self):
        # 4 סשנים קצרים שהושלמו ו-3 ארוכים שנעצרו, בימים קודמים
        r = self.repo()
        for i in range(7):
            self.freeze(datetime(2026, 10, 20 + i, 9, 0, tzinfo=clock.LOCAL_TZ))
            minutes = 15 if i < 4 else 30
            session_id = r.create_session(self.user, "focus", minutes * 60)
            status = "completed" if i < 4 else "stopped"
            r.finish_session(self.user, session_id, status, clock.now_iso(), minutes * 30)
        self.freeze(datetime(2026, 10, 29, 10, 0, tzinfo=clock.LOCAL_TZ))

    def test_learning_is_off_until_consent(self):
        self.make_short_session_history()
        self.assertEqual(self.repo().get_settings(self.user)["learning_enabled"], 0)
        html = self.html(self.client_.get("/zehava/insights"))
        self.assertIn("/zehava/learning/consent", html)
        self.assertEqual(self.post(self.client_, "/zehava/insights/short_sessions/accept").status_code, 404)
        self.assertEqual(self.client_.get("/zehava/insights/data").status_code, 302)

    def test_consent_and_accept_changes_focus_length(self):
        self.make_short_session_history()
        self.post(self.client_, "/zehava/learning/consent", {"enable": "1"})
        settings = self.repo().get_settings(self.user)
        self.assertEqual(settings["learning_enabled"], 1)
        self.assertIsNotNone(settings["learning_consent_at"])
        history_ = build_history(self.repo(), self.user, settings)
        self.assertEqual(pe.choose(history_).rule_id, "short_sessions")
        self.assertIn("/zehava/insights/short_sessions/accept", self.html(self.client_.get("/zehava/insights")))
        self.assertIn("short_sessions", self.html(self.client_.get("/zehava/insights/data")))
        response = self.post(self.client_, "/zehava/insights/short_sessions/accept")
        self.assertTrue(response.headers["Location"].endswith("/zehava/timer"))
        self.assertEqual(self.repo().get_settings(self.user)["focus_minutes"], 15)
        row = self.repo().conn.execute("SELECT status, evidence FROM insights").fetchone()
        self.assertEqual(row[0], "accepted")
        self.assertIn("short_completed_pct", row[1])

    def test_dismiss_hides_the_suggestion(self):
        self.make_short_session_history()
        self.post(self.client_, "/zehava/learning/consent", {"enable": "1"})
        self.post(self.client_, "/zehava/insights/short_sessions/dismiss")
        self.assertNotIn("/zehava/insights/short_sessions/accept", self.html(self.client_.get("/zehava/insights")))
        self.assertEqual(self.repo().get_settings(self.user)["focus_minutes"], 25)

    def test_unknown_or_inactive_insight_is_ignored(self):
        self.post(self.client_, "/zehava/learning/consent", {"enable": "1"})
        self.post(self.client_, "/zehava/insights/made_up/accept")
        self.assertEqual(self.post(self.client_, "/zehava/insights/x/explode").status_code, 404)
        self.assertEqual(self.repo().insight_feedback(self.user), [])

    def test_turning_off_and_deleting_learning_data(self):
        self.post(self.client_, "/zehava/learning/consent", {"enable": "1"})
        self.repo().save_pulse(self.user, "2026-10-28", 4, "")
        self.repo().add_sound_feedback(self.user, "calm", True)
        self.post(self.client_, "/zehava/learning/consent", {"enable": "0"})
        self.assertEqual(self.repo().get_settings(self.user)["learning_enabled"], 0)
        self.post(self.client_, "/zehava/settings/delete-learning")
        self.assertEqual(self.repo().pulses_since(self.user, "2000-01-01"), [])
        self.assertEqual(self.repo().sound_feedback_counts(self.user), {})

    def test_demo_seed_produces_a_working_history(self):
        from timeflow.demo import seed_demo
        email, _ = seed_demo(self.app)
        repo = self.repo()
        user = repo.get_user_by_email(email)
        history_ = build_history(repo, user["id"], repo.get_settings(user["id"]))
        self.assertGreaterEqual(sum(1 for d in history_.days if d.rating), 10)
        self.assertTrue(len(history_.sessions) > 10)
        pe.evaluate(history_)    # לא נופל על נתונים אמיתיים בגודל מלא
