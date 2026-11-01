-- גרסה 4: מצב תצוגה "לפי השעה".
-- רק עמודה חדשה. ערכת הצבעים הקיימת (theme) נשארת כמו שהיא, וכל אחת ממשיכה לראות בדיוק מה שראתה.
-- 1 = האתר בהיר בבוקר ובצהריים וכהה בערב ובלילה, לפי שעון ישראל. לפני ההרצה db.migrate שומר גיבוי.
ALTER TABLE user_settings ADD COLUMN theme_by_clock INTEGER NOT NULL DEFAULT 0 CHECK (theme_by_clock IN (0, 1));
