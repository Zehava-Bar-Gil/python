"""אבטחה: משתמשת מחוברת, CSRF, כותרות אבטחה, הגבלת ניסיונות ואסימונים חתומים."""
import hashlib
import hmac
import secrets
from datetime import timedelta

from flask import abort, current_app, g, redirect, request, session, url_for
from itsdangerous import BadSignature, URLSafeTimedSerializer

from . import clock

CSRF_FIELD = "_csrf"
# הסרה מדיוור בלחיצה אחת מתוכנת המייל: האסימון בכתובת הוא ההרשאה
CSRF_EXEMPT = {"zehava.unsubscribe"}

LOGIN_WINDOW = timedelta(minutes=15)
MAX_FAILS_PER_EMAIL = 5
MAX_FAILS_PER_IP = 30

# האתר לא משתמש ב-JavaScript בכלל, ולכן אפשר לחסום כל סקריפט. זו הגנה חזקה מפני XSS
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'none'",
    "style-src 'self' https://fonts.googleapis.com",
    "style-src-attr 'unsafe-inline'",
    "font-src https://fonts.gstatic.com",
    "img-src 'self' data:",
    "media-src 'self'",
    "form-action 'self' https://accounts.google.com",
    "frame-ancestors 'none'",
    "base-uri 'none'",
    "object-src 'none'",
])


# ---------- CSRF ----------
def csrf_token():
    if CSRF_FIELD not in session:
        session[CSRF_FIELD] = secrets.token_urlsafe(32)
    return session[CSRF_FIELD]


def check_csrf():
    # כל POST חייב לשאת את האסימון מהטופס. טופס מאתר זר לא מכיר אותו
    if request.method != "POST" or request.endpoint in CSRF_EXEMPT:
        return
    sent = request.form.get(CSRF_FIELD, "")
    expected = session.get(CSRF_FIELD, "")
    if not expected or not hmac.compare_digest(sent, expected):
        abort(400)


# ---------- משתמשת מחוברת ----------
def auth_fingerprint(password_hash):
    # טביעה קצרה של הסיסמה הנוכחית. אחרי החלפת סיסמה, כל ההתחברויות הישנות מתבטלות
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def login_user(user):
    # session חדש לגמרי בכל התחברות (מונע session fixation)
    session.clear()
    session.permanent = True
    session["uid"] = user["id"]
    session["fp"] = auth_fingerprint(user["password_hash"])


def logout_user():
    session.clear()


def load_user(repo):
    g.user = None
    g.settings = None
    user_id = session.get("uid")
    if not user_id:
        return
    user = repo.get_user(user_id)
    if user and hmac.compare_digest(session.get("fp", ""), auth_fingerprint(user["password_hash"])):
        g.user = user
        g.settings = repo.get_settings(user_id)
    else:
        session.clear()


def login_redirect(public_endpoints):
    # כל דף דורש התחברות, חוץ מרשימה סגורה של דפים ציבוריים. כך דף חדש מוגן כברירת מחדל
    if g.get("user") is not None or request.endpoint in public_endpoints or request.endpoint is None:
        return None
    target = request.full_path.rstrip("?") if request.method == "GET" else None
    return redirect(url_for("zehava.login", next=target))


def safe_next(target, default_endpoint="zehava.home"):
    # מפנים רק לדפים של האתר עצמו (מונע open redirect)
    if target and target.startswith("/zehava") and "//" not in target and "\\" not in target:
        return target
    return url_for(default_endpoint)


def client_ip():
    return request.remote_addr or "unknown"


# ---------- הגבלת ניסיונות ----------
def login_blocked(repo, email, ip):
    since = clock.to_iso(clock.now() - LOGIN_WINDOW)
    return (repo.failed_logins(since, email=email) >= MAX_FAILS_PER_EMAIL
            or repo.failed_logins(since, ip=ip) >= MAX_FAILS_PER_IP)


# ---------- אסימונים חתומים (מייל, איפוס, הסרה, משוב) ----------
def _serializer(purpose):
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=f"timeflow-{purpose}")


def make_token(purpose, data):
    return _serializer(purpose).dumps(data)


def read_token(purpose, token, max_age):
    try:
        return _serializer(purpose).loads(token, max_age=max_age)
    except BadSignature:   # כולל אסימון שפג תוקפו
        return None


# ---------- כותרות אבטחה ----------
def add_security_headers(response):
    response.headers.setdefault("Content-Security-Policy", CSP)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if current_app.config.get("SESSION_COOKIE_SECURE"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    # דפים אישיים לא נשמרים במטמון, כדי שאחרי יציאה "חזרה" בדפדפן לא תציג אותם
    if g.get("user") is not None:
        response.headers["Cache-Control"] = "no-store"
    return response
