"""כלים משותפים לבדיקות: אפליקציה עם מסד זמני, משתמשות סינתטיות ושעון קפוא.

כל בדיקה מקבלת תיקייה זמנית משלה, ולכן אין תלות בין בדיקות ואין נגיעה בנתונים אמיתיים.
"""
import email
import email.policy
import logging
import re
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from flask import Flask

import timeflow
from timeflow import clock
from timeflow.db import connect
from timeflow.repository import Repository

PROJECT_DIR = Path(__file__).resolve().parent.parent
CSRF = "test-csrf-token"

# אזהרות צפויות (מייל שנכשל בכוונה, תקלת AI מדומה) לא מלכלכות את פלט הבדיקות
logging.getLogger("timeflow").setLevel(logging.CRITICAL)


def make_app(folder, **overrides):
    app = Flask("app", root_path=str(PROJECT_DIR))
    config = {
        "TESTING": True,
        "DATABASE": str(Path(folder) / "test.db"),
        "BACKUP_DIR": str(Path(folder) / "backups"),
        "OUTBOX_DIR": str(Path(folder) / "outbox"),
        "MAIL_BACKEND": "file",
        "SCHEDULER": "off",
        "AI_ENABLED": False,
        "GOOGLE_CLIENT_ID": "",
        "GOOGLE_CLIENT_SECRET": "",
        "BASE_URL": "http://localhost",
        "SECRET_KEY": "test-secret-key",
    }
    config.update(overrides)
    return timeflow.init_app(app, instance_dir=folder, overrides=config)


class TimeFlowTestCase(unittest.TestCase):
    app_overrides = {}

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="timeflow-test-")
        # נרשם ראשון ולכן רץ אחרון, אחרי שכל החיבורים למסד נסגרו (חשוב ב-Windows)
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        self.addCleanup(clock.freeze, None)
        self.app = make_app(self.folder, **self.app_overrides)
        self.freeze(datetime(2026, 10, 29, 10, 0, tzinfo=clock.LOCAL_TZ))

    # ---------- זמן ----------
    def freeze(self, moment):
        clock.freeze(moment)

    # ---------- מסד ----------
    def repo(self):
        conn = connect(self.app.config["DATABASE"])
        self.addCleanup(conn.close)
        return Repository(conn)

    # ---------- משתמשות ובקשות ----------
    def client(self):
        return self.app.test_client()

    def post(self, client, url, data=None, **kwargs):
        # כל טופס אמיתי נושא אסימון CSRF. כאן שמים אותו ב-session ובטופס
        with client.session_transaction() as session:
            session["_csrf"] = CSRF
        return client.post(url, data={"_csrf": CSRF, **(data or {})}, **kwargs)

    def register(self, email="zehava@example.com", name="Zehava", password="calm-steps-2026", verified=True):
        client = self.client()
        response = self.post(client, "/zehava/register", {"email": email, "name": name, "password": password})
        self.assertEqual(response.status_code, 302, response.get_data(as_text=True)[:500])
        user = self.repo().get_user_by_email(email)
        if verified:
            self.repo().mark_email_verified(user["id"], email)
        return client, user["id"]

    def html(self, response):
        return response.get_data(as_text=True)

    def outbox(self):
        """המיילים שנכתבו לתיקיית outbox, מפוענחים: [(נושא, טקסט, הודעה)]."""
        messages = []
        for path in sorted(Path(self.app.config["OUTBOX_DIR"]).glob("*.eml")):
            message = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
            body = message.get_body(preferencelist=("plain",))
            messages.append((str(message["Subject"]), body.get_content() if body else "", message))
        return messages

    def csrf_from(self, html):
        match = re.search(r'name="_csrf" value="([^"]+)"', html)
        return match.group(1) if match else None
