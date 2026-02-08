"""
🚀 Startup Sandbox - Database Setup
ساختار دیتابیس بهینه و تمیز برای شبیه‌ساز استارتاپ
"""

import sqlite3
from datetime import datetime

def create_database(db_path: str = 'startup.db'):
    """ساخت و بهینه‌سازی دیتابیس با ساختار کامل.

    نکته: برای تست و دیپلوی، مسیر دیتابیس باید قابل تنظیم باشد.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=" * 50)
    print("🚀 در حال ساخت دیتابیس Startup Sandbox...")
    print("=" * 50)

    # ۱. جدول کاربران
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total_games INTEGER DEFAULT 0,
        best_score INTEGER DEFAULT 0
    )
    ''')

    # ۲. جدول بازی‌ها (وضعیت فعلی هر بازی)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        startup_name TEXT NOT NULL,
        budget INTEGER DEFAULT 1000,
        reputation INTEGER DEFAULT 50,
        morale INTEGER DEFAULT 80,
        turn INTEGER DEFAULT 1,
        is_game_over BOOLEAN DEFAULT 0,
        game_over_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    ''')

    # ۳. جدول سناریوها (اتفاقات بازی)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scenarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER,
        scenario_type TEXT NOT NULL CHECK(scenario_type IN ('CRISIS', 'OPPORTUNITY', 'NORMAL', 'DILEMMA', 'EXTREME_CRISIS')),
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        difficulty_level INTEGER DEFAULT 1 CHECK(difficulty_level BETWEEN 1 AND 5),
        turn_number INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE
    )
    ''')

    # ۴. جدول انتخاب‌ها (گزینه‌های هر سناریو)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS choices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scenario_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        cost_impact INTEGER DEFAULT 0,
        reputation_impact INTEGER DEFAULT 0,
        morale_impact INTEGER DEFAULT 0,
        risk_level INTEGER DEFAULT 1 CHECK(risk_level BETWEEN 1 AND 5),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (scenario_id) REFERENCES scenarios (id) ON DELETE CASCADE
    )
    ''')

    # ۵. جدول لاگ‌ها (تاریخچه بازی و پاسخ‌های هوش مصنوعی)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS game_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER NOT NULL,
        turn_number INTEGER NOT NULL,
        scenario_id INTEGER,
        scenario_title TEXT,
        scenario_type TEXT,
        user_choice TEXT,
        choice_id INTEGER,
        budget_before INTEGER,
        reputation_before INTEGER,
        morale_before INTEGER,
        budget_after INTEGER,
        reputation_after INTEGER,
        morale_after INTEGER,
        ai_response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE,
        FOREIGN KEY (scenario_id) REFERENCES scenarios (id) ON DELETE SET NULL,
        FOREIGN KEY (choice_id) REFERENCES choices (id) ON DELETE SET NULL
    )
    ''')

    # ۶. جدول آمار بازی (برای تحلیل)
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
    cursor.execute("""
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


    # ایجاد ایندکس‌ها برای بهبود عملکرد
    print("\n📊 در حال ایجاد ایندکس‌ها...")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_games_user_id ON games(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_games_game_over ON games(is_game_over)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_scenarios_game_id ON scenarios(game_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_scenarios_type ON scenarios(scenario_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_choices_scenario_id ON choices(scenario_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_game_id ON game_logs(game_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_turn ON game_logs(turn_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_scenario_type ON game_logs(scenario_type)')

    print("✅ جدول‌ها و ایندکس‌ها ساخته شدند.")
    
    # --- اضافه کردن داده‌های اولیه (Seed Data) ---
    print("\n📝 در حال بررسی داده‌های اولیه...")
    
    cursor.execute('SELECT count(*) FROM scenarios WHERE game_id IS NULL')
    if cursor.fetchone()[0] == 0:
        print("➕ اضافه کردن سناریوهای پایه برای fallback...")
        
        # سناریوهای پایه برای fallback
        base_scenarios = [
            {
                "title": "حمله سایبری!",
                "description": "سایت استارتاپ شما توسط هکرها قفل شده و آن‌ها درخواست ۵۰۰ دلار باج دارند. تیم فنی شما می‌گوید می‌تواند در ۲۴ ساعت مشکل را حل کند، اما در این مدت سایت شما آفلاین خواهد بود و مشتریان ناراضی می‌شوند.",
                "type": "CRISIS",
                "difficulty": 3,
                "choices": [
                    {"text": "پرداخت باج (۵۰۰ دلار)", "cost": -500, "rep": -15, "morale": -25, "risk": 3},
                    {"text": "مقاومت و بازیابی بکاپ (۱۰۰ دلار هزینه)", "cost": -100, "rep": +25, "morale": +15, "risk": 2},
                    {"text": "تماس با پلیس سایبری (رایگان، اما زمان‌بر)", "cost": 0, "rep": +10, "morale": -10, "risk": 4}
                ]
            },
            {
                "title": "پیشنهاد سرمایه‌گذار مشکوک",
                "description": "یک سرمایه‌گذار پیشنهاد ۳۰۰ دلار سرمایه در ازای ۴۰٪ سهام و تبلیغات مزاحم در سایت می‌دهد. این می‌تواند سریع پول بدهد اما کنترل شما را کم می‌کند و ممکن است مشتریان را ناراضی کند.",
                "type": "DILEMMA",
                "difficulty": 2,
                "choices": [
                    {"text": "قبول پیشنهاد (پول سریع)", "cost": +300, "rep": -35, "morale": -20, "risk": 4},
                    {"text": "رد پیشنهاد و ادامه مستقل", "cost": 0, "rep": +15, "morale": +25, "risk": 2},
                    {"text": "مذاکره برای شرایط بهتر (۵۰٪ احتمال موفقیت)", "cost": +150, "rep": -10, "morale": +5, "risk": 3}
                ]
            },
            {
                "title": "استعفای کارمند کلیدی",
                "description": "یکی از اعضای مهم تیم شما استعفا داده و می‌خواهد فوراً برود. او روی پروژه‌های مهم کار می‌کرد و رفتنش می‌تواند تأثیر منفی روی روحیه تیم و کیفیت کار بگذارد.",
                "type": "CRISIS",
                "difficulty": 3,
                "choices": [
                    {"text": "پذیرش استعفا و استخدام فوری (هزینه‌بر)", "cost": -400, "rep": 0, "morale": -10, "risk": 3},
                    {"text": "تلاش برای نگه داشتن با افزایش حقوق", "cost": -200, "rep": +5, "morale": +10, "risk": 2},
                    {"text": "قبول استعفا و تقسیم کار بین اعضا (رایگان اما سخت)", "cost": 0, "rep": -5, "morale": -20, "risk": 4}
                ]
            }
        ]
        
        for scenario_data in base_scenarios:
            cursor.execute("""
                INSERT INTO scenarios (scenario_type, title, description, difficulty_level) 
                VALUES (?, ?, ?, ?)
            """, (scenario_data["type"], scenario_data["title"], scenario_data["description"], scenario_data["difficulty"]))
            scenario_id = cursor.lastrowid
            
            for choice_data in scenario_data["choices"]:
                cursor.execute("""
                    INSERT INTO choices (scenario_id, text, cost_impact, reputation_impact, morale_impact, risk_level) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    scenario_id,
                    choice_data["text"],
                    choice_data["cost"],
                    choice_data["rep"],
                    choice_data["morale"],
                    choice_data["risk"]
                ))

        print("✅ داده‌های اولیه اضافه شدند.")
    else:
        print("ℹ️ داده‌ها از قبل وجود دارند.")

    conn.commit()
    conn.close()
    print("\n" + "=" * 50)
    print(f"✅ دیتابیس {db_path} آماده است!")
    print("=" * 50)

if __name__ == "__main__":
    create_database()
