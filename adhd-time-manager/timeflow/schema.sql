-- TimeFlow: סכמת מסד הנתונים (גרסה 1)
-- לכל טבלה של נתונים אישיים יש user_id, והיא נמחקת יחד עם המשתמשת (ON DELETE CASCADE).
-- כל הזמנים נשמרים כמחרוזות ISO ב-UTC. תאריכים בלבד נשמרים כ-YYYY-MM-DD לפי שעון ישראל.

CREATE TABLE IF NOT EXISTS users (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    email             TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    display_name      TEXT    NOT NULL CHECK (length(display_name) BETWEEN 1 AND 40),
    password_hash     TEXT    NOT NULL,
    email_verified_at TEXT,
    created_at        TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id             INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    lang                TEXT    NOT NULL DEFAULT 'he'    CHECK (lang IN ('he', 'en')),
    theme               TEXT    NOT NULL DEFAULT 'auto'  CHECK (theme IN ('auto', 'light', 'dark')),
    reduce_motion       INTEGER NOT NULL DEFAULT 0       CHECK (reduce_motion IN (0, 1)),
    sound_pref          TEXT    NOT NULL DEFAULT 'ask'   CHECK (sound_pref IN ('ask', 'none', 'deep', 'calm', 'study', 'reading')),
    timer_chime         INTEGER NOT NULL DEFAULT 0       CHECK (timer_chime IN (0, 1)),
    focus_minutes       INTEGER NOT NULL DEFAULT 25      CHECK (focus_minutes BETWEEN 2 AND 120),
    short_break_minutes INTEGER NOT NULL DEFAULT 5       CHECK (short_break_minutes BETWEEN 1 AND 30),
    long_break_minutes  INTEGER NOT NULL DEFAULT 15      CHECK (long_break_minutes BETWEEN 5 AND 60),
    notifications       TEXT    NOT NULL DEFAULT 'quiet' CHECK (notifications IN ('off', 'quiet', 'normal')),
    calm_mode           INTEGER NOT NULL DEFAULT 0       CHECK (calm_mode IN (0, 1)),
    pulse_enabled       INTEGER NOT NULL DEFAULT 1       CHECK (pulse_enabled IN (0, 1)),
    learning_enabled    INTEGER NOT NULL DEFAULT 0       CHECK (learning_enabled IN (0, 1)),
    learning_consent_at TEXT,
    ai_enabled          INTEGER NOT NULL DEFAULT 1       CHECK (ai_enabled IN (0, 1)),
    daily_email         INTEGER NOT NULL DEFAULT 0       CHECK (daily_email IN (0, 1)),
    daily_email_at      TEXT    NOT NULL DEFAULT '21:00',
    goal_text           TEXT    NOT NULL DEFAULT ''      CHECK (length(goal_text) <= 60),
    updated_at          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title         TEXT    NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    details       TEXT    NOT NULL DEFAULT '' CHECK (length(details) <= 1000),
    tag           TEXT    NOT NULL DEFAULT '',
    priority      TEXT    NOT NULL DEFAULT 'normal' CHECK (priority IN ('later', 'normal', 'important')),
    due_date      TEXT,
    due_time      TEXT,
    status        TEXT    NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
    started_at    TEXT,
    completed_at  TEXT,
    snooze_count  INTEGER NOT NULL DEFAULT 0,
    source        TEXT    NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'note', 'snooze', 'ai', 'calendar')),
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id, status);

CREATE TABLE IF NOT EXISTS task_steps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
    done_at     TEXT,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_steps_task ON task_steps(task_id);

CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body        TEXT    NOT NULL CHECK (length(body) BETWEEN 1 AND 500),
    color       TEXT    NOT NULL DEFAULT 'yellow' CHECK (color IN ('yellow', 'pink', 'green', 'blue')),
    tag         TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(user_id);

-- סשן מיקוד או הפסקה. planned_seconds = 0 הוא מצב גמיש (סופר קדימה)
CREATE TABLE IF NOT EXISTS focus_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id         INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    kind            TEXT    NOT NULL DEFAULT 'focus' CHECK (kind IN ('focus', 'short_break', 'long_break')),
    planned_seconds INTEGER NOT NULL CHECK (planned_seconds >= 0),
    started_at      TEXT    NOT NULL,
    paused_at       TEXT,
    paused_seconds  INTEGER NOT NULL DEFAULT 0,
    ended_at        TEXT,
    actual_seconds  INTEGER,
    status          TEXT    NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'paused', 'completed', 'stopped')),
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);
-- אי אפשר להריץ שני טיימרים במקביל: רק סשן פעיל אחד לכל משתמשת
CREATE UNIQUE INDEX IF NOT EXISTS one_active_session ON focus_sessions(user_id) WHERE status IN ('running', 'paused');
CREATE INDEX IF NOT EXISTS idx_sessions_user ON focus_sessions(user_id, started_at);

