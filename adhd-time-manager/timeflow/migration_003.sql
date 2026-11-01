-- גרסה 3: פרופיל אישי. שם בעברית ובאנגלית, יום הולדת, תמונה או אווטאר, ומשאלות יום הולדת.
-- רק מוסיפים עמודות וטבלאות. שום דבר לא נמחק, והשם הקיים (display_name) נשאר.
ALTER TABLE users ADD COLUMN first_name_he TEXT CHECK (first_name_he IS NULL OR length(first_name_he) <= 40);
ALTER TABLE users ADD COLUMN first_name_en TEXT CHECK (first_name_en IS NULL OR length(first_name_en) <= 40);
ALTER TABLE users ADD COLUMN last_name_he TEXT CHECK (last_name_he IS NULL OR length(last_name_he) <= 40);
ALTER TABLE users ADD COLUMN last_name_en TEXT CHECK (last_name_en IS NULL OR length(last_name_en) <= 40);
ALTER TABLE users ADD COLUMN birthday TEXT CHECK (birthday IS NULL OR birthday GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]');
ALTER TABLE users ADD COLUMN avatar TEXT NOT NULL DEFAULT 'letter'
    CHECK (avatar IN ('letter', 'photo', 'curls', 'long', 'bun', 'short', 'balloon', 'mountain'));

-- השם הקיים עובר לשפה שבה הוא כתוב: עם אותיות עבריות לעברית, אחרת לאנגלית
UPDATE users SET first_name_he = display_name WHERE display_name GLOB '*[א-ת]*';
UPDATE users SET first_name_en = display_name WHERE first_name_he IS NULL;

-- תמונת פרופיל: נשמרת במסד עצמו, מוקטנת ל-256x256 ובלי נתוני מיקום (EXIF)
CREATE TABLE IF NOT EXISTS avatar_photos (
    user_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    data       BLOB    NOT NULL,
    updated_at TEXT    NOT NULL
);

-- משאלה אחת לכל יום הולדת (אפשר לעדכן אותה באותה שנה)
CREATE TABLE IF NOT EXISTS birthday_wishes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    year       INTEGER NOT NULL,
    body       TEXT    NOT NULL CHECK (length(body) BETWEEN 1 AND 300),
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL,
    UNIQUE (user_id, year)
);
