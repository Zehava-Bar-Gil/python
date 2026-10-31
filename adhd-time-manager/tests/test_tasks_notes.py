"""משימות, צעדים ופתקיות: יצירה, עריכה, מחיקה, אימות קלט, המרות ושמירה במסד."""
from .helpers import TimeFlowTestCase, make_app


class TaskTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()

    def add(self, **fields):
        return self.post(self.client_, "/zehava/add", {"title": "לסיים את המצגת", **fields})

    def test_add_task_with_all_fields(self):
        self.add(tag="work", priority="important", due_date="2026-10-30", due_time="09:30", details="שקף 3")
        task = self.repo().list_tasks(self.user)[0]
        self.assertEqual((task["title"], task["tag"], task["priority"]), ("לסיים את המצגת", "work", "important"))
        self.assertEqual((task["due_date"], task["due_time"], task["details"]), ("2026-10-30", "09:30", "שקף 3"))
        self.assertIn("לסיים את המצגת", self.html(self.client_.get("/zehava/tasks")))

    def test_invalid_values_are_cleaned(self):
        self.add(tag="hacker", priority="urgent!!", due_date="2026-13-45", due_time="25:99")
        task = self.repo().list_tasks(self.user)[0]
        self.assertEqual((task["tag"], task["priority"], task["due_date"], task["due_time"]), ("", "normal", None, None))

    def test_empty_title_is_not_saved(self):
        response = self.add(title="   ")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.repo().list_tasks(self.user), [])

    def test_long_title_is_cut(self):
        self.add(title="א" * 500)
        self.assertEqual(len(self.repo().list_tasks(self.user)[0]["title"]), 200)

    def test_edit_task(self):
        self.add()
        task_id = self.repo().list_tasks(self.user)[0]["id"]
        self.assertEqual(self.client_.get(f"/zehava/tasks/{task_id}/edit").status_code, 200)
        self.post(self.client_, f"/zehava/tasks/{task_id}/edit", {"title": "שם חדש", "priority": "later"})
        task = self.repo().get_task(self.user, task_id)
        self.assertEqual((task["title"], task["priority"]), ("שם חדש", "later"))

    def test_toggle_awards_and_unawards_points(self):
        self.add()
        task_id = self.repo().list_tasks(self.user)[0]["id"]
        self.post(self.client_, f"/zehava/toggle/{task_id}")
        self.assertEqual(self.repo().get_task(self.user, task_id)["status"], "done")
        self.assertEqual(self.repo().journey_points(self.user), 3)
        # לחיצה כפולה לא סופרת פעמיים
        self.post(self.client_, f"/zehava/toggle/{task_id}")
        self.post(self.client_, f"/zehava/toggle/{task_id}")
        self.assertEqual(self.repo().journey_points(self.user), 3)
        self.post(self.client_, f"/zehava/toggle/{task_id}")
        self.assertEqual(self.repo().get_task(self.user, task_id)["status"], "open")
        self.assertEqual(self.repo().journey_points(self.user), 0)

    def test_delete_keeps_points_already_earned(self):
        self.add()
        task_id = self.repo().list_tasks(self.user)[0]["id"]
        self.post(self.client_, f"/zehava/toggle/{task_id}")
        self.post(self.client_, f"/zehava/delete/{task_id}")
        self.assertIsNone(self.repo().get_task(self.user, task_id))
        self.assertEqual(self.repo().journey_points(self.user), 3)

    def test_steps(self):
        self.add()
        task_id = self.repo().list_tasks(self.user)[0]["id"]
        self.post(self.client_, f"/zehava/steps/add/{task_id}", {"text": "לפתוח את הקובץ"})
        self.post(self.client_, f"/zehava/steps/add/{task_id}", {"text": "  "})
        steps = self.repo().steps_for_tasks(self.user, [task_id])[task_id]
        self.assertEqual([s["title"] for s in steps], ["לפתוח את הקובץ"])
        step_id = steps[0]["id"]
        self.post(self.client_, f"/zehava/steps/toggle/{task_id}/{step_id}")
        self.assertIsNotNone(self.repo().get_task(self.user, task_id)["started_at"])
        self.assertEqual(self.repo().journey_points(self.user), 1)
        self.post(self.client_, f"/zehava/steps/toggle/{task_id}/{step_id}")
        self.assertEqual(self.repo().journey_points(self.user), 0)
        self.post(self.client_, f"/zehava/steps/delete/{task_id}/{step_id}")
        self.assertEqual(self.repo().steps_for_tasks(self.user, [task_id])[task_id], [])

    def test_deleting_task_deletes_its_steps(self):
        self.add()
        task_id = self.repo().list_tasks(self.user)[0]["id"]
        self.repo().add_step(self.user, task_id, "צעד")
        self.post(self.client_, f"/zehava/delete/{task_id}")
        count = self.repo().conn.execute("SELECT COUNT(*) FROM task_steps").fetchone()[0]
        self.assertEqual(count, 0)

    def test_filter_and_progressive_list(self):
        for i in range(9):
            self.add(title=f"משימה {i}", tag="study" if i == 0 else "home")
        html = self.html(self.client_.get("/zehava/tasks?tag=study"))
        self.assertIn("משימה 0", html)
        self.assertNotIn("משימה 1<", html)
        full = self.html(self.client_.get("/zehava/tasks?all=1"))
        self.assertIn("משימה 8", full)

    def test_split_hint_after_three_postpones(self):
        task_id = self.repo().create_task(self.user, "משימה תקועה", due_date="2026-10-29", due_time="10:30")
        for _ in range(3):
            self.repo().snooze_task(self.user, task_id, "2026-10-29", "11:00")
        html = self.html(self.client_.get("/zehava/tasks"))
        self.assertIn(f'/zehava/snooze/help/{task_id}', html)

    def test_postpone_next_timed_task(self):
        task_id = self.repo().create_task(self.user, "שיחה", due_date="2026-10-29", due_time="10:20")
        self.post(self.client_, "/zehava/snooze/15")
        task = self.repo().get_task(self.user, task_id)
        self.assertEqual((task["due_time"], task["snooze_count"]), ("10:35", 1))
        self.assertEqual(self.post(self.client_, "/zehava/snooze/7").status_code, 404)

    def test_data_survives_new_app_instance(self):
        self.add(title="נשמר במסד")
        second = make_app(self.folder)
        with second.test_client() as client:
            self.post(client, "/zehava/login", {"email": "zehava@example.com", "password": "calm-steps-2026"})
            self.assertIn("נשמר במסד", self.html(client.get("/zehava/tasks")))


class NoteTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()

    def note(self):
        return self.repo().list_notes(self.user)[0]

    def test_add_edit_delete_note(self):
        self.post(self.client_, "/zehava/notes/add", {"text": "לקנות חלב", "color": "pink", "tag": "בית"})
        note = self.note()
        self.assertEqual((note["body"], note["color"], note["tag"]), ("לקנות חלב", "pink", "בית"))
        self.post(self.client_, f"/zehava/notes/{note['id']}/edit", {"text": "Buy milk", "color": "nope"})
        note = self.note()
        self.assertEqual((note["body"], note["color"]), ("Buy milk", "yellow"))
        self.post(self.client_, f"/zehava/notes/delete/{note['id']}")
        self.assertEqual(self.repo().list_notes(self.user), [])

    def test_empty_note_is_not_saved(self):
        self.post(self.client_, "/zehava/notes/add", {"text": " "})
        self.assertEqual(self.repo().list_notes(self.user), [])

    def test_hebrew_and_english_note_render(self):
        self.post(self.client_, "/zehava/notes/add", {"text": "שלום hello"})
        html = self.html(self.client_.get("/zehava/notes"))
        self.assertIn("שלום hello", html)
        self.assertIn('dir="auto"', html)

    def test_note_to_task(self):
        self.post(self.client_, "/zehava/notes/add", {"text": "להתקשר לרופא"})
        self.post(self.client_, f"/zehava/notes/{self.note()['id']}/to-task")
        task = self.repo().list_tasks(self.user)[0]
        self.assertEqual((task["title"], task["source"]), ("להתקשר לרופא", "note"))
        self.assertEqual(self.repo().list_notes(self.user), [])

    def test_note_to_step(self):
        task_id = self.repo().create_task(self.user, "פרויקט")
        self.post(self.client_, "/zehava/notes/add", {"text": "לכתוב פתיח"})
        note_id = self.note()["id"]
        self.post(self.client_, f"/zehava/notes/{note_id}/to-step", {})
        self.assertIsNotNone(self.repo().get_note(self.user, note_id))      # בלי משימה לא קורה כלום
        self.post(self.client_, f"/zehava/notes/{note_id}/to-step", {"task_id": str(task_id)})
        self.assertEqual([s["title"] for s in self.repo().steps_for_tasks(self.user, [task_id])[task_id]], ["לכתוב פתיח"])
        self.assertIsNone(self.repo().get_note(self.user, note_id))

    def test_note_to_snooze(self):
        self.post(self.client_, "/zehava/notes/add", {"text": "מחשבה שמטרידה"})
        self.post(self.client_, f"/zehava/notes/{self.note()['id']}/to-snooze")
        self.assertEqual(self.repo().list_snooze_entries(self.user)[0]["body"], "מחשבה שמטרידה")
        self.assertEqual(self.repo().list_notes(self.user), [])
