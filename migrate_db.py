"""Startup Sandbox - Database Migration Script

این فایل برای اجرای روی دیتابیس‌های قدیمی/جدید طراحی شده است.
هدف: جلوگیری از خطاهای رایج (جدول/ستون وجود ندارد) در محیط‌هایی مثل Render/Replit.

نکته:
- این اسکریپت idempotent است (اجرای چندباره بدون مشکل).
- به جای وابستگی به جدول game_logs، فقط logs را به عنوان جدول لاگ اصلی در نظر می‌گیرد.
"""

import os
import sqlite3
import sys
from datetime import datetime

# Fix encoding for Windows console
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


def migrate_database(db_path: str = "startup.db") -> bool:
    """به‌روزرسانی دیتابیس به ساختار جدید.

    - اگر فایل DB وجود نداشت، ساخته می‌شود.
    - جداول اصلی با CREATE TABLE IF NOT EXISTS ایجاد می‌شوند.
    - ستون‌های جدید با ALTER TABLE فقط در صورت نبودن اضافه می‌شوند.
    - هرگز روی table/column ناموجود باعث کرش نمی‌شود.
    """

    # اگر DB وجود ندارد، بساز (برای محیط‌های fresh)
    if not os.path.exists(db_path):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.close()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    def table_exists(table: str) -> bool:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        return cursor.fetchone() is not None

    def cols(table: str) -> set[str]:
        cursor.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cursor.fetchall()}

    def add_col(table: str, col: str, col_def: str) -> None:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
        except sqlite3.OperationalError as e:
            # اگر ستون از قبل وجود داشت، نادیده بگیر
            if "duplicate column name" in str(e).lower():
                return
            raise

    try:
        print("=" * 50)
        print("[INFO] در حال به روزرساني ديتابيس...")
        print("=" * 50)

        # -------------------------
        # Core tables (safe create)
        # -------------------------
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                name TEXT,
                idea TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                startup_name TEXT,
                budget INTEGER DEFAULT 1000,
                reputation INTEGER DEFAULT 50,
                morale INTEGER DEFAULT 80,
                turn INTEGER DEFAULT 1,
                score INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER,
                scenario_type TEXT DEFAULT 'normal',
                title TEXT,
                description TEXT,
                difficulty_level TEXT DEFAULT 'medium',
                turn_number INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS choices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id INTEGER,
                text TEXT,
                cost_impact INTEGER DEFAULT 0,
                reputation_impact INTEGER DEFAULT 0,
                morale_impact INTEGER DEFAULT 0,
                risk_level TEXT DEFAULT 'medium'
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                turn INTEGER NOT NULL,
                scenario_id INTEGER,
                scenario_title TEXT,
                choice_id INTEGER,
                choice_text TEXT,
                cost_impact INTEGER DEFAULT 0,
                reputation_impact INTEGER DEFAULT 0,
                morale_impact INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.commit()

        # -------------------------
        # Column upgrades (idempotent)
        # -------------------------
        if table_exists("users"):
            u = cols("users")
            if "username" not in u:
                add_col("users", "username", "TEXT")
            if "name" not in u:
                add_col("users", "name", "TEXT")
            if "idea" not in u:
                add_col("users", "idea", "TEXT")
            if "created_at" not in u:
                add_col("users", "created_at", "TEXT")

        if table_exists("games"):
            g = cols("games")
            if "startup_name" not in g:
                add_col("games", "startup_name", "TEXT")
            if "updated_at" not in g:
                add_col("games", "updated_at", "TEXT")
                now = datetime.now().isoformat()
                cursor.execute("UPDATE games SET updated_at = ? WHERE updated_at IS NULL", (now,))

        if table_exists("scenarios"):
            s = cols("scenarios")
            if "game_id" not in s:
                add_col("scenarios", "game_id", "INTEGER")
            if "scenario_type" not in s:
                add_col("scenarios", "scenario_type", "TEXT DEFAULT 'normal'")
            if "difficulty_level" not in s:
                add_col("scenarios", "difficulty_level", "TEXT DEFAULT 'medium'")
            if "turn_number" not in s:
                add_col("scenarios", "turn_number", "INTEGER DEFAULT 1")

        if table_exists("choices"):
            c = cols("choices")
            if "risk_level" not in c:
                add_col("choices", "risk_level", "TEXT DEFAULT 'medium'")

        if table_exists("logs"):
            l = cols("logs")
            # برای سازگاری با نسخه‌های قدیمی‌تر
            if "scenario_id" not in l:
                add_col("logs", "scenario_id", "INTEGER")
            if "scenario_title" not in l:
                add_col("logs", "scenario_title", "TEXT")
            if "choice_id" not in l:
                add_col("logs", "choice_id", "INTEGER")
            if "choice_text" not in l:
                add_col("logs", "choice_text", "TEXT")
            if "cost_impact" not in l:
                add_col("logs", "cost_impact", "INTEGER DEFAULT 0")
            if "reputation_impact" not in l:
                add_col("logs", "reputation_impact", "INTEGER DEFAULT 0")
            if "morale_impact" not in l:
                add_col("logs", "morale_impact", "INTEGER DEFAULT 0")
            if "created_at" not in l:
                add_col("logs", "created_at", "TEXT")

        # -------------------------
        # Indexes (safe)
        # -------------------------
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scenarios_game_id ON scenarios(game_id)")
        except Exception:
            pass
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_choices_scenario_id ON choices(scenario_id)")
        except Exception:
            pass
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_game_id ON logs(game_id)")
        except Exception:
            pass

        conn.commit()
        print("[OK] ديتابيس با موفقيت به روزرساني شد!")
        return True

    except Exception as e:
        print(f"[WARNING] مهاجرت با خطا مواجه شد (برنامه ادامه می‌دهد): {e}")
        conn.rollback()
        # در محیط‌های سرویس، ترجیح می‌دهیم کرش نکنیم
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()
