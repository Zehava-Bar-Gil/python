"""טיימר עגבנייה, מצב מיקוד ומסע הכדור הפורח."""
from datetime import timedelta

from timeflow import clock, focus_timer, journey

from .helpers import TimeFlowTestCase


class TimerTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()

    def later(self, **delta):
        self.freeze(clock.now() + timedelta(**delta))

    def session(self):
        return self.repo().conn.execute("SELECT * FROM focus_sessions ORDER BY id DESC").fetchone()

    def test_only_one_active_session(self):
        self.post(self.client_, "/zehava/timer/start", {"kind": "focus", "minutes": "25"})
        self.post(self.client_, "/zehava/timer/start", {"kind": "focus", "minutes": "10"})
        count = self.repo().conn.execute("SELECT COUNT(*) FROM focus_sessions").fetchone()[0]
        self.assertEqual(count, 1)
        self.assertEqual(self.session()["planned_seconds"], 25 * 60)

    def test_lazy_completion_is_counted_once(self):
        self.post(self.client_, "/zehava/timer/start", {"kind": "focus", "minutes": "25"})
        self.later(minutes=26)
        self.client_.get("/zehava/timer")
        self.client_.get("/zehava")
        session = self.session()
        self.assertEqual(session["status"], "completed")
        self.assertEqual(session["actual_seconds"], 25 * 60)
        self.assertEqual(self.repo().journey_points(self.user), 1)
        # שתי לשוניות שסוגרות יחד: רק אחת מצליחה
        self.assertIsNone(focus_timer.complete_if_due(self.repo(), self.user, clock.now()))

    def test_pause_and_resume(self):
        self.post(self.client_, "/zehava/timer/start", {"kind": "focus", "minutes": "25"})
        self.later(minutes=5)
        self.post(self.client_, "/zehava/timer/pause")
        self.later(minutes=10)
        state = focus_timer.state(self.repo().active_session(self.user), clock.now())
        self.assertTrue(state["paused"])
        self.assertEqual(state["remaining"], 20 * 60)
        self.post(self.client_, "/zehava/timer/resume")
        self.assertEqual(self.session()["paused_seconds"], 600)
        self.later(minutes=19)
        self.client_.get("/zehava/timer")
        self.assertEqual(self.session()["status"], "running")
        self.later(minutes=2)
        self.client_.get("/zehava/timer")
        self.assertEqual(self.session()["status"], "completed")

    def test_paused_session_does_not_finish(self):
        self.post(self.client_, "/zehava/timer/start", {"kind": "focus", "minutes": "5"})
        self.post(self.client_, "/zehava/timer/pause")
        self.later(hours=2)
        self.client_.get("/zehava/timer")
        self.assertEqual(self.session()["status"], "paused")

    def test_reset_records_real_time_without_points(self):
        self.post(self.client_, "/zehava/timer/start", {"kind": "focus", "minutes": "25"})
        self.later(minutes=7)
        self.post(self.client_, "/zehava/timer/reset")
        session = self.session()
        self.assertEqual((session["status"], session["actual_seconds"]), ("stopped", 420))
        self.assertEqual(self.repo().journey_points(self.user), 0)

    def test_flexible_session(self):
        self.post(self.client_, "/zehava/timer/start", {"kind": "focus", "flexible": "1"})
        self.assertEqual(self.session()["planned_seconds"], 0)
        self.later(hours=3)
        self.client_.get("/zehava/timer")
        self.assertEqual(self.session()["status"], "running")    # גמיש לא נגמר לבד
        self.post(self.client_, "/zehava/timer/reset")
        self.assertEqual(self.session()["status"], "completed")
        self.assertEqual(self.repo().journey_points(self.user), 1)

    def test_very_short_flexible_session_is_not_counted(self):
        self.post(self.client_, "/zehava/timer/start", {"kind": "focus", "flexible": "1"})
        self.later(seconds=30)
        self.post(self.client_, "/zehava/timer/reset")
        self.assertEqual(self.session()["status"], "stopped")
        self.assertEqual(self.repo().journey_points(self.user), 0)

    def test_breaks_use_settings_length_and_give_no_points(self):
        self.post(self.client_, "/zehava/timer/start", {"kind": "short_break", "minutes": "50"})
        self.assertEqual(self.session()["planned_seconds"], 5 * 60)
        self.later(minutes=6)
        self.client_.get("/zehava/timer")
        self.assertEqual(self.session()["status"], "completed")
        self.assertEqual(self.repo().journey_points(self.user), 0)

    def test_minutes_are_validated(self):
        self.post(self.client_, "/zehava/timer/start", {"kind": "focus", "minutes": "9999"})
        self.assertEqual(self.session()["planned_seconds"], 180 * 60)
        self.post(self.client_, "/zehava/timer/reset")
        self.assertEqual(self.post(self.client_, "/zehava/timer/0").status_code, 404)
        self.assertEqual(self.post(self.client_, "/zehava/timer/break/nap").status_code, 404)

    def test_break_offer_after_focus(self):
        self.post(self.client_, "/zehava/timer/start", {"kind": "focus", "minutes": "25"})
        self.later(minutes=26)
        html = self.html(self.client_.get("/zehava/timer"))
        self.assertIn("/zehava/timer/break/short_break", html)
        self.later(minutes=30)
        html = self.html(self.client_.get("/zehava/timer"))
        self.assertNotIn('class="break-offer', html)

    def test_long_break_after_four_sessions(self):
        settings = self.repo().get_settings(self.user)
        for _ in range(4):
            focus_timer.start(self.repo(), self.user, "focus", 25)
            self.later(minutes=26)
            focus_timer.complete_if_due(self.repo(), self.user, clock.now())
        self.assertEqual(focus_timer.break_suggestion(self.repo(), self.user, settings, clock.today()),
                         ("long_break", 15))

    def test_focus_mode_done_marks_task(self):
        task_id = self.repo().create_task(self.user, "לכתוב סיכום")
        self.post(self.client_, f"/zehava/focus/start/15", {"task_id": str(task_id)})
        self.assertIsNotNone(self.repo().get_task(self.user, task_id)["started_at"])
        self.assertIn("לכתוב סיכום", self.html(self.client_.get("/zehava/focus")))
        self.later(minutes=8)
        self.post(self.client_, "/zehava/focus/done", {"task_id": str(task_id)})
        self.assertEqual(self.repo().get_task(self.user, task_id)["status"], "done")
        self.assertEqual(self.session()["actual_seconds"], 480)
        self.assertEqual(self.repo().journey_points(self.user), 3)

    def test_leaving_focus_mode_keeps_time(self):
        self.post(self.client_, "/zehava/focus/start/25")
        self.later(minutes=12)
        response = self.post(self.client_, "/zehava/focus/leave")
        self.assertTrue(response.headers["Location"].endswith("/zehava"))
        self.assertEqual(self.session()["actual_seconds"], 720)

    def test_chime_plays_only_when_enabled(self):
        self.post(self.client_, "/zehava/timer/start", {"kind": "focus", "minutes": "5"})
        self.later(minutes=6)
        self.assertNotIn('<audio class="chime" autoplay', self.html(self.client_.get("/zehava/timer")))
        self.repo().update_settings(self.user, timer_chime=1)
        self.post(self.client_, "/zehava/timer/start", {"kind": "focus", "minutes": "5"})
        self.later(minutes=6)
        self.assertIn('<audio class="chime" autoplay', self.html(self.client_.get("/zehava/timer")))

    def test_sound_votes(self):
        self.assertEqual(self.post(self.client_, "/zehava/sounds/vote/calm/yes").status_code, 204)
        self.post(self.client_, "/zehava/sounds/vote/calm/no")
        self.post(self.client_, "/zehava/sounds/vote/evil/yes")
        self.assertEqual(self.repo().sound_feedback_counts(self.user), {"calm": {"yes": 1, "no": 1, "total": 2}})


