"""
Startup Sandbox - Database Migration Script
Update old database to new structure
"""

import sqlite3
import os
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def migrate_database(db_path: str = 'startup.db'):
    """به‌روزرسانی دیتابیس به ساختار جدید.

    این اسکریپت به‌صورت idempotent طراحی شده تا هم روی دیتابیس‌های قدیمی
    و هم دیتابیس‌های جدید بدون خطا اجرا شود.
    """
    
    if not os.path.exists(db_path):
        print("[ERROR] فايل ديتابيس يافت نشد. لطفا ابتدا db_setup.py را اجرا كنيد.")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=" * 50)
    print("[INFO] در حال به روزرساني ديتابيس...")
    print("=" * 50)
    
    try:
        # اطمینان از وجود جدول‌های اصلی (در صورت دیتابیس خیلی قدیمی)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cursor.fetchone() is None:
            # اگر حتی جدول users وجود ندارد، از db_setup استفاده کنید.
            print("[ERROR] ساختار دیتابیس بسیار قدیمی/خالی است. لطفاً ابتدا db_setup.py را اجرا کنید.")
            return False

        # بررسی وجود فیلد game_id در scenarios
        cursor.execute("PRAGMA table_info(scenarios)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'game_id' not in columns:
            print("[+] اضافه کردن فيلد game_id به جدول scenarios...")
            cursor.execute("ALTER TABLE scenarios ADD COLUMN game_id INTEGER")
            cursor.execute("ALTER TABLE scenarios ADD COLUMN scenario_type TEXT DEFAULT 'NORMAL'")
            cursor.execute("ALTER TABLE scenarios ADD COLUMN difficulty_level INTEGER DEFAULT 1")
            cursor.execute("ALTER TABLE scenarios ADD COLUMN turn_number INTEGER")
            print("[OK] فيلدهاي جديد اضافه شدند.")
        else:
            print("[INFO] فيلد game_id از قبل وجود دارد.")
        
        # بررسی وجود فیلد risk_level در choices
        cursor.execute("PRAGMA table_info(choices)")
        choice_columns = [row[1] for row in cursor.fetchall()]
        
        if 'risk_level' not in choice_columns:
            print("[+] اضافه کردن فيلد risk_level به جدول choices...")
            cursor.execute("ALTER TABLE choices ADD COLUMN risk_level INTEGER DEFAULT 3")
            print("[OK] فيلد risk_level اضافه شد.")
        else:
            print("[INFO] فيلد risk_level از قبل وجود دارد.")
        
        # بررسی وجود فیلدهای جدید در game_logs
        cursor.execute("PRAGMA table_info(game_logs)")
        log_columns = [row[1] for row in cursor.fetchall()]
        
        new_log_fields = {
            'scenario_id': 'INTEGER',
            'scenario_type': 'TEXT',
            'choice_id': 'INTEGER',
            'budget_before': 'INTEGER',
            'reputation_before': 'INTEGER',
            'morale_before': 'INTEGER',
            'budget_after': 'INTEGER',
            'reputation_after': 'INTEGER',
            'morale_after': 'INTEGER'
        }
        
        for field_name, field_type in new_log_fields.items():
            if field_name not in log_columns:
                print(f"[+] اضافه کردن فيلد {field_name} به جدول game_logs...")
                cursor.execute(f"ALTER TABLE game_logs ADD COLUMN {field_name} {field_type}")
                print(f"[OK] فيلد {field_name} اضافه شد.")
        
        # بررسی وجود فیلدهای جدید در games
        cursor.execute("PRAGMA table_info(games)")
        game_columns = [row[1] for row in cursor.fetchall()]
        
        if 'game_over_reason' not in game_columns:
            print("[+] اضافه کردن فيلد game_over_reason به جدول games...")
            cursor.execute("ALTER TABLE games ADD COLUMN game_over_reason TEXT")
            print("[OK] فيلد game_over_reason اضافه شد.")
        
        if 'updated_at' not in game_columns:
            print("[+] اضافه کردن فيلد updated_at به جدول games...")
            cursor.execute("ALTER TABLE games ADD COLUMN updated_at TIMESTAMP")
            # Set default value for existing rows
            from datetime import datetime
            now = datetime.now().isoformat()
            cursor.execute("UPDATE games SET updated_at = ? WHERE updated_at IS NULL", (now,))
            print("[OK] فيلد updated_at اضافه شد.")

        # اطمینان از وجود جدول game_statistics (برای تحلیل)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='game_statistics'")
        if cursor.fetchone() is None:
            print("[+] ايجاد جدول game_statistics...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    total_turns INTEGER DEFAULT 0,
                    total_crises INTEGER DEFAULT 0,
                    total_opportunities INTEGER DEFAULT 0,
                    avg_budget INTEGER DEFAULT 0,
                    avg_reputation INTEGER DEFAULT 0,
                    avg_morale INTEGER DEFAULT 0,
                    FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE
                )
            ''')
            print("[OK] جدول game_statistics ايجاد شد.")



            conn.execute("""
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
            """)
        conn.commit()


        # (این بلوک عمداً فقط یک بار اجرا می‌شود)
        
        # ایجاد ایندکس‌های جدید
        print("\n[+] در حال ايجاد ايندكسهاي جديد...")
        indexes = [
            ('idx_games_game_over', 'games', 'is_game_over'),
            ('idx_scenarios_game_id', 'scenarios', 'game_id'),
            ('idx_scenarios_type', 'scenarios', 'scenario_type'),
            ('idx_logs_scenario_type', 'game_logs', 'scenario_type'),
            ('idx_logs_game_id', 'game_logs', 'game_id'),
        ]
        
        for idx_name, table, column in indexes:
            try:
                cursor.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})')
                print(f"[OK] ايندكس {idx_name} ايجاد شد.")
            except Exception as e:
                print(f"[WARNING] خطا در ايجاد ايندكس {idx_name}: {e}")
        
        # به‌روزرسانی سناریوهای قدیمی (اگر game_id ندارند)
        cursor.execute("SELECT COUNT(*) FROM scenarios WHERE game_id IS NULL")
        null_count = cursor.fetchone()[0]
        
        if null_count > 0:
            print(f"\n[WARNING] {null_count} سناريو بدون game_id يافت شد.")
            print("[INFO] اين سناريوها به عنوان fallback استفاده مي شوند.")
        
        # به‌روزرسانی scenario_type برای سناریوهای قدیمی
        cursor.execute("UPDATE scenarios SET scenario_type = 'NORMAL' WHERE scenario_type IS NULL")
        
        # به‌روزرسانی risk_level برای choices قدیمی
        cursor.execute("UPDATE choices SET risk_level = 3 WHERE risk_level IS NULL")
        
        conn.commit()
        print("\n" + "=" * 50)
        print("[OK] ديتابيس با موفقيت به روزرساني شد!")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"\n[ERROR] خطا در به روزرساني ديتابيس: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
