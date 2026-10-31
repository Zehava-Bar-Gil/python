# חיבור TimeFlow ל-Google Calendar

הקוד כבר קיים ב-`adhd-time-manager-v2.zip`: `timeflow/google_calendar.py`. ההרשאה היא קריאה בלבד (`calendar.events.readonly`).
נשאר רק ליצור מפתחות ב-Google ולשים אותם בקובץ `.env`. זה לוקח כ-15 דקות, ואין צורך לשנות קוד.

**הצעד הראשון:** לפתוח את https://console.cloud.google.com ולהתחבר עם חשבון ה-Gmail שלך.

---

## שלב 1 מתוך 4: פרויקט ו-API (3 דק')

1. למעלה משמאל, בבורר הפרויקטים: **New Project**. שם: `TimeFlow`. לוחצים **Create** ובוחרים בפרויקט.
2. בתפריט: **APIs & Services ← Library**. מחפשים `Google Calendar API` ולוחצים **Enable**.

## שלב 2 מתוך 4: מסך ההסכמה (5 דק')

1. בתפריט: **Google Auth Platform** (בממשק הישן: **OAuth consent screen**). לוחצים **Get started**.
2. ממלאים: App name `TimeFlow`, ובשדה User support email את הכתובת שלך.
3. בשדה Audience בוחרים **External**. אחר כך ממלאים את כתובת המייל שלך ב-Contact, ולוחצים **Create**.
4. בלשונית **Audience**, תחת **Test users**, לוחצים **Add users** ומוסיפים את כתובת ה-Gmail שלך.
   האפליקציה תישאר במצב Testing, וזה מספיק לפרויקט.

## שלב 3 מתוך 4: מפתחות (4 דק')

1. בלשונית **Clients** לוחצים **Create client**.
2. Application type: **Web application**. Name: `TimeFlow local`.
3. תחת **Authorized redirect URIs** לוחצים **Add URI** ומדביקים בדיוק את הכתובת הזו:
   ```
   http://127.0.0.1:5000/zehava/calendar/oauth/callback
   ```
4. לוחצים **Create**, ומעתיקים את **Client ID** ואת **Client secret**.

## שלב 4 מתוך 4: לחבר באתר (3 דק')

1. בתיקיית הפרויקט ב-VS Code: מעתיקים את `.env.example` לקובץ חדש בשם `.env`.
2. בקובץ `.env` מורידים את ה-`#` משתי השורות האלה וממלאים אותן:
   ```
   GOOGLE_CLIENT_ID=המזהה-שהעתקת.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=הסוד-שהעתקת
   ```
3. בטרמינל מריצים `python app.py`.
4. פותחים את האתר בכתובת **http://127.0.0.1:5000** ולא ב-localhost, כי הכתובת צריכה להתאים בדיוק ל-Redirect URI.
5. בלשונית **Google Calendar** לוחצים "חיבור", ומאשרים ב-Google.
   אם מופיע המסך "Google hasn't verified this app", לוחצים **Continue**. זה תקין כשהאפליקציה במצב Testing.
6. בסוף צריך להופיע "מסונכרן" עם שעה, והאירועים שלך יופיעו בלוח החודשי.

**סיימת!** הבדיקה: יוצרים אירוע ב-Google Calendar, לוחצים "סנכרון" באתר, והאירוע מופיע.

---

## אם משהו לא עובד

| מה רואים | הסיבה | התיקון |
|---|---|---|
| `redirect_uri_mismatch` | הכתובת לא זהה | בודקים שפתחת את 127.0.0.1 ולא localhost, ושה-URI בשלב 3 הועתק בדיוק |
| `access_denied` / "Access blocked" | החשבון לא ברשימת Test users | חוזרים לשלב 2, סעיף 4 |
| "לא הוגדר" באתר | הקובץ `.env` לא נקרא | בודקים שהשם הוא בדיוק `.env`, שהוא בתיקייה של `app.py`, ושהשרת הופעל מחדש |
| אחרי שבוע: "צריך חידוש" | במצב Testing, Google מבטל את ההרשאה אחרי 7 ימים | לוחצים שוב "חיבור". זה תקין |

## חשוב לפני GitHub

`.env` מכיל את הסוד, ולכן **אסור להעלות אותו**. הוא כבר מופיע ב-`.gitignore`. לפני `git add` כדאי להריץ `git status` ולוודא ש-`.env` לא ברשימה.
