-- גרסה 2 (שלב 5): זמן משוער למשימה, והצמדת פתק חשוב.
-- רק מוסיפים עמודות. שום טבלה לא נמחקת, וכל המשימות והפתקים הקיימים נשארים כמו שהם
-- (זמן משוער ריק, ואף פתק לא מוצמד). לפני ההרצה db.migrate שומר גיבוי של המסד.
ALTER TABLE tasks ADD COLUMN estimate_minutes INTEGER CHECK (estimate_minutes IS NULL OR estimate_minutes BETWEEN 1 AND 180);
ALTER TABLE notes ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1));
