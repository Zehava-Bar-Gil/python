"""Google Calendar: חיבור OAuth 2.0 וקריאת אירועים, עם urllib בלבד.

- הרשאה מינימלית: קריאת אירועים בלבד (calendar.events.readonly).
- state אקראי ב-session מגן מפני זיוף של החזרה מ-Google (CSRF ב-OAuth).
- האסימונים נשמרים בשרת בלבד. אסימון שפג תוקפו מתחדש לבד, ואסימון שבוטל מסומן "צריך חידוש".
- האתר מציג "מסונכרן" רק אחרי קריאה שהצליחה בפועל.
- סנכרון חוזר מעדכן אירועים קיימים לפי המזהה של Google, ולכן אין כפילויות.
"""
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from . import clock

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly"
SYNC_PAST_DAYS = 7
SYNC_FUTURE_DAYS = 31


class GoogleError(Exception):
    def __init__(self, kind):
        super().__init__(kind)
        self.kind = kind    # "config", "auth", "network", "api"


def http_request(method, url, data=None, headers=None):
    # הבקשה היחידה לרשת בקובץ. בבדיקות מחליפים אותה בפונקציה מדומה
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        try:
            payload = json.loads(error.read() or b"{}")
        except ValueError:
            payload = {}
        return error.code, payload
    except (urllib.error.URLError, OSError, ValueError):
        raise GoogleError("network")


def is_configured(config):
    return bool(config.get("GOOGLE_CLIENT_ID") and config.get("GOOGLE_CLIENT_SECRET"))


def redirect_uri(config):
    return config.get("GOOGLE_REDIRECT_URI") or f"{config['BASE_URL']}/zehava/calendar/oauth/callback"


def new_state():
    return secrets.token_urlsafe(24)


def authorization_url(config, state):
    params = {
        "client_id": config["GOOGLE_CLIENT_ID"],
        "redirect_uri": redirect_uri(config),
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def _expires_at(seconds):
    return clock.to_iso(clock.now() + timedelta(seconds=int(seconds or 3600)))


def exchange_code(repo, config, user_id, code):
    status, data = http_request("POST", TOKEN_URL, {
        "code": code,
        "client_id": config["GOOGLE_CLIENT_ID"],
        "client_secret": config["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": redirect_uri(config),
        "grant_type": "authorization_code",
    })
    if status != 200 or "access_token" not in data:
        raise GoogleError("auth")
    if SCOPE not in data.get("scope", SCOPE).split():
        raise GoogleError("auth")
    repo.save_google_account(user_id, data["access_token"], data.get("refresh_token"),
                             _expires_at(data.get("expires_in")), data.get("scope", SCOPE))


def access_token(repo, config, user_id):
    # אסימון בתוקף. אם עומד לפוג, מחדשים אותו עם ה-refresh token
    account = repo.get_google_account(user_id)
    if not account:
        raise GoogleError("auth")
    if clock.from_iso(account["expires_at"]) - clock.now() > timedelta(seconds=60):
        return account["access_token"]
    if not account["refresh_token"]:
        raise GoogleError("auth")
    status, data = http_request("POST", TOKEN_URL, {
        "client_id": config["GOOGLE_CLIENT_ID"],
        "client_secret": config["GOOGLE_CLIENT_SECRET"],
        "refresh_token": account["refresh_token"],
        "grant_type": "refresh_token",
    })
    if status != 200 or "access_token" not in data:
        # invalid_grant = המשתמשת ביטלה את הגישה ב-Google, או שהאסימון פג
        repo.update_google_sync(user_id, last_error="auth")
        raise GoogleError("auth")
    repo.save_google_account(user_id, data["access_token"], None, _expires_at(data.get("expires_in")),
                             account["scope"])
    return data["access_token"]


def _event_times(event):
    start, end = event.get("start", {}), event.get("end", {})
    if "dateTime" in start:
        return (clock.to_iso(datetime.fromisoformat(start["dateTime"])),
                clock.to_iso(datetime.fromisoformat(end["dateTime"])) if "dateTime" in end else None, False)
    day = clock.parse_day(start.get("date"))
    if not day:
        return None
    start_iso, _ = clock.day_bounds(day)
    return start_iso, None, True


def sync(repo, config, user_id, today=None):
    # מושך אירועים משבוע אחורה עד חודש קדימה, ושומר אותם בלי כפילויות
    if not is_configured(config):
        raise GoogleError("config")
    today = today or clock.today()
    start_iso, _ = clock.day_bounds(today - timedelta(days=SYNC_PAST_DAYS))
    _, end_iso = clock.day_bounds(today + timedelta(days=SYNC_FUTURE_DAYS))
    token = access_token(repo, config, user_id)
    params = {"timeMin": start_iso.replace("+00:00", "Z"), "timeMax": end_iso.replace("+00:00", "Z"),
              "singleEvents": "true", "orderBy": "startTime", "maxResults": "250"}
    status, data = http_request("GET", f"{EVENTS_URL}?{urllib.parse.urlencode(params)}",
                                headers={"Authorization": f"Bearer {token}"})
    if status in (401, 403):
        repo.update_google_sync(user_id, last_error="auth")
        raise GoogleError("auth")
    if status != 200:
        repo.update_google_sync(user_id, last_error="api")
        raise GoogleError("api")
    seen = set()
    for event in data.get("items", []):
        if event.get("status") == "cancelled" or "id" not in event:
            continue
        times = _event_times(event)
        if not times:
            continue
        seen.add(event["id"])
        repo.upsert_calendar_event(user_id, event["id"], (event.get("summary") or "")[:200], *times)
    repo.remove_calendar_events_not_in(user_id, start_iso, end_iso, seen)
    repo.update_google_sync(user_id, last_sync_at=clock.now_iso())
    return len(seen)


def disconnect(repo, config, user_id):
    # מבטלים את האסימון אצל Google (גם אם זה נכשל) ומוחקים אותו ואת האירועים מהמסד
    account = repo.get_google_account(user_id)
    if account:
        try:
            http_request("POST", REVOKE_URL, {"token": account["refresh_token"] or account["access_token"]})
        except GoogleError:
            pass
    repo.delete_google_account(user_id)


def status(repo, config, user_id):
    # מצב היומן לתצוגה. "synced" רק אחרי סנכרון שהצליח באמת
    if not is_configured(config):
        return {"state": "not_configured"}
    account = repo.get_google_account(user_id)
    if not account:
        return {"state": "internal"}
    if account["last_error"] == "auth":
        return {"state": "needs_reconnect"}
    if not account["last_sync_at"]:
        return {"state": "pending"}
    return {"state": "synced", "at": clock.from_iso(account["last_sync_at"]).strftime("%H:%M")}
