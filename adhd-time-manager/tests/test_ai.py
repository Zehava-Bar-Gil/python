"""ה-AI ב-Snooze: ספק מדומה, נפילה למצב בסיסי, הסתרת פרטים, הגבלה ופעולות על הצעות.

אף בדיקה לא פונה ל-API אמיתי: הספק או הלקוח מוחלפים באובייקט מדומה.
"""
import json
import unittest
from types import SimpleNamespace

from timeflow import snooze_assistant
from timeflow.ai_providers import (ClaudeProvider, OfflineProvider, Option, ProviderError, Suggestion,
                                   clean_options)

from .helpers import TimeFlowTestCase


class FakeProvider:
    name = "claude"

    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def suggest(self, purpose, text, lang, context):
        self.calls.append((purpose, text, lang, context))
        if self.error:
            raise ProviderError(self.error)
        return Suggestion("נשמע שיש הרבה.", "מה הכי דחוף?",
                          [Option("לפתוח את המייל", 5), Option("לכתוב רשימה", 10)], source="claude")


class SnoozeAiTests(TimeFlowTestCase):
    app_overrides = {"AI_DAILY_LIMIT": 3}

    def setUp(self):
        super().setUp()
        self.client_, self.user = self.register()
        self.fake = FakeProvider()
        self.app.extensions["timeflow_ai"] = self.fake

    def write(self, text="יש לי מבחן, צריך לשלם חשבון ולהתקשר לסבתא"):
        self.post(self.client_, "/zehava/snooze/write", {"text": text})
        return self.repo().list_snooze_entries(self.user)[0]["id"]

    def suggestion(self, entry_id):
        return Suggestion.from_json(self.repo().get_snooze_entry(self.user, entry_id)["ai_reply"])

    def ai_log(self):
        return [tuple(row) for row in self.repo().conn.execute("SELECT purpose, provider, status FROM ai_requests")]

    def test_suggestion_from_provider_is_saved_and_shown(self):
        entry = self.write()
        self.post(self.client_, f"/zehava/snooze/{entry}/suggest")
        suggestion = self.suggestion(entry)
        self.assertEqual((suggestion.source, len(suggestion.options)), ("claude", 2))
        html = self.html(self.client_.get(f"/zehava/snooze?entry={entry}"))
        self.assertIn("לפתוח את המייל", html)
        self.assertEqual(self.ai_log(), [("unload", "claude", "ok")])

    def test_personal_details_are_removed_before_sending(self):
        entry = self.write("לכתוב ל-dana@example.com ולהתקשר ל-050-1234567")
        self.post(self.client_, f"/zehava/snooze/{entry}/suggest")
        sent = self.fake.calls[0][1]
        self.assertNotIn("dana@example.com", sent)
        self.assertNotIn("050-1234567", sent)
        self.assertIn("[email]", sent)
        self.assertIn("[phone]", sent)

    def test_disabled_by_user_uses_basic_mode_without_calling(self):
        self.repo().update_settings(self.user, ai_enabled=0)
        entry = self.write()
        self.post(self.client_, f"/zehava/snooze/{entry}/suggest")
        self.assertEqual(self.fake.calls, [])
        suggestion = self.suggestion(entry)
        self.assertEqual((suggestion.source, suggestion.notice), ("offline", "ai_disabled"))
        self.assertTrue(suggestion.options)

    def test_provider_error_falls_back_honestly(self):
        self.app.extensions["timeflow_ai"] = FakeProvider(error="error")
        entry = self.write()
        self.post(self.client_, f"/zehava/snooze/{entry}/suggest")
        self.assertEqual((self.suggestion(entry).source, self.suggestion(entry).notice), ("offline", "ai_error"))
        self.assertEqual(self.ai_log(), [("unload", "claude", "error")])

    def test_refusal_falls_back(self):
        self.app.extensions["timeflow_ai"] = FakeProvider(error="refused")
        entry = self.write()
        self.post(self.client_, f"/zehava/snooze/{entry}/suggest")
        self.assertEqual(self.suggestion(entry).notice, "ai_error")
        self.assertEqual(self.ai_log(), [("unload", "claude", "refused")])

    def test_daily_limit(self):
        entry = self.write()
        for _ in range(5):
            self.post(self.client_, f"/zehava/snooze/{entry}/suggest")
        self.assertEqual(len(self.fake.calls), 3)
        self.assertEqual(self.suggestion(entry).notice, "ai_limited")

    def test_without_key_the_page_says_basic_mode(self):
        del self.app.extensions["timeflow_ai"]          # AI_ENABLED=False בבדיקות: אין מפתח
        entry = self.write()
        self.post(self.client_, f"/zehava/snooze/{entry}/suggest")
        self.assertEqual(self.suggestion(entry).notice, "ai_offline")
        self.assertEqual(self.ai_log(), [("unload", "offline", "offline")])

    def test_option_index_is_read_from_server(self):
        entry = self.write()
        self.post(self.client_, f"/zehava/snooze/{entry}/suggest")
        self.assertEqual(self.post(self.client_, f"/zehava/snooze/{entry}/option/7/task").status_code, 404)
        self.assertEqual(self.post(self.client_, f"/zehava/snooze/{entry}/option/0/hack").status_code, 404)
        self.post(self.client_, f"/zehava/snooze/{entry}/option/1/task", {"title": "טקסט מזויף"})
        task = self.repo().list_tasks(self.user)[0]
        self.assertEqual((task["title"], task["source"]), ("לכתוב רשימה", "ai"))
        self.assertEqual(self.repo().get_snooze_entry(self.user, entry)["bucket"], "action")

    def test_option_starts_timer_with_its_minutes(self):
        entry = self.write()
        self.post(self.client_, f"/zehava/snooze/{entry}/suggest")
        response = self.post(self.client_, f"/zehava/snooze/{entry}/option/0/timer")
        self.assertIn("/zehava/focus", response.headers["Location"])
        session = self.repo().active_session(self.user)
        self.assertEqual(session["planned_seconds"], 5 * 60)
        self.assertEqual(self.repo().get_task(self.user, session["task_id"])["title"], "לפתוח את המייל")

    def test_start_help_adds_steps_to_the_original_task(self):
        task_id = self.repo().create_task(self.user, "לכתוב עבודה")
        self.assertEqual(self.client_.get(f"/zehava/snooze/help/{task_id}").status_code, 302)
        self.post(self.client_, f"/zehava/snooze/help/{task_id}")
        purpose, text, _, context = self.fake.calls[0]
        self.assertEqual((purpose, text, context), ("start_help", "לכתוב עבודה", {"prefer_short": True}))
        entry = self.repo().list_snooze_entries(self.user)[0]
        self.assertEqual((entry["bucket"], entry["task_id"]), ("action", task_id))
        self.post(self.client_, f"/zehava/snooze/{entry['id']}/option/0/step")
        steps = self.repo().steps_for_tasks(self.user, [task_id])[task_id]
        self.assertEqual([s["title"] for s in steps], ["לפתוח את המייל"])

    def test_sort_convert_and_delete(self):
        entry = self.write("רעיון")
        self.post(self.client_, f"/zehava/snooze/{entry}/sort/let_go")
        self.assertEqual(self.repo().get_snooze_entry(self.user, entry)["bucket"], "let_go")
        self.assertEqual(self.post(self.client_, f"/zehava/snooze/{entry}/sort/trash").status_code, 404)
        self.post(self.client_, f"/zehava/snooze/{entry}/to-task")
        self.assertEqual(self.repo().list_tasks(self.user)[0]["source"], "snooze")
        self.post(self.client_, f"/zehava/snooze/{entry}/delete")
        self.assertEqual(self.repo().list_snooze_entries(self.user), [])

    def test_api_key_never_reaches_the_page(self):
        import os
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-secret-value"
        self.addCleanup(os.environ.pop, "ANTHROPIC_API_KEY", None)
        entry = self.write()
        self.post(self.client_, f"/zehava/snooze/{entry}/suggest")
        for path in ("/zehava/snooze", f"/zehava/snooze?entry={entry}", "/zehava/settings", "/zehava/settings/export"):
            self.assertNotIn("sk-ant-test-secret-value", self.html(self.client_.get(path)), path)


