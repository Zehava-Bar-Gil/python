"""הטקסטים של האתר: כל טקסט קיים בעברית ובאנגלית, באותו מבנה ועם אותם מקומות למילוי."""
import re
import unittest

from timeflow.texts import TEXTS, Addr

HEBREW = re.compile("[֐-׿]")
SLOT = re.compile(r"\{[a-z_]*\}")


def strings(value):
    # כל המחרוזות שבתוך ערך: מחרוזת, רשימה, זוג או מילון
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):        # כולל Addr: כל שלוש הצורות נבדקות
        value = list(value.values())
    if isinstance(value, (list, tuple)):
        return [text for item in value for text in strings(item)]
    return []


class TextsTests(unittest.TestCase):
    he, en = TEXTS["he"], TEXTS["en"]

    def test_same_keys_in_both_languages(self):
        self.assertEqual(set(self.he), set(self.en))

    def test_same_shape_and_slots(self):
        for key in self.he:
            with self.subTest(key=key):
                he_type = str if isinstance(self.he[key], Addr) else type(self.he[key])
                self.assertIs(he_type, type(self.en[key]))
                he_slots = sorted({s for text in strings(self.he[key]) for s in SLOT.findall(text)})
                en_slots = sorted({s for text in strings(self.en[key]) for s in SLOT.findall(text)})
                self.assertEqual(he_slots, en_slots)

    def test_english_has_no_hebrew(self):
        # היוצא מן הכלל: הכפתור שמחליף לעברית כתוב בעברית
        for key, value in self.en.items():
            if key == "switch":
                continue
            for text in strings(value):
                self.assertIsNone(HEBREW.search(text), f"{key}: {text}")

    def test_hebrew_speaks_to_everyone(self):
        # טקסט רגיל בעברית מתאים לכולם. פנייה בלשון נקבה או זכר מותרת רק בתוך Addr, עם שלוש צורות
        for key, value in self.he.items():
            if isinstance(value, Addr):
                continue
            for text in strings(value):
                self.assertNotRegex(text, r"(?<![\u0590-\u05FF])(תרצי|תוכלי|בחרי|לחצי|כתבי|תרצה|תוכל|היכנסי|שימי)(?![\u0590-\u05FF])", key)
