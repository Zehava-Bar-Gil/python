"""הגדרות TimeFlow. הסודות נקראים ממשתני סביבה או מקובץ .env, ואף פעם לא נכתבים בקוד."""
import json
import os
import secrets
from datetime import timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_AI_MODEL = "claude-opus-5-5"


def load_env_file(path):
    # קובץ .env פשוט: KEY=VALUE בכל שורה. משתנה שכבר מוגדר בסביבה לא נדרס
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def secret_key(instance_dir):
    # בפיתוח נוצר מפתח אקראי ונשמר ב-instance, כדי שההתחברות תשרוד הפעלה מחדש
    key = os.environ.get("TIMEFLOW_SECRET_KEY")
    if key:
        return key
    path = instance_dir / "secret_key"
    if path.exists():
        return path.read_text().strip()
    key = secrets.token_hex(32)
    path.write_text(key)
    return key


def legacy_mail_settings():
    # תאימות לגרסה 1: אם יש mail_config.json ישן, משתמשים בו לשליחה דרך Gmail
    path = PROJECT_DIR / "mail_config.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if "@" not in data.get("gmail", "") or not data.get("app_password"):
        return {}
    return {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": 465,
        "SMTP_SSL": True,
        "SMTP_USER": data["gmail"],
        "SMTP_PASSWORD": data["app_password"].replace(" ", ""),
        "MAIL_FROM": data["gmail"],
    }


def build_config(instance_dir):
    instance_dir = Path(instance_dir)
    instance_dir.mkdir(parents=True, exist_ok=True)
    load_env_file(PROJECT_DIR / ".env")

    smtp = {
        "SMTP_HOST": os.environ.get("SMTP_HOST", ""),
        "SMTP_PORT": int(os.environ.get("SMTP_PORT", "465")),
        "SMTP_SSL": env_bool("SMTP_SSL", True),
        "SMTP_USER": os.environ.get("SMTP_USER", ""),
        "SMTP_PASSWORD": os.environ.get("SMTP_PASSWORD", ""),
        "MAIL_FROM": os.environ.get("MAIL_FROM", os.environ.get("SMTP_USER", "")),
    }
    if not smtp["SMTP_HOST"]:
        smtp.update(legacy_mail_settings())
    # בלי שרת SMTP, המיילים נשמרים כקבצים ב-instance/outbox (מצב פיתוח גלוי)
    mail_backend = os.environ.get("MAIL_BACKEND") or ("smtp" if smtp.get("SMTP_HOST") else "file")

    return {
        "SECRET_KEY": secret_key(instance_dir),
        "DATABASE": os.environ.get("TIMEFLOW_DATABASE", str(instance_dir / "timeflow.db")),
        "BACKUP_DIR": str(instance_dir / "backups"),
        "BASE_URL": os.environ.get("TIMEFLOW_BASE_URL", "http://127.0.0.1:5000").rstrip("/"),
        # עוגיית ההתחברות: לא נגישה לסקריפטים, לא נשלחת מאתרים זרים, ובשרת HTTPS רק בחיבור מוצפן
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": env_bool("TIMEFLOW_HTTPS"),
        "PERMANENT_SESSION_LIFETIME": timedelta(days=14),
        "MAX_CONTENT_LENGTH": 64 * 1024,
        "MAIL_BACKEND": mail_backend,
        "OUTBOX_DIR": str(instance_dir / "outbox"),
        **smtp,
        "AI_MODEL": os.environ.get("TIMEFLOW_AI_MODEL", DEFAULT_AI_MODEL),
        "AI_DAILY_LIMIT": int(os.environ.get("TIMEFLOW_AI_DAILY_LIMIT", "20")),
        "AI_ENABLED": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "GOOGLE_CLIENT_ID": os.environ.get("GOOGLE_CLIENT_ID", ""),
        "GOOGLE_CLIENT_SECRET": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        "GOOGLE_REDIRECT_URI": os.environ.get("GOOGLE_REDIRECT_URI", ""),
        # תהליך הרקע של הסיכום היומי: "thread" בתוך השרת, או "off" כשמתזמנים מבחוץ
        "SCHEDULER": os.environ.get("TIMEFLOW_SCHEDULER", "thread"),
    }