def fake_response(stop_reason="end_turn", payload=None, raw=None):
    text = raw if raw is not None else json.dumps(payload)
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.kwargs = None
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class ClaudeProviderTests(unittest.TestCase):
    def provider(self, result):
        client = FakeClient(result)
        return ClaudeProvider("claude-opus-5-5", client=client), client

    def test_valid_answer_is_cleaned(self):
        payload = {"reflection": "  נשמע   עמוס. ", "question": "מה קודם?",
                   "options": [{"title": "א", "minutes": 100}, {"title": "ב", "minutes": 0},
                               {"title": "ג", "minutes": "x"}, {"title": "ד", "minutes": 5}]}
        provider, client = self.provider(fake_response(payload=payload))
        result = provider.suggest("unload", "טקסט", "he", {})
        self.assertEqual(result.reflection, "נשמע עמוס.")
        self.assertEqual([(o.title, o.minutes) for o in result.options], [("א", 25), ("ב", 2), ("ג", 5)])
        self.assertEqual(result.source, "claude")
        self.assertEqual(client.kwargs["model"], "claude-opus-5-5")
        self.assertIn("Hebrew", client.kwargs["system"])
        self.assertIn("<thought>טקסט</thought>", client.kwargs["messages"][0]["content"])

    def test_refusal_and_bad_output(self):
        for response, status in ((fake_response("refusal", raw=""), "refused"),
                                 (fake_response("max_tokens", raw="{"), "error"),
                                 (fake_response(raw="not json"), "error"),
                                 (fake_response(payload={"reflection": "", "question": "", "options": []}), "error")):
            provider, _ = self.provider(response)
            with self.assertRaises(ProviderError) as caught:
                provider.suggest("unload", "x", "en", {})
            self.assertEqual(caught.exception.status, status)

    def test_api_errors_become_provider_errors(self):
        try:
            import anthropic
            import httpx2
        except ImportError:
            self.skipTest("anthropic is not installed")
        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        errors = [anthropic.RateLimitError("slow down", response=httpx2.Response(429, request=request), body=None),
                  anthropic.InternalServerError("oops", response=httpx2.Response(500, request=request), body=None),
                  anthropic.APIConnectionError(request=request)]
        for error in errors:
            provider, _ = self.provider(error)
            with self.assertRaises(ProviderError):
                provider.suggest("start_help", "x", "he", {"prefer_short": True})

    def test_offline_provider(self):
        result = OfflineProvider().suggest("unload", "לשלם חשבון, לכבס", "he", {})
        self.assertEqual(len(result.options), 3)
        self.assertEqual(result.source, "offline")
        result = OfflineProvider().suggest("start_help", "Essay", "en", {})
        self.assertIn("Essay", result.reflection)
        self.assertEqual(len(clean_options([{"title": str(i)} for i in range(9)])), 3)

    def test_scrub(self):
        self.assertEqual(snooze_assistant.scrub("a@b.co +972 50 123 4567"), "[email] [phone]")
        self.assertEqual(len(snooze_assistant.scrub("x" * 5000)), 1000)