class JourneyTests(TimeFlowTestCase):
    def test_position_math(self):
        self.assertEqual(journey.position(0)["lit"], 0)
        self.assertEqual(journey.position(0)["to_next"], 4)
        self.assertEqual(journey.position(5)["lit"], 1)
        self.assertEqual(journey.position(5)["to_next"], 3)
        self.assertEqual(journey.position(24)["climb"], 2)
        self.assertEqual(journey.position(24)["lit"], 0)

    def test_balloon_moves_up_with_points(self):
        tops = [journey.position(p)["top"] for p in range(0, 25)]
        self.assertEqual(tops[0], journey.BALLOON_TOPS[0])
        self.assertTrue(all(a >= b for a, b in zip(tops[:24], tops[1:24])))
        self.assertEqual(journey.balloon_top(99), journey.BALLOON_TOPS[-1])
        self.assertEqual(journey.balloon_top(-3), journey.BALLOON_TOPS[0])

    def test_view_remembers_what_was_shown_and_celebrates_summit(self):
        client, user = self.register()
        r = self.repo()
        for task_id in range(1, 8):            # 7 משימות = 21 נקודות
            journey.record(r, user, "task", task_id)
        first = journey.view(r, user)
        self.assertFalse(first["summit_reached"])
        self.assertEqual(r.get_shown_points(user), 21)
        journey.record(r, user, "task", 8)     # 24 נקודות = פסגה
        second = journey.view(r, user)
        self.assertTrue(second["summit_reached"])
        self.assertEqual(second["lit"], journey.STATIONS)
        self.assertFalse(journey.view(r, user)["summit_reached"])
        self.assertEqual(client.get("/zehava").status_code, 200)

    def test_adding_tasks_never_lowers_progress(self):
        client, user = self.register()
        journey.record(self.repo(), user, "step", 1)
        for i in range(10):
            self.post(client, "/zehava/add", {"title": f"t{i}"})
        self.assertEqual(self.repo().journey_points(user), 1)

    def test_same_item_counts_once(self):
        _, user = self.register()
        self.assertTrue(journey.record(self.repo(), user, "task", 5))
        self.assertFalse(journey.record(self.repo(), user, "task", 5))
        self.assertEqual(self.repo().journey_points(user), 3)

    def test_stations_reached_per_day(self):
        _, user = self.register()
        r = self.repo()
        for task_id in (1, 2):
            journey.record(r, user, "task", task_id)     # 6 נקודות היום
        self.assertEqual(journey.stations_reached(r, user, clock.today()), 1)
        self.freeze(clock.now() + timedelta(days=1))
        journey.record(r, user, "task", 3)               # 9 נקודות: תחנה 2
        self.assertEqual(journey.stations_reached(r, user, clock.today()), 1)
