# TimeFlow 🎈

**A calmer way to focus, one step at a time.**

אפליקציית Flask לניהול זמן ומיקוד, בעברית ובאנגלית. כל הלוגיקה ב-Python, בלי JavaScript.
פרויקט הגמר של זהבה בקורס Pretech. האתר נמצא בכתובת `/zehava` בתוך השלד של הקורס.

בכל רגע רואים רק את מה שצריך עכשיו: צעד אחד, פעולה אחת, והכדור הפורח שעולה בשביל ההר לפי מה שבאמת נעשה.

---

## מה יש באתר

| | כלי | מה עושים בו |
|---|---|---|
| ✅ | **רשימת מטלות** | משימות עם תאריך, שעה, קטגוריה ועדיפות. פירוק לצעדים קטנים. "קשה להתחיל?" |
| 📝 | **פתקיות** | פתקים בכתב יד בעברית ובאנגלית, ב-4 צבעים, עם תגית. הפיכה למשימה, לצעד או ל-Snooze |
| 🍅 | **טיימר עגבנייה** | כל אורך, או גמיש. השהיה, המשך, הפסקות קצרות וארוכות, צליל סיום (לא חובה) |
| 🌙 | **Snooze** | מקום לפרוק מחשבות, למיין אותן, ולקבל הצעה לצעד קטן (עם AI או בלי) |
| 📅 | **יומן Google** | לוח חודשי עם המשימות, וחיבור לא חובה ל-Google Calendar (קריאה בלבד) |

ובנוסף, מחוץ לתפריט העליון: **דף הבית** ("עכשיו"), **התובנות שלי**, **Daily Pulse** (משוב יומי), **סיכום יומי במייל**, **Soundscape**, **הגדרות** ו**פרטיות**.

---

## התקנה והרצה (Windows)

```bat
cd C:\Users\zehav\OneDrive\Desktop\i\python\adhd-time-manager
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

ואז לפתוח בדפדפן: **http://127.0.0.1:5000/zehava**

בפעם הראשונה נוצרת התיקייה `instance/` עם מסד הנתונים (`timeflow.db`) ומפתח הצפנה. היא לא עולה לגיט.
נרשמים עם מייל וסיסמה (לפחות 8 תווים).

### משתמשת הדגמה

```bat
flask --app app seed-demo
```

יוצר את `demo@timeflow.local` עם הסיסמה `timeflow-demo`, ו-3 שבועות של נתונים סינתטיים (משימות, סשנים, משוב יומי), כדי לראות את המסע והתובנות בפעולה. הפקודה מוחקת ויוצרת מחדש רק את משתמשת ההדגמה.

### בדיקות

```bat
python -m unittest
```

150 בדיקות אוטומטיות, עם מסד זמני ונתונים סינתטיים בלבד. הן לא נוגעות במסד האמיתי ולא שולחות מיילים או בקשות לאינטרנט. התוצאות האחרונות: [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md).

### פקודות ניהול

| פקודה | מה עושה |
|---|---|
| `flask --app app init-db` | יוצר או מעדכן את מסד הנתונים |
| `flask --app app backup-db` | שומר גיבוי ב-`instance/backups` |
| `flask --app app restore-db <קובץ>` | משחזר גיבוי (כשהשרת כבוי). לפני כן נשמר גיבוי של המצב הנוכחי |
| `flask --app app send-daily` | שולח עכשיו את הסיכומים היומיים שהגיע זמנם |
| `flask --app app run-scheduler` | מריץ רק את תהליך הסיכום היומי, בלי אתר |
| `flask --app app seed-demo` | משתמשת הדגמה |

---

## חיבור לשירותים חיצוניים (לא חובה)

האתר עובד בלי אף מפתח. כל חלק שצריך שירות חיצוני אומר בגלוי כשהוא לא מחובר, ואף כפתור לא מעמיד פנים.

מעתיקים את `.env.example` ל-`.env` (באותה תיקייה) וממלאים רק את מה שצריך. הקובץ `.env` נמצא ב-`.gitignore`.

### AI ב-Snooze (Claude)
1. יוצרים מפתח API ב-https://console.anthropic.com
2. ב-`.env`: `ANTHROPIC_API_KEY=...`
3. מפעילים מחדש את השרת.

המפתח נשאר בשרת בלבד. בלי מפתח, Snooze נותן הצעות בסיסיות מכללים קבועים, וכתוב שם שזה מצב בסיסי. יש מגבלה של 20 בקשות ביום לכל משתמשת (`TIMEFLOW_AI_DAILY_LIMIT`).

### מייל אמיתי (Gmail)
1. בחשבון Google: אבטחה ← אימות דו-שלבי ← **סיסמאות אפליקציה**. יוצרים סיסמה.
2. ב-`.env`:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=465
   SMTP_USER=your.name@gmail.com
   SMTP_PASSWORD=הסיסמה-של-האפליקציה
   ```

