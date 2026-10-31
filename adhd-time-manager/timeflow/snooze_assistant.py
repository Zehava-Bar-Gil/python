"""ניהול השיחה ב-Snooze: מה נשלח, למי, באיזו תדירות, ומה מוצג.

הפרדה בין האחריות:
- כאן: הסכמה, הגבלת שימוש, הסתרת פרטים אישיים, בחירת ספק ונפילה למצב בסיסי.
- ai_providers.py: הקריאה עצמה לספק.
- repository.py: שמירה ורישום.
"""
import re
from datetime import timedelta

from flask import current_app

from . import clock
from .ai_providers import ClaudeProvider, OfflineProvider, ProviderError

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_PATTERN = re.compile(r"\+?\d[\d\s-]{7,}\d")


def scrub(text):
    # לא שולחים כתובות מייל ומספרי טלפון לספק חיצוני
    text = EMAIL_PATTERN.sub("[email]", text)
    return PHONE_PATTERN.sub("[phone]", text)[:1000]


def provider():
    # בבדיקות אפשר להחליף ספק דרך app.extensions["timeflow_ai"]
    custom = current_app.extensions.get("timeflow_ai")
    if custom is not None:
        return custom
    if current_app.config["AI_ENABLED"]:
        return ClaudeProvider(current_app.config["AI_MODEL"])
    return OfflineProvider()


def suggest(repo, user_id, settings, purpose, text, context=None):
    context = context or {}
    lang = settings["lang"]
    offline = OfflineProvider()
    chosen = provider()

    def fallback(notice, status):
        repo.log_ai_request(user_id, purpose, chosen.name if status in ("error", "refused") else "offline", status)
        result = offline.suggest(purpose, text, lang, context)
        result.notice = notice
        return result

    if not settings["ai_enabled"]:
        return fallback("ai_disabled", "offline")
    if chosen.name == "offline":
        return fallback("ai_offline", "offline")
    since = clock.to_iso(clock.now() - timedelta(days=1))
    if repo.count_ai_requests(user_id, since) >= current_app.config["AI_DAILY_LIMIT"]:
        return fallback("ai_limited", "limited")
    try:
        result = chosen.suggest(purpose, scrub(text), lang, context)
    except ProviderError as error:
        return fallback("ai_error", error.status)
    repo.log_ai_request(user_id, purpose, chosen.name, "ok")
    return result
