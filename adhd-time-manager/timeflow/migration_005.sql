-- גרסה 5: איך האתר פונה בעברית.
-- f = בלשון נקבה, m = בלשון זכר, x = לא מוגדר (צורה כוללת, כמו את.ה).
-- כל מי שכבר רשומה מתחילה ב-x, ואפשר לשנות בהגדרות. לפני ההרצה db.migrate שומר גיבוי.
ALTER TABLE user_settings ADD COLUMN address TEXT NOT NULL DEFAULT 'x' CHECK (address IN ('f', 'm', 'x'));