-- מסע הכדור הפורח: כל פריט נספר פעם אחת בלבד
CREATE TABLE IF NOT EXISTS journey_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind        TEXT    NOT NULL CHECK (kind IN ('task', 'step', 'session')),
    ref_id      INTEGER NOT NULL,
    points      INTEGER NOT NULL CHECK (points > 0),
    created_at  TEXT    NOT NULL,
    UNIQUE (user_id, kind, ref_id)
);

CREATE TABLE IF NOT EXISTS journey_state (
    user_id      INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    shown_points INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS daily_pulse (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day         TEXT    NOT NULL,
    rating      INTEGER CHECK (rating BETWEEN 1 AND 5),
    reasons     TEXT    NOT NULL DEFAULT '',
    skipped     INTEGER NOT NULL DEFAULT 0 CHECK (skipped IN (0, 1)),
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    UNIQUE (user_id, day)
);

-- תובנות שהוצגו ומה המשתמשת בחרה לעשות איתן
CREATE TABLE IF NOT EXISTS insights (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rule_id     TEXT    NOT NULL,
    evidence    TEXT    NOT NULL DEFAULT '{}',
    status      TEXT    NOT NULL CHECK (status IN ('accepted', 'dismissed', 'corrected')),
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_insights_user ON insights(user_id, rule_id);

CREATE TABLE IF NOT EXISTS sound_feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    space       TEXT    NOT NULL CHECK (space IN ('deep', 'calm', 'study', 'reading')),
    helped      INTEGER NOT NULL CHECK (helped IN (0, 1)),
    created_at  TEXT    NOT NULL
);

-- Snooze: מחשבות שנפרקו. bucket = לאן מיינו אותן
CREATE TABLE IF NOT EXISTS snooze_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body        TEXT    NOT NULL CHECK (length(body) BETWEEN 1 AND 1000),
    bucket      TEXT    NOT NULL DEFAULT 'unsorted' CHECK (bucket IN ('unsorted', 'action', 'later', 'let_go')),
    task_id     INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    ai_reply    TEXT,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snooze_user ON snooze_entries(user_id);

-- רישום בקשות AI לצורך הגבלת שימוש. התוכן עצמו לא נשמר כאן
CREATE TABLE IF NOT EXISTS ai_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose     TEXT    NOT NULL CHECK (purpose IN ('unload', 'start_help')),
    provider    TEXT    NOT NULL,
    status      TEXT    NOT NULL CHECK (status IN ('ok', 'error', 'refused', 'limited', 'offline')),
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_user ON ai_requests(user_id, created_at);

-- יומן המיילים. הסיכום היומי ייחודי למשתמשת וליום, וכך לא יישלח פעמיים
CREATE TABLE IF NOT EXISTS email_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    kind        TEXT    NOT NULL CHECK (kind IN ('daily', 'verify', 'reset', 'manual')),
    day         TEXT,
    status      TEXT    NOT NULL CHECK (status IN ('sending', 'sent', 'failed')),
    attempts    INTEGER NOT NULL DEFAULT 1,
    error       TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_daily_email ON email_log(user_id, day) WHERE kind = 'daily';

CREATE TABLE IF NOT EXISTS login_attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT    NOT NULL,
    ip          TEXT    NOT NULL,
    success     INTEGER NOT NULL CHECK (success IN (0, 1)),
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_login_attempts ON login_attempts(created_at);

-- Google Calendar. האסימונים נשמרים רק בשרת ולא נשלחים לדפדפן
CREATE TABLE IF NOT EXISTS google_accounts (
    user_id        INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    access_token   TEXT    NOT NULL,
    refresh_token  TEXT,
    expires_at     TEXT    NOT NULL,
    scope          TEXT    NOT NULL,
    connected_at   TEXT    NOT NULL,
    last_sync_at   TEXT,
    last_error     TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    google_id   TEXT    NOT NULL,
    summary     TEXT    NOT NULL DEFAULT '',
    starts_at   TEXT    NOT NULL,
    ends_at     TEXT,
    all_day     INTEGER NOT NULL DEFAULT 0,
    task_id     INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    updated_at  TEXT    NOT NULL,
    UNIQUE (user_id, google_id)
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
