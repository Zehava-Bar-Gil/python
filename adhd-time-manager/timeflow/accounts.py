"""חשבונות: הרשמה, התחברות, אימות מייל, איפוס סיסמה ושינוי סיסמה.

סיסמאות נשמרות רק כ-hash (scrypt של Werkzeug), אף פעם לא כטקסט גלוי ולא ביומנים.
"""
import re
from datetime import timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from . import clock, security

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8
STRONG_PASSWORD = 12
# סיסמאות ורצפים שמופיעים בראש הרשימות של סיסמאות שדלפו. סיסמה שבנויה מהם נחשבת חלשה
COMMON_PASSWORDS = ("password", "passw0rd", "qwerty", "qwertyuiop", "asdfgh", "zxcvbn", "iloveyou",
                    "letmein", "welcome", "admin", "abc123", "monkey", "dragon", "football", "sunshine")
SEQUENCES = ("0123456789", "9876543210", "abcdefghijklmnopqrstuvwxyz", "qwertyuiop", "asdfghjkl")
VERIFY_MAX_AGE = 2 * 24 * 3600
RESET_MAX_AGE = 3600
LOGIN_LOG_DAYS = timedelta(days=30)
# hash קבוע להשוואה כשהמייל לא קיים, כדי שזמן התגובה לא יסגיר אם יש חשבון
_DUMMY_HASH = generate_password_hash("timeflow-dummy-password")


def normalize_email(email):
    return (email or "").strip().lower()


def password_strength(password, email=""):
    # חלשה, בינונית או חזקה. לפי ההנחיות של NIST (SP 800-63B): אורך חשוב יותר מסוגי תווים,
    # וסיסמה נפוצה או צפויה חלשה גם כשהיא ארוכה. חלשה לא נשמרת, בינונית וחזקה כן
    password = password or ""
    plain = password.lower()
    core = re.sub(r"[\d\W_]+", "", plain)          # בלי מספרים וסימנים: "Password123!" -> "password"
    local = email.split("@")[0] if email else ""
    if (len(password) < MIN_PASSWORD
            or len(set(plain)) <= 2                          # aaaaaaaa, abababab
            or any(plain in run for run in SEQUENCES)        # 12345678, abcdefgh
            or core in COMMON_PASSWORDS or plain in COMMON_PASSWORDS
            or (local and len(local) >= 3 and local in plain)):
        return "weak"
    return "strong" if len(password) >= STRONG_PASSWORD else "medium"


def password_errors(password, email=""):
    errors = []
    if len(password or "") < MIN_PASSWORD:
        errors.append("err_password_short")
    elif email and password.strip().lower() == email:
        errors.append("err_password_email")
    elif password_strength(password, email) == "weak":
        errors.append("err_password_weak")
    return errors


def registration_errors(email, name, password):
    errors = []
    if not EMAIL_RE.match(email) or len(email) > 254:
        errors.append("err_email")
    if not name or len(name) > 40:
        errors.append("err_name")
    return errors + password_errors(password, email)


def register(repo, email, name, password, lang="he"):
    # מחזיר (מזהה, שגיאות). כשיש שגיאות לא נוצר דבר
    email, name = normalize_email(email), (name or "").strip()
    errors = registration_errors(email, name, password)
    if not errors and repo.get_user_by_email(email):
        errors.append("err_email_taken")
    if errors:
        return None, errors
    return repo.create_user(email, name, generate_password_hash(password), lang), []


def authenticate(repo, email, password, ip):
    # מחזיר (משתמשת, None) או (None, מפתח שגיאה)
    email = normalize_email(email)
    if security.login_blocked(repo, email, ip):
        return None, "err_rate_limited"
    user = repo.get_user_by_email(email)
    ok = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password or "")
    ok = ok and user is not None
    repo.record_login_attempt(email, ip, ok)
    # ניסיונות התחברות נשמרים רק 30 יום (מדיניות שמירת הנתונים)
    repo.clear_old_login_attempts(clock.to_iso(clock.now() - LOGIN_LOG_DAYS))
    return (user, None) if ok else (None, "err_login")


def change_password(repo, user, current, new):
    if not check_password_hash(user["password_hash"], current or ""):
        return ["err_current_password"]
    errors = password_errors(new, user["email"])
    if not errors:
        repo.set_password(user["id"], generate_password_hash(new))
    return errors


def verification_token(user):
    return security.make_token("verify", {"uid": user["id"], "email": user["email"]})


def confirm_verification(repo, token):
    data = security.read_token("verify", token, VERIFY_MAX_AGE)
    if not data:
        return False
    return repo.mark_email_verified(data["uid"], data["email"])


def reset_token(user):
    # האסימון כולל טביעה של הסיסמה הנוכחית: אחרי האיפוס הוא כבר לא תקף (שימוש אחד)
    return security.make_token("reset", {"uid": user["id"], "fp": security.auth_fingerprint(user["password_hash"])})


def user_for_reset(repo, token):
    data = security.read_token("reset", token, RESET_MAX_AGE)
    if not data:
        return None
    user = repo.get_user(data["uid"])
    if not user or security.auth_fingerprint(user["password_hash"]) != data["fp"]:
        return None
    return user


def reset_password(repo, token, new_password):
    user = user_for_reset(repo, token)
    if not user:
        return ["reset_bad"]
    errors = password_errors(new_password, user["email"])
    if not errors:
        repo.set_password(user["id"], generate_password_hash(new_password))
    return errors
