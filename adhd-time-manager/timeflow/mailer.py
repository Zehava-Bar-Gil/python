"""מיילים: שליחה, הסיכום היומי (Daily Reflection) ותזמון.

- בפיתוח, בלי שרת SMTP, המיילים נשמרים כקבצי .eml בתיקייה instance/outbox. כך בודקים
  בלי חשבון מייל, והאתר אומר זאת בגלוי.
- הסיכום היומי "נתפס" במסד לפני השליחה (UNIQUE למשתמשת וליום), ולכן גם שני תהליכים
  שרצים יחד לא ישלחו אותו פעמיים.
- נושא המייל לא כולל תוכן אישי, כדי שלא יופיע במסך הנעילה.
- סיסמאות ותוכן המייל לא נכתבים ליומן (log).
"""
import logging
import smtplib
import ssl
import threading
import time
import uuid
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from flask import render_template, url_for

from . import clock, focus_timer, journey, security, ui
from .db import connect
from .repository import Repository
from .texts import texts

log = logging.getLogger("timeflow.mail")
MAX_ATTEMPTS = 3
RETRY_AFTER = timedelta(minutes=30)
PULSE_LINK_MAX_AGE = 3 * 24 * 3600


class MailError(Exception):
    pass


def send_email(config, to, subject, html, text, headers=None):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(("TimeFlow", config.get("MAIL_FROM") or "timeflow@localhost"))
    message["To"] = to
    for key, value in (headers or {}).items():
        message[key] = value
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    backend = config["MAIL_BACKEND"]
    if backend == "smtp":
        _send_smtp(config, message)
    elif backend == "file":
        _save_to_outbox(config["OUTBOX_DIR"], message)
    else:
        raise MailError("mail backend is off")


def _send_smtp(config, message):
    try:
        context = ssl.create_default_context()
        if config["SMTP_SSL"]:
            server = smtplib.SMTP_SSL(config["SMTP_HOST"], config["SMTP_PORT"], timeout=20, context=context)
        else:
            server = smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"], timeout=20)
            server.starttls(context=context)
        with server:
            if config.get("SMTP_USER"):
                server.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        # רק סוג השגיאה נרשם, בלי פרטי התחברות
        raise MailError(type(error).__name__) from error


