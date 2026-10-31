# אילו קבצים השתנו מגרסה 1

רשימה להשוואה לפני commit. הקוד של גרסה 1, כמו שהיה, נמצא בתיקייה `v1-original/`.

## שונו (11)

- `.gitignore`
- `app.py`
- `requirements.txt`
- `static/css/zehava.css`
- `templates/zehava/base.html`
- `templates/zehava/email.html`
- `templates/zehava/focus.html`
- `templates/zehava/index.html`
- `templates/zehava/login.html`
- `templates/zehava/macros.html`
- `templates/zehava/sounds.html`

## הועברו (1)

- `PLAN.md` ← עבר ל-`docs/history/PLAN-v1.md`

## חדשים (97)

- `.env.example`
- `CHANGELOG.md`
- `IMPLEMENTATION_PLAN.md`
- `PROJECT_AUDIT.md`
- `README.md`
- `docs/`: 26 קבצים
- `static/sounds/chime.mp3`
- `static/sounds/chime.ogg`
- `templates/`: 22 קבצים
- `tests/__init__.py`
- `tests/helpers.py`
- `tests/test_ai.py`
- `tests/test_auth.py`
- `tests/test_calendar.py`
- `tests/test_isolation.py`
- `tests/test_personalization.py`
- `tests/test_pulse_mail.py`
- `tests/test_tasks_notes.py`
- `tests/test_timer_journey.py`
- `tests/test_ui_db.py`
- `timeflow/`: 30 קבצים
- `tools/make_sounds.py`

## לא השתנו (11)

- `mail_config.example.json`
- `static/img/balloon.png`
- `static/img/sky-mountain.jpg`
- `static/sounds/calm.mp3`
- `static/sounds/calm.ogg`
- `static/sounds/deep.mp3`
- `static/sounds/deep.ogg`
- `static/sounds/reading.mp3`
- `static/sounds/reading.ogg`
- `static/sounds/study.mp3`
- `static/sounds/study.ogg`

## לא נכללים ב-zip (נשארים רק במחשב)

- `instance/`: מסד הנתונים, המפתח הסודי, הגיבויים ותיבת הדואר של מצב הפיתוח
- `.env` ו-`mail_config.json`: סיסמאות ומפתחות
- `.venv/` ו-`__pycache__/`
