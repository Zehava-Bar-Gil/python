"""משימות, צעדים ופתקיות: יצירה, עריכה, מחיקה, אימות קלט, המרות ושמירה במסד."""
from .helpers import TimeFlowTestCase, make_app


class TaskTests(TimeFlowTestCase):
    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()

    def add(self, **fields):
        return self.post(self.client_, "/zehava/add", {"title": "לסיים את המצגת", **fields})

    def test_add_task_with_all_fields(self):
        self.add(tag="work", priority="important", due_year="2026", due_month="10", due_day="30", due_time="09:30", details="שקף 3")
        task = self.repo().list_tasks(self.user)[0]
        self.assertEqual((task["title"], task["tag"], task["priority"]), ("לסיים את המצגת", "work", "important"))
        self.assertEqual((task["due_date"], task["due_time"], task["details"]), ("2026-10-30", "09:30", "שקף 3"))
        self.assertIn("לסיים את המצגת", self.html(self.client_.get("/zehava/tasks")))

    def test_invalid_values_are_cleaned(self):
        self.add(tag="hacker", priority="urgent!!", due_year="2026", due_month="13", due_day="45", due_time="25:99")
        task = self.repo().list_tasks(self.user)[0]
        self.assertEqual((task["tag"], task["priority"], task["due_date"], task["due_time"]), ("", "normal", None, None))

    def test_due_date_is_three_lists_in_the_site_language(self):
        html = self.html(self.client_.get("/zehava/tasks"))
        self.assertNotIn('type="date"', html)
        self.assertIn('name="due_day"', html)
        self.assertIn('>יוני</option>', html)
        self.add(due_year="2026", due_month="6", due_day="31")       # 31 ביוני לא קיים
        self.assertIsNone(self.repo().list_tasks(self.user)[0]["due_date"])
        self.assertIn("נשמרה בלי תאריך", self.html(self.client_.get("/zehava/tasks")))

    def test_edit_keeps_the_due_date_selected(self):
        task_id = self.repo().create_task(self.user, "ישנה", due_date="2019-03-04")
        html = self.html(self.client_.get(f"/zehava/tasks/{task_id}/edit"))
        self.assertIn('<option value="4" selected>4</option>', html)
        self.assertIn('<option value="3" selected>מרץ</option>', html)
        self.assertIn('<option value="2019" selected>2019</option>', html)

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

    def test_done_task_offers_undo_and_is_highlighted_once(self):
        self.add()
        task_id = self.repo().list_tasks(self.user)[0]["id"]
        self.post(self.client_, f"/zehava/toggle/{task_id}", {"back": "/zehava/tasks"})
        html = self.html(self.client_.get("/zehava/tasks"))
        self.assertIn("בוצע: לסיים את המצגת", html)
        self.assertIn(f'action="/zehava/toggle/{task_id}"', html.split('class="flashes"')[1])   # כפתור "ביטול" בתוך ההודעה
        self.post(self.client_, f"/zehava/toggle/{task_id}", {"back": "/zehava/tasks"})        # ביטול
        self.assertEqual(self.repo().get_task(self.user, task_id)["status"], "open")
        self.assertEqual(self.repo().journey_points(self.user), 0)
        html = self.html(self.client_.get("/zehava/tasks"))
        self.assertRegex(html, rf'class="task [^"]*\bjust\b[^"]*" id="task-{task_id}"')      # המשימה שחזרה מודגשת
        self.assertNotIn(" just", self.html(self.client_.get("/zehava/tasks")))               # ורק פעם אחת

    def test_step_list_stays_open_after_marking_a_step(self):
        self.add()
        task_id = self.repo().list_tasks(self.user)[0]["id"]
        step_id = self.repo().add_step(self.user, task_id, "לפתוח את הקובץ")
        self.post(self.client_, f"/zehava/steps/toggle/{task_id}/{step_id}", {"back": "/zehava/tasks"})
        html = self.html(self.client_.get("/zehava/tasks"))
        self.assertIn('<details class="steps" open>', html)
        self.assertIn('class="step done just"', html)

    def test_estimate_is_saved_validated_and_summed(self):
        self.add(estimate="25")
        self.add(title="משימה שנייה", estimate="999")                 # לא מהרשימה: לא נשמר
        self.add(title="משימה שלישית", estimate="60")
        tasks = self.repo().list_tasks(self.user)
        self.assertEqual([t["estimate_minutes"] for t in tasks], [25, None, 60])
        html = self.html(self.client_.get("/zehava/tasks"))
        self.assertIn("כ-25 דק&#39;", html)
        self.assertIn("כשעה", html)
        self.assertIn("כל המשימות הפתוחות יחד: 1 שע&#39; 25 דק&#39; בערך", html)
        self.post(self.client_, f"/zehava/tasks/{tasks[0]['id']}/edit", {"title": "לסיים את המצגת", "estimate": ""})
        self.assertIsNone(self.repo().get_task(self.user, tasks[0]["id"])["estimate_minutes"])

    def test_focus_offers_the_estimate(self):
        self.add(estimate="15")
        task_id = self.repo().list_tasks(self.user)[0]["id"]
        html = self.html(self.client_.get(f"/zehava/focus?task={task_id}"))
        self.assertIn("לפי ההערכה שלך: כ-15 דק&#39;", html)
        self.assertIn('action="/zehava/focus/start/15"', html)

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

    def test_new_note_is_highlighted_once(self):
        self.post(self.client_, "/zehava/notes/add", {"text": "רעיון חדש", "color": "pink"})
        note_id = self.repo().list_notes(self.user)[0]["id"]
        self.assertRegex(self.html(self.client_.get("/zehava/notes")), rf'class="note note-pink[^"]*\bjust\b[^"]*" id="note-{note_id}"')
        self.assertNotRegex(self.html(self.client_.get("/zehava/notes")), r'class="note [^"]*\bjust\b')

    def test_pinned_note_comes_first(self):
        for text in ("ראשון", "שני", "שלישי"):
            self.post(self.client_, "/zehava/notes/add", {"text": text})
        first = [n for n in self.repo().list_notes(self.user) if n["body"] == "ראשון"][0]
        self.post(self.client_, f"/zehava/notes/{first['id']}/pin")
        self.assertEqual([n["body"] for n in self.repo().list_notes(self.user)], ["ראשון", "שלישי", "שני"])
        html = self.html(self.client_.get("/zehava/notes"))
        self.assertIn("הפתק הוצמד למעלה.", html)
        self.assertRegex(html, rf'class="note note-yellow pinned[^"]*" id="note-{first["id"]}"')
        self.post(self.client_, f"/zehava/notes/{first['id']}/pin")                 # לחיצה נוספת: ביטול
        self.assertEqual(self.repo().list_notes(self.user)[0]["body"], "שלישי")

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
