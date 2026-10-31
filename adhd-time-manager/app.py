import os

from flask import Flask, jsonify, render_template_string, request

import timeflow

app = Flask(__name__)

# רשימת הקישורים בדף הבית (slug -> שם)
PEOPLE = {
    "zehava": "זהבה",
    "yair": "יאיר",
    "guy": "גיא",
    "hillel": "הלל",
    "harel": "הראל",
    "ariel": "אריאל",
}

BASE = """<!doctype html>
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
</head>
<body>
  <nav><a href="/">דף הבית</a></nav>
  <h1>{{ title }}</h1>
  {{ content | safe }}
</body>
</html>"""

INDEX_CONTENT = """<ul>
{% for slug, name in people.items() %}  <li><a href="/{{ slug }}">{{ name }}</a></li>
{% endfor %}</ul>"""

PERSON_CONTENT = """<p>ברוכים הבאים לדף של {{ name }}.</p>"""


def render_page(title, content_template, **ctx):
    content = render_template_string(content_template, **ctx)
    return render_template_string(BASE, title=title, content=content)


@app.route("/")
def index():
    return render_page("שלד Flask", INDEX_CONTENT, people=PEOPLE)


# ---------- הדף של זהבה: TimeFlow ----------
# כל הקוד של TimeFlow נמצא בחבילה timeflow/ (נתיבים, מסד נתונים, אבטחה, מייל, AI).
# כאן רק מחברים אותה לשלד. הכתובות נשארות תחת /zehava כמו בגרסה 1.
timeflow.init_app(app)


@app.route("/yair")
def yair():
    return render_page("יאיר", PERSON_CONTENT, name="יאיר", slug="yair")


@app.route("/guy")
def guy():
    return render_page("גיא", PERSON_CONTENT, name="גיא", slug="guy")


@app.route("/hillel")
def hillel():
    return render_page("הלל", PERSON_CONTENT, name="הלל", slug="hillel")


@app.route("/harel")
def harel():
    return render_page("הראל", PERSON_CONTENT, name="הראל", slug="harel")


@app.route("/ariel")
def ariel():
    return render_page("אריאל", PERSON_CONTENT, name="אריאל", slug="ariel")


@app.route("/api/health")
def health():
    return jsonify(status="ok")


@app.route("/api/echo", methods=["POST"])
def echo():
    return jsonify(received=request.get_json(silent=True))


@app.errorhandler(404)
def not_found(e):
    # בדפים של TimeFlow: דף שגיאה רגוע. בשאר השלד: JSON כמו קודם
    if request.path.startswith("/zehava"):
        return timeflow.error_page(e)
    return jsonify(error="not found"), 404


if __name__ == "__main__":
    # מצב debug רק במחשב המקומי. בשרת אמיתי מריצים עם TIMEFLOW_DEBUG=0 (או עם waitress/gunicorn)
    debug = os.environ.get("TIMEFLOW_DEBUG", "1") == "1"
    # הסיכום היומי: תהליך רקע אחד. עם debug הקוד נטען פעמיים, ולכן מפעילים רק בתהליך הפעיל
    if app.config["SCHEDULER"] == "thread" and (not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true"):
        timeflow.start_scheduler(app)
    app.run(debug=debug)
