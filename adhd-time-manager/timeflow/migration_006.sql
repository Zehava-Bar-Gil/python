-- גרסה 6: זמן מסך. מודעות ולא חסימה: האתר לא רואה את הטלפון, ונשמר רק מה שהמשתמשת בחרה או רשמה.
-- רק טבלאות חדשות. שום דבר קיים לא משתנה. לפני ההרצה db.migrate שומר גיבוי.

-- יעד יומי לכל רשת. שורה קיימת = עוקבים אחרי הרשת הזאת
CREATE TABLE IF NOT EXISTS screen_limits (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    app        TEXT    NOT NULL,
    minutes    INTEGER NOT NULL CHECK (minutes BETWEEN 5 AND 600),
    updated_at TEXT    NOT NULL,
    PRIMARY KEY (user_id, app)
);

-- דקות בפועל ליום, כפי שנרשמו (למשל מזמן מסך באייפון). שורה אחת לכל רשת ביום
CREATE TABLE IF NOT EXISTS screen_log (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    app        TEXT    NOT NULL,
    day        TEXT    NOT NULL CHECK (day GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    minutes    INTEGER NOT NULL CHECK (minutes BETWEEN 0 AND 1440),
    updated_at TEXT    NOT NULL,
    PRIMARY KEY (user_id, app, day)
);

-- כל מעבר בשער הכוונה: למה, לכמה זמן, והאם בסוף נכנסו (opened = 0: בחרו לא להיכנס)
CREATE TABLE IF NOT EXISTS screen_visits (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    app        TEXT    NOT NULL,
    day        TEXT    NOT NULL CHECK (day GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    reason     TEXT,
    minutes    INTEGER CHECK (minutes IS NULL OR minutes BETWEEN 1 AND 120),
    note       TEXT    NOT NULL DEFAULT '' CHECK (length(note) <= 100),
    opened     INTEGER NOT NULL DEFAULT 1 CHECK (opened IN (0, 1)),
    created_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_screen_visits_user_day ON screen_visits (user_id, day);
