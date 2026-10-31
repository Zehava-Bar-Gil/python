"""חיבור למסד הנתונים SQLite, יצירת הטבלאות, גרסאות סכמה וגיבוי."""
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import current_app, g

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
# כל מיגרציה מקבלת מספר. גרסה 1 היא הסכמה המלאה. שינויים עתידיים יתווספו כ-2, 3...
MIGRATIONS = {1: SCHEMA_FILE}
LATEST_VERSION = max(MIGRATIONS)


def connect(path):
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    # חיבור אחד לכל בקשה, נסגר בסוף הבקשה
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def current_version(conn):
    try:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
    except sqlite3.OperationalError:
        return 0
    return row["version"] if row else 0


def migrate(path, backup_dir):
    # יוצר את המסד אם אינו קיים, ומעדכן לגרסה האחרונה. לפני עדכון של מסד קיים נשמר גיבוי
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    existed = Path(path).exists() and Path(path).stat().st_size > 0
    conn = connect(path)
    try:
        version = current_version(conn)
        if version >= LATEST_VERSION:
            return version
        if existed and version > 0:
            backup(path, backup_dir, label=f"before-v{LATEST_VERSION}")
        for number in range(version + 1, LATEST_VERSION + 1):
            conn.executescript(MIGRATIONS[number].read_text(encoding="utf-8"))
            conn.execute("DELETE FROM schema_version")
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (number,))
            conn.commit()
        return LATEST_VERSION
    finally:
        conn.close()


def backup(path, backup_dir, label="manual"):
    # גיבוי עקבי גם כשהאתר פועל, בעזרת backup API של SQLite
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"timeflow-{datetime.now():%Y%m%d-%H%M%S}-{label}.db"
    source = connect(path)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    return target


def restore(backup_file, path):
    # שחזור: מעתיק את קובץ הגיבוי במקום המסד הנוכחי (כשהשרת כבוי)
    source = sqlite3.connect(backup_file)
    dest = sqlite3.connect(path)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
