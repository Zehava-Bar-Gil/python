"""הפרדה בין משתמשות: משתמשת ב' לא רואה ולא משנה שום דבר של משתמשת א'."""
import json

from timeflow import clock

from .helpers import TimeFlowTestCase


class IsolationTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.a_client, self.a = self.register(email="a@example.com", name="Avital")
        self.b_client, self.b = self.register(email="b@example.com", name="Bella")
        r = self.repo()
        self.task = r.create_task(self.a, "סוד של א")
        self.step = r.add_step(self.a, self.task, "צעד סודי")
        self.note = r.create_note(self.a, "פתק סודי")
        self.entry = r.create_snooze_entry(self.a, "מחשבה סודית")
        start = clock.to_iso(clock.now())
        r.upsert_calendar_event(self.a, "g-1", "פגישה סודית", start, None, False)
        self.event = r.calendar_events_between(self.a, "0000", "9999")[0]["id"]

    def assert_a_untouched(self):
        r = self.repo()
        task = r.get_task(self.a, self.task)
        self.assertEqual(task["status"], "open")
        self.assertEqual(task["title"], "סוד של א")
        self.assertIsNotNone(r.get_step(self.a, self.task, self.step))
        self.assertIsNone(r.get_step(self.a, self.task, self.step)["done_at"])
        self.assertEqual(r.get_note(self.a, self.note)["body"], "פתק סודי")
        self.assertEqual(r.get_snooze_entry(self.a, self.entry)["bucket"], "unsorted")
        self.assertEqual(r.list_tasks(self.b), [])
        self.assertEqual(r.journey_points(self.b), 0)

    def test_pages_do_not_show_other_users_data(self):
        for path in ("/zehava", "/zehava/tasks", "/zehava/notes", "/zehava/snooze", "/zehava/calendar",
                     f"/zehava/snooze?entry={self.entry}", f"/zehava/focus?task={self.task}",
                     f"/zehava/timer?task={self.task}", "/zehava/insights"):
            html = self.html(self.b_client.get(path))
            for secret in ("סוד של א", "צעד סודי", "פתק סודי", "מחשבה סודית", "פגישה סודית"):
                self.assertNotIn(secret, html, path)

    def test_task_routes_return_404_for_other_user(self):
        b = self.b_client
        self.assertEqual(b.get(f"/zehava/tasks/{self.task}/edit").status_code, 404)
        self.assertEqual(self.post(b, f"/zehava/tasks/{self.task}/edit", {"title": "x"}).status_code, 404)
        self.assertEqual(self.post(b, f"/zehava/toggle/{self.task}").status_code, 404)
        self.assertEqual(self.post(b, f"/zehava/steps/toggle/{self.task}/{self.step}").status_code, 404)
        self.post(b, f"/zehava/delete/{self.task}")
        self.post(b, f"/zehava/steps/delete/{self.task}/{self.step}")
        self.post(b, f"/zehava/steps/add/{self.task}", {"text": "צעד זר"})
        self.assertEqual(len(self.repo().steps_for_tasks(self.a, [self.task])[self.task]), 1)
        self.assert_a_untouched()

    def test_note_routes_return_404_for_other_user(self):
        b = self.b_client
        self.assertEqual(b.get(f"/zehava/notes/{self.note}/edit").status_code, 404)
        for path in (f"/zehava/notes/{self.note}/to-task", f"/zehava/notes/{self.note}/to-snooze",
                     f"/zehava/notes/{self.note}/to-step"):
            self.assertEqual(self.post(b, path, {"task_id": str(self.task)}).status_code, 404, path)
        self.post(b, f"/zehava/notes/delete/{self.note}")
        self.assert_a_untouched()

    def test_note_cannot_become_step_of_other_users_task(self):
        own_note = self.repo().create_note(self.b, "של ב")
        self.post(self.b_client, f"/zehava/notes/{own_note}/to-step", {"task_id": str(self.task)})
        self.assertEqual(len(self.repo().steps_for_tasks(self.a, [self.task])[self.task]), 1)
        self.assertIsNotNone(self.repo().get_note(self.b, own_note))

    def test_snooze_routes_return_404_for_other_user(self):
        b = self.b_client
        for path in (f"/zehava/snooze/{self.entry}/suggest", f"/zehava/snooze/{self.entry}/option/0/task",
                     f"/zehava/snooze/{self.entry}/sort/later", f"/zehava/snooze/{self.entry}/to-task",
                     f"/zehava/snooze/help/{self.task}"):
            self.assertEqual(self.post(b, path).status_code, 404, path)
        self.post(b, f"/zehava/snooze/{self.entry}/delete")
        self.assert_a_untouched()

    def test_timer_cannot_attach_other_users_task(self):
        self.post(self.b_client, "/zehava/timer/start", {"kind": "focus", "minutes": "10", "task_id": str(self.task)})
        session = self.repo().active_session(self.b)
        self.assertIsNotNone(session)
        self.assertIsNone(session["task_id"])
        self.post(self.b_client, "/zehava/focus/done", {"task_id": str(self.task)})
        self.assert_a_untouched()
        self.assertIsNone(self.repo().active_session(self.a))

    def test_calendar_event_of_other_user(self):
        self.assertEqual(self.post(self.b_client, f"/zehava/calendar/event/{self.event}/to-task").status_code, 404)
        self.assertIsNone(self.repo().get_calendar_event(self.a, self.event)["task_id"])

    def test_export_contains_only_own_data(self):
        self.repo().create_task(self.b, "של ב")
        response = self.b_client.get("/zehava/settings/export")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(data["user"]["email"], "b@example.com")
        self.assertNotIn("password_hash", data["user"])
        self.assertEqual([t["title"] for t in data["tasks"]], ["של ב"])
        for table in ("task_steps", "notes", "snooze_entries", "calendar_events"):
            self.assertEqual(data[table], [], table)
        text = response.get_data(as_text=True)
        self.assertNotIn("סוד", text)

    def test_deleting_one_account_keeps_the_other(self):
        self.post(self.b_client, "/zehava/settings/delete-account", {"password": "calm-steps-2026", "confirm": "1"})
        self.assertIsNone(self.repo().get_user(self.b))
        self.assert_a_untouched_after_delete()

    def assert_a_untouched_after_delete(self):
        r = self.repo()
        self.assertIsNotNone(r.get_user(self.a))
        self.assertIsNotNone(r.get_task(self.a, self.task))
        self.assertEqual(self.a_client.get("/zehava/tasks").status_code, 200)
