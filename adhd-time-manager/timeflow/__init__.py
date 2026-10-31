"""TimeFlow: האפליקציה של זהבה, כחבילה שמתחברת לשלד ה-Flask הקיים.

ב-app.py מספיקה שורה אחת: timeflow.init_app(app). כל השאר כאן:
הגדרות, מסד נתונים, אבטחה, הנתיבים תחת /zehava, דפי שגיאה ופקודות ניהול.
"""
import logging
import sqlite3
from pathlib import Path

import click
from flask import g, has_request_context, jsonify, render_template, request

from . import clock, db, focus_timer, mailer, security
from .config import build_config
from .repository import Repository
from .views import PUBLIC, bp, common_context, say

log = logging.getLogger("timeflow")
start_scheduler = mailer.start_scheduler


def init_app(app, instance_dir=None, overrides=None):
    app.config.update(build_config(Path(instance_dir or app.instance_path)))
    app.config.update(overrides or {})
    db.migrate(app.config["DATABASE"], app.config["BACKUP_DIR"])

    app.teardown_appcontext(db.close_db)
    app.before_request(before_request)
    app.after_request(security.add_security_headers)
    app.context_processor(lambda: common_context() if is_timeflow_request() else {})
    app.register_blueprint(bp)
    for code in (400, 403, 404, 405, 413, 500):
        app.register_error_handler(code, error_page)
    app.register_error_handler(sqlite3.Error, database_error)
    register_commands(app)
    return app


def is_timeflow_request():
    # בלי בקשה (למשל המייל היומי שנשלח מתהליך הרקע) אין דף של TimeFlow
    if not has_request_context():
        return False
    return request.path == "/zehava" or request.path.startswith("/zehava/")


def before_request():
    # רק לדפים של TimeFlow. שאר השלד (/, /api/...) ממשיך לעבוד כמו קודם
    if not is_timeflow_request():
        return None
    repo = Repository(db.get_db())
    g.repo = repo
    security.load_user(repo)
    security.check_csrf()
    blocked = security.login_redirect(PUBLIC)
    if blocked or g.user is None:
        return blocked
    # סשן שהזמן שלו נגמר נסגר כאן, בכל דף שנפתח, ונספר פעם אחת בלבד
    finished = focus_timer.complete_if_due(repo, g.user["id"], clock.now())
    if finished:
        say("session_done" if finished["kind"] == "focus" else "break_done")
        g.chime = bool(g.settings["timer_chime"])
    return None


def error_page(error):
    code = getattr(error, "code", 500) or 500
    if not is_timeflow_request():
        return jsonify(error=getattr(error, "name", "error").lower()), code
    keys = {400: "csrf_text", 404: "not_found_text", 500: "server_error_text"}
    title = "not_found_title" if code == 404 else "error_title"
    return render_template("zehava/error.html", code=code, title_key=title,
                           text_key=keys.get(code, "server_error_text"), active=None), code


def database_error(error):
    # תקלה במסד לא מפילה את האתר ולא מציגה פרטים טכניים. הפרטים נרשמים ביומן השרת בלבד
    log.error("database error on %s: %s", request.path, type(error).__name__)
    error.code = 500
    return error_page(error)


# ---------- פקודות ניהול: flask --app app <פקודה> ----------
def register_commands(app):
    @app.cli.command("init-db")
    def init_db_command():
        """יוצר או מעדכן את מסד הנתונים."""
        version = db.migrate(app.config["DATABASE"], app.config["BACKUP_DIR"])
        click.echo(f"database ready (schema v{version}): {app.config['DATABASE']}")

    @app.cli.command("backup-db")
    def backup_command():
        """שומר גיבוי של המסד בתיקייה instance/backups."""
        click.echo(db.backup(app.config["DATABASE"], app.config["BACKUP_DIR"]))

    @app.cli.command("restore-db")
    @click.argument("backup_file")
    def restore_command(backup_file):
        """משחזר גיבוי (כשהשרת כבוי). לפני השחזור נשמר גיבוי של המצב הנוכחי."""
        db.backup(app.config["DATABASE"], app.config["BACKUP_DIR"], label="before-restore")
        db.restore(backup_file, app.config["DATABASE"])
        click.echo("restored")

    @app.cli.command("send-daily")
    def send_daily_command():
        """שולח עכשיו את הסיכומים היומיים שהגיע זמנם (ל-cron או ל-Task Scheduler)."""
        click.echo(f"sent: {mailer.run_daily_emails(app)}")

    @app.cli.command("run-scheduler")
    def run_scheduler_command():
        """מריץ רק את תהליך הסיכום היומי, בלי שרת אתר."""
        import time
        click.echo("daily email scheduler running (Ctrl+C to stop)")
        while True:
            mailer.run_daily_emails(app)
            time.sleep(60)

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """יוצר משתמשת הדגמה עם 3 שבועות של נתונים סינתטיים."""
        from .demo import seed_demo
        email, password = seed_demo(app)
        click.echo(f"demo user: {email} / {password}")