def _save_to_outbox(folder, message):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{clock.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.eml"
    path.write_bytes(bytes(message))
    return path


def external_url(app, endpoint, **values):
    # קישור מלא למייל, גם כשאין בקשה פעילה (למשל בתהליך הרקע)
    with app.test_request_context(base_url=app.config["BASE_URL"]):
        return url_for(endpoint, _external=True, **values)


# ---------- מיילים של חשבון ----------
def send_account_email(app, repo, user, kind, lang, link):
    # kind: "verify" או "reset". מחזיר True אם נשלח
    t = texts(lang)
    html = render_template("zehava/email_account.html", t=t, lang=lang, kind=kind, link=link,
                           name=ui.first_name(user, lang))
    body = t[f"{kind}_body"] + "\n\n" + link + "\n\n" + t["mail_ignore"]
    try:
        send_email(app.config, user["email"], t[f"{kind}_subject"], html, body)
    except MailError as error:
        repo.log_email(user["id"], kind, "failed", str(error))
        log.warning("account email failed kind=%s user=%s", kind, user["id"])
        return False
    repo.log_email(user["id"], kind, "sent")
    return True


# ---------- הסיכום היומי ----------
def daily_summary(repo, user_id, day):
    # רק נתונים שנמדדו בפועל. אין הערכות ואין ציון
    start, end = clock.day_bounds(day)
    done = [t for t in repo.list_tasks(user_id, status="done") if t["completed_at"] and start <= t["completed_at"] < end]
    stats = focus_timer.day_stats(repo, user_id, day)
    return {
        "done": [t["title"] for t in done],
        "sessions": stats["completed"],
        "focus_minutes": stats["focus_seconds"] // 60,
        "stations": journey.stations_reached(repo, user_id, day),
    }


def render_daily(app, user, lang, summary, pulse_link, unsubscribe_link):
    t = texts(lang)
    name = ui.first_name(user, lang)   # השם בשפה של המייל
    html = render_template("zehava/email.html", t=t, lang=lang, name=name, summary=summary,
                           pulse_link=pulse_link, unsubscribe_link=unsubscribe_link,
                           today_label=f"{clock.today().day} {t['months'][clock.today().month - 1]}")
    lines = [t["mail_hello"].format(name=name), "", t["mail_intro"]]
    lines += [f"- {title}" for title in summary["done"]]
    lines += [f"{t['mail_sessions']}: {summary['sessions']}", f"{t['mail_focus_time']}: {summary['focus_minutes']}",
              "", f"{t['mail_pulse_cta']}: {pulse_link}", "", t["mail_closing"], "",
              f"{t['mail_unsubscribe']}: {unsubscribe_link}"]
    return t["mail_subject_daily"], html, "\n".join(lines)


def _daily_message(app, repo, user, day, lang):
    pulse_link = external_url(app, "zehava.pulse_from_email",
                              token=security.make_token("pulse", {"uid": user["id"], "day": day.isoformat()}))
    unsubscribe_link = external_url(app, "zehava.unsubscribe", token=security.make_token("unsubscribe", {"uid": user["id"]}))
    subject, html, text = render_daily(app, user, lang, daily_summary(repo, user["id"], day), pulse_link, unsubscribe_link)
    headers = {"List-Unsubscribe": f"<{unsubscribe_link}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
    return subject, html, text, headers


def send_daily(app, repo, user, day, log_id):
    # שולח סיכום אחד שכבר "נתפס" במסד, ומעדכן את הסטטוס
    subject, html, text, headers = _daily_message(app, repo, user, day, user.get("lang", "he"))
    try:
        send_email(app.config, user["email"], subject, html, text, headers=headers)
    except MailError as error:
        repo.finish_email(log_id, "failed", str(error))
        log.warning("daily email failed user=%s", user["id"])
        return False
    repo.finish_email(log_id, "sent")
    return True


def send_summary_now(app, repo, user, lang):
    # הכפתור "שליחת הסיכום עכשיו". לא נוגע בסיכום היומי המתוזמן, שיישלח בשעה שנבחרה
    subject, html, text, headers = _daily_message(app, repo, user, clock.today(), lang)
    try:
        send_email(app.config, user["email"], subject, html, text, headers=headers)
    except MailError as error:
        repo.log_email(user["id"], "manual", "failed", str(error))
        log.warning("manual email failed user=%s", user["id"])
        return False
    repo.log_email(user["id"], "manual", "sent")
    return True


def run_daily_emails(app, now=None):
    # עובר על כל מי שביקשה סיכום, ושולח למי שהגיעה השעה שלה ועוד לא קיבלה היום
    now = now or clock.now()
    sent = 0
    with app.app_context():
        conn = connect(app.config["DATABASE"])
        try:
            repo = Repository(conn)
            for user in repo.users_with_daily_email():
                at = clock.parse_hhmm(user["daily_email_at"])
                if not at or now.time() < at:
                    continue
                day = now.date()
                log_id = repo.claim_daily_email(user["id"], day.isoformat())
                if log_id is None:
                    status = repo.daily_email_status(user["id"], day.isoformat())
                    if status and status["status"] == "failed" and \
                            now - clock.from_iso(status["updated_at"]) >= RETRY_AFTER:
                        log_id = repo.retry_daily_email(user["id"], day.isoformat(), MAX_ATTEMPTS)
                if log_id is not None and send_daily(app, repo, user, day, log_id):
                    sent += 1
        finally:
            conn.close()
    return sent


_scheduler = {"thread": None}


def start_scheduler(app, interval=60):
    # תהליך רקע בתוך השרת: פעם בדקה בודק אם הגיע זמן לשלוח. בייצור אפשר במקומו להריץ
    # את הפקודה `flask --app app send-daily` מ-cron או מ-Task Scheduler
    if _scheduler["thread"] is not None:
        return

    def loop():
        while True:
            try:
                run_daily_emails(app)
            except Exception:   # התהליך לא נופל בגלל תקלה אחת
                log.exception("daily email loop error")
            time.sleep(interval)

    _scheduler["thread"] = threading.Thread(target=loop, name="timeflow-mail", daemon=True)
    _scheduler["thread"].start()
