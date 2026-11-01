"""תמונת פרופיל: בדיקה, הקטנה ושמירה כ-JPEG נקי.

כל תמונה נפתחת ונשמרת מחדש עם Pillow. כך נשמרים רק הפיקסלים: בלי נתוני מיקום (EXIF),
ובלי שום תוכן אחר שמישהו הסתיר בתוך הקובץ.
"""
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD = 3 * 1024 * 1024          # עד 3MB, כמו תמונה רגילה מהטלפון
SIZE = 256                            # התמונה נשמרת ריבועית, 256x256
FORMATS = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = 40_000_000   # הגנה מקובץ ענק שמתחזה לתמונה קטנה


def process(file_storage):
    """מחזיר (bytes, None) כשהתמונה תקינה, או (None, מפתח הודעה) כשלא."""
    raw = file_storage.read(MAX_UPLOAD + 1)
    if not raw:
        return None, "photo_missing"
    if len(raw) > MAX_UPLOAD:
        return None, "photo_too_big"
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.format not in FORMATS:
                return None, "photo_bad_type"
            image = ImageOps.exif_transpose(image)          # תמונה מהטלפון עומדת ישר
            image = ImageOps.fit(image.convert("RGB"), (SIZE, SIZE))
            out = BytesIO()
            image.save(out, "JPEG", quality=86)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return None, "photo_bad_type"
    return out.getvalue(), None