בלי SMTP, המיילים (אימות כתובת, איפוס סיסמה, סיכום יומי) נשמרים כקבצי `.eml` בתיקייה `instance/outbox`, ואפשר לפתוח אותם ב-Outlook או בדפדפן. האתר כותב זאת בגלוי.
אם יש לך `mail_config.json` מגרסה 1, הוא עדיין נקרא.

### Google Calendar
1. ב-[Google Cloud Console](https://console.cloud.google.com/): יוצרים פרויקט, מפעילים **Google Calendar API**.
2. OAuth consent screen: סוג External, ומוסיפים את עצמך כ-Test user.
3. Credentials ← Create OAuth client ID ← **Web application**.
   Authorized redirect URI: `http://127.0.0.1:5000/zehava/calendar/oauth/callback`
4. ב-`.env`: `GOOGLE_CLIENT_ID=...` ו-`GOOGLE_CLIENT_SECRET=...`

ההרשאה היא קריאה בלבד (`calendar.events.readonly`). האתר מציג "מסונכרן" רק אחרי סנכרון שהצליח באמת.

### סיכום יומי כשהאתר סגור (Task Scheduler)
כשהשרת רץ, הסיכום נשלח ממנו בשעה שנבחרה בהגדרות. כדי לשלוח גם כשהוא כבוי:
1. ב-`.env`: `TIMEFLOW_SCHEDULER=off`
2. Task Scheduler ← Create Basic Task ← Daily, וחזרה כל 15 דקות.
3. Action: Start a program
   - Program: `C:\Users\zehav\OneDrive\Desktop\i\python\adhd-time-manager\.venv\Scripts\flask.exe`
   - Arguments: `--app app send-daily`
   - Start in: `C:\Users\zehav\OneDrive\Desktop\i\python\adhd-time-manager`

כל סיכום נשלח פעם אחת ביום בלבד, גם אם הפקודה רצה הרבה פעמים.

---

## מבנה הפרויקט

```
app.py                  השלד של Pretech + שורה אחת: timeflow.init_app(app)
timeflow/               כל הקוד של TimeFlow (פירוט ב-docs/ARCHITECTURE.md)
  views/                הנתיבים, קובץ לכל אזור
  personalization_engine.py   מנוע ההתאמה האישית (Python טהור)
templates/zehava/       התבניות
static/                 CSS, התמונות והצלילים
tests/                  150 בדיקות
tools/make_sounds.py    יוצר את קובצי הצליל מחישוב מתמטי (בלי זכויות של אחרים)
docs/                   ארכיטקטורה, פרטיות, תוצאות בדיקות, רשימת תכונות, צילומי מסך
v1-original/            הקוד של גרסה 1 כמו שהיה, לפני השדרוג
```

## מסמכים

- [PROJECT_AUDIT.md](PROJECT_AUDIT.md): סקירת גרסה 1 לפני השדרוג, כולל באגים וסיכונים
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md): התוכנית וההחלטות הטכנולוגיות
- [CHANGELOG.md](CHANGELOG.md): מה השתנה, שלב אחר שלב
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): איך הקוד בנוי, ואיך עובד מנוע ההתאמה האישית
- [docs/PRIVACY.md](docs/PRIVACY.md): אילו נתונים נשמרים, כמה זמן, ומה אפשר למחוק
- [docs/FEATURES.md](docs/FEATURES.md): מה עובד, ומה צריך מפתח כדי לעבוד
- [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md): תוצאות הבדיקות

## הערה

TimeFlow הוא כלי עזר לארגון זמן. הוא לא מאבחן, לא מטפל ולא מחליף ייעוץ מקצועי.

הפרויקט נבנה בעזרת Claude (Anthropic) ככלי עזר לכתיבת קוד, לבדיקות ולתיעוד.
