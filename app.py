"""
🚀 Startup Sandbox - Advanced Game Logic
شبیه‌ساز پیشرفته تصمیم‌گیری برای استارتاپ‌ها
"""

from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import json
import os
import requests
from google import genai


"""Startup Sandbox (Flask)

نکته مهم:
- مقادیر حساس (مثل GROQ_API_KEY) نباید داخل کد هاردکد شوند.
- اگر python-dotenv نصب نبود، برنامه باید بدون کرش بالا بیاید.
"""

# تلاش برای لود .env (اختیاری)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass
import random
from datetime import datetime

# اجرای مهاجرت دیتابیس در زمان اجرا (برای دیتابیس‌های قدیمی)
try:
    from migrate_db import migrate_database
except Exception:
    migrate_database = None


DB_PATH = os.getenv("STARTUP_DB_PATH", "startup.db")


def ensure_db():
    """Ensure DB file + schema exists (safe for fresh/free hosts like Replit/Render).

    ما هم جداول را می‌سازیم و هم اگر دیتابیس قدیمی بود، ستون‌های جدید را با ALTER اضافه می‌کنیم.
    """
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # --- base tables (CREATE) ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        name TEXT NOT NULL,
        idea TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
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
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS scenarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER NOT NULL,
        scenario_type TEXT DEFAULT 'crisis',
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        difficulty_level TEXT DEFAULT 'medium',
        turn_number INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS choices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scenario_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        cost_impact INTEGER DEFAULT 0,
        reputation_impact INTEGER DEFAULT 0,
        morale_impact INTEGER DEFAULT 0,
        risk_level TEXT DEFAULT 'medium'
    )
    """)

    cur.execute("""
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

    # --- schema upgrades (ALTER if missing) ---
    def _cols(table: str) -> set[str]:
        cur.execute(f"PRAGMA table_info({table})")
        return {r[1] for r in cur.fetchall()}

    # users: add columns if old schema
    ucols = _cols("users")
    if "username" not in ucols:
        cur.execute("ALTER TABLE users ADD COLUMN username TEXT")
    if "name" not in ucols:
        cur.execute("ALTER TABLE users ADD COLUMN name TEXT")
    if "idea" not in ucols:
        cur.execute("ALTER TABLE users ADD COLUMN idea TEXT")

    # games: add startup_name/updated_at if old schema
    gcols = _cols("games")
    if "startup_name" not in gcols:
        cur.execute("ALTER TABLE games ADD COLUMN startup_name TEXT")
    if "updated_at" not in gcols:
        cur.execute("ALTER TABLE games ADD COLUMN updated_at TEXT DEFAULT CURRENT_TIMESTAMP")

    # scenarios: add difficulty_level/turn_number if old schema
    scols = _cols("scenarios")
    if "difficulty_level" not in scols:
        cur.execute("ALTER TABLE scenarios ADD COLUMN difficulty_level TEXT DEFAULT 'medium'")
    if "turn_number" not in scols:
        cur.execute("ALTER TABLE scenarios ADD COLUMN turn_number INTEGER DEFAULT 1")

    # choices: add risk_level if old schema
    ccols = _cols("choices")
    if "risk_level" not in ccols:
        cur.execute("ALTER TABLE choices ADD COLUMN risk_level TEXT DEFAULT 'medium'")

    conn.commit()
    conn.close()


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")


# =========================
# AI Config (Gemini)
# =========================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()

client = None
_model_candidates: list[str] = []
_working_model: str | None = None
_ai_disabled_reason: str | None = None

if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Candidate models (اولویت با GEMINI_MODEL در env)
        if GEMINI_MODEL:
            _model_candidates.append(GEMINI_MODEL)

        _model_candidates += [
            # مدل‌های جدیدتر (ممکن است برای بعضی کلیدها/نسخه‌ها در دسترس نباشند)
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro",
            "gemini-1.5-pro-latest",
            # مدل‌های قدیمی‌تر/سازگارتر
            "gemini-1.0-pro",
            "gemini-pro",
        ]

        # حذف تکراری‌ها با حفظ ترتیب
        _seen = set()
        _model_candidates = [m for m in _model_candidates if not (m in _seen or _seen.add(m))]

    except Exception as e:
        client = None
        _ai_disabled_reason = f"init_failed: {e}"

# =========================
# Game Constants
# =========================
INITIAL_BUDGET = 1000
INITIAL_REPUTATION = 50
INITIAL_MORALE = 80

MIN_BUDGET = 0
MAX_BUDGET = 5000

MIN_REPUTATION = 0
MAX_REPUTATION = 100

MIN_MORALE = 0
MAX_MORALE = 100


# =========================
# Game Modes
# =========================
GAME_MODES = {
    "classic": {"budget": 1.0, "rep": 1.0, "morale": 1.0},
    "hard": {"budget": 1.2, "rep": 1.3, "morale": 1.1},
    "easy": {"budget": 0.8, "rep": 0.8, "morale": 0.8},
}


# ========== Database Functions ==========
_db_schema_initialized = False


def _ensure_db_schema() -> None:
    global _db_schema_initialized
    if _db_schema_initialized:
        return

    # ✅ کامل‌ترین مسیر: ensure_db (ساخت + ارتقا)
    try:
        ensure_db()
    except Exception as e:
        print(f"⚠️ خطا در ensure_db: {e}")

    # بعدش اگر migrate وجود داشت اجرا شود
    if migrate_database is None:
        _db_schema_initialized = True
        return

    try:
        migrate_database(DB_PATH)
        _db_schema_initialized = True
    except Exception as e:
        print(f"⚠️ خطا در migrate_database: {e}")
        _db_schema_initialized = True


def get_db_connection():
    _ensure_db_schema()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def clamp_stat(v: int, vmin: int, vmax: int) -> int:
    return max(vmin, min(vmax, v))


def call_ai_api(prompt: str, json_mode: bool = True, temperature: float = 0.7):
    """Call Gemini.

    - اگر کلید/کلاینت موجود نباشد => None
    - اگر مدل انتخابی پیدا نشود (404) => مدل‌های جایگزین را امتحان می‌کند
    - اگر خطای کلید/دسترسی باشد => برای جلوگیری از اسپم لاگ، AI غیرفعال می‌شود
    """
    global _working_model, _ai_disabled_reason

    if client is None or _ai_disabled_reason is not None:
        return None

    def _request(model_name: str) -> str:
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config={"temperature": temperature},
        )
        return (resp.text or "").strip()

    # اگر قبلاً یک مدل سالم پیدا کردیم، اول همون رو امتحان کن
    candidates: list[str] = []
    if _working_model:
        candidates.append(_working_model)
    else:
        candidates.extend(_model_candidates)

    last_err: Exception | None = None

    for mname in candidates:
        try:
            text = _request(mname)
            if text:
                _working_model = mname
                return text
            # اگر خروجی خالی بود، مدل بعدی
        except Exception as e:
            last_err = e
            msg = str(e)

            # مدل پیدا نشد => مدل بعدی
            if ("NOT_FOUND" in msg) or ("not found" in msg.lower()) or ("404" in msg):
                continue

            # خطای کلید/مجوز => دیگر تلاش نکن تا لاگ پر نشود
            if ("PERMISSION_DENIED" in msg) or ("invalid" in msg.lower()) or ("api key" in msg.lower()) or ("401" in msg):
                _ai_disabled_reason = msg
                break

            # سایر خطاها => همان یک بار fallback
            break

    if last_err:
        print(f"❌ خطا در اتصال به Gemini: {last_err}")
    return None

def get_scenario_type_weights(turn_number, budget, reputation, morale):
    weights = {
        "CRISIS": 3,
        "OPPORTUNITY": 2,
        "NORMAL": 3,
        "DILEMMA": 2,
        "EXTREME_CRISIS": 1
    }
    if budget < 300:
        weights["CRISIS"] += 2
    if reputation > 75:
        weights["OPPORTUNITY"] += 2
    if morale < 40:
        weights["CRISIS"] += 1
    if turn_number > 10:
        weights["EXTREME_CRISIS"] += 1
    return weights


# ========== Scenario Generation ==========
def generate_dynamic_scenario(game_id, startup_name, turn_number, current_budget, current_reputation, current_morale):
    """تولید سناریوی پویا و چالشی با AI"""
    conn = get_db_connection()

    try:
        # دریافت تاریخچه سناریوهای قبلی (از logs)
        previous_logs = conn.execute('''
            SELECT scenario_title 
            FROM logs 
            WHERE game_id = ? 
            ORDER BY turn DESC, id DESC 
            LIMIT 5
        ''', (game_id,)).fetchall()

        previous_titles = ", ".join([row['scenario_title'] for row in previous_logs if 'scenario_title' in row.keys()])
    except Exception:
        previous_titles = ""

    scenario_types = ["CRISIS", "OPPORTUNITY", "NORMAL", "DILEMMA", "EXTREME_CRISIS"]
    weights = get_scenario_type_weights(turn_number, current_budget, current_reputation, current_morale)
    selected_type = random.choices(scenario_types, weights=[weights[t] for t in scenario_types])[0]

    difficulty = "medium"
    if selected_type in ["CRISIS", "EXTREME_CRISIS"]:
        difficulty = "hard"
    elif selected_type == "OPPORTUNITY":
        difficulty = "easy"

    prompt = f"""
تو یک طراح بازی شبیه‌ساز مدیریت استارتاپ هستی. برای یک استارتاپ با مشخصات زیر یک سناریوی جدید بساز.

نام استارتاپ: {startup_name}
نوبت: {turn_number}
بودجه: {current_budget}
شهرت: {current_reputation}
روحیه تیم: {current_morale}

نوع سناریو: {selected_type}

سناریوهای قبلی (برای جلوگیری از تکرار): {previous_titles}

خروجی را فقط در قالب JSON بده با این ساختار:
{{
  "title": "...",
  "description": "...",
  "options": [
    {{"text": "...", "cost_impact": -100, "reputation_impact": 5, "morale_impact": -3, "risk_level": "low"}},
    {{"text": "...", "cost_impact": 200, "reputation_impact": -2, "morale_impact": 4, "risk_level": "high"}},
    {{"text": "...", "cost_impact": 0, "reputation_impact": 1, "morale_impact": 0, "risk_level": "medium"}}
  ]
}}
"""

    raw = call_ai_api(prompt, json_mode=True, temperature=0.7)

    # fallback JSON
    if not raw:
        print("⚠️ استفاده از سناریوی fallback")
        raw = json.dumps({
            "title": "بحران تأمین مواد",
            "description": "یکی از تأمین‌کنندگان اصلی شما اعلام کرده قیمت‌ها افزایش یافته و تحویل با تأخیر انجام می‌شود.",
            "options": [
                {"text": "مواد اولیه گران‌تر بخر", "cost_impact": -150, "reputation_impact": 5, "morale_impact": -2, "risk_level": "low"},
                {"text": "کیفیت را کاهش بده", "cost_impact": 50, "reputation_impact": -10, "morale_impact": -5, "risk_level": "high"},
                {"text": "تأمین‌کننده جدید پیدا کن", "cost_impact": -50, "reputation_impact": 2, "morale_impact": 3, "risk_level": "medium"}
            ]
        }, ensure_ascii=False)

    try:
        scenario_data = json.loads(raw)
    except Exception:
        # اگر مدل چیز اضافه نوشته بود
        try:
            # تلاش برای پیدا کردن اولین { ... }
            start = raw.find("{")
            end = raw.rfind("}")
            scenario_data = json.loads(raw[start:end+1])
        except Exception:
            scenario_data = {
                "title": "سناریو اضطراری",
                "description": "یک وضعیت غیرمنتظره رخ داده و باید سریع تصمیم بگیرید.",
                "options": [
                    {"text": "حالت محافظه‌کارانه", "cost_impact": -50, "reputation_impact": 1, "morale_impact": 0, "risk_level": "low"},
                    {"text": "ریسک بالا برای رشد", "cost_impact": -200, "reputation_impact": 5, "morale_impact": -2, "risk_level": "high"},
                    {"text": "راه‌حل میانه", "cost_impact": -100, "reputation_impact": 2, "morale_impact": 1, "risk_level": "medium"}
                ]
            }

    # validate
    if not scenario_data.get("title") or not scenario_data.get("description"):
        scenario_data["title"] = scenario_data.get("title") or "سناریو"
        scenario_data["description"] = scenario_data.get("description") or "توضیحی برای این سناریو موجود نیست."

    if len(scenario_data.get("options", [])) < 3:
        # تکمیل گزینه‌ها
        while len(scenario_data["options"]) < 3:
            scenario_data["options"].append(
                {"text": "گزینه جایگزین", "cost_impact": 0, "reputation_impact": 0, "morale_impact": 0, "risk_level": "medium"}
            )

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO scenarios (game_id, scenario_type, title, description, difficulty_level, turn_number)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (game_id, selected_type.lower(), scenario_data["title"], scenario_data["description"], difficulty, turn_number))
    scenario_id = cursor.lastrowid

    for opt in scenario_data["options"][:3]:
        cursor.execute("""
            INSERT INTO choices (scenario_id, text, cost_impact, reputation_impact, morale_impact, risk_level)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            scenario_id,
            opt.get("text", "گزینه"),
            int(opt.get("cost_impact", 0)),
            int(opt.get("reputation_impact", 0)),
            int(opt.get("morale_impact", 0)),
            opt.get("risk_level", "medium")
        ))

    conn.commit()
    conn.close()


# =========================
# Routes
# =========================
@app.route("/mode", methods=["GET", "POST"])
def mode():
    # اگر بازی هنوز ساخته نشده، برگرد به صفحه اصلی
    if "game_id" not in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        session["mode"] = request.form.get("mode", "classic")
        return redirect(url_for("game"))

    return render_template("mode.html")@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route('/new_game', methods=['POST'])
def new_game():
    """شروع بازی جدید (سازگار با اسکیماهای مختلف دیتابیس)"""
    username = (request.form.get('username') or '').strip()          # نام مدیرعامل
    startup_name = (request.form.get('startup_name') or '').strip()  # نام استارتاپ
    idea = (request.form.get('idea') or '').strip()

    if not username or not startup_name or not idea:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # ستون‌های جدول users را بخوان تا با اسکیماهای مختلف سازگار باشیم
        cursor.execute("PRAGMA table_info(users)")
        ucols = {row[1] for row in cursor.fetchall()}

        # کاربر موجود؟
        if "username" in ucols:
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        else:
            cursor.execute('SELECT id FROM users WHERE name = ?', (username,))
        user = cursor.fetchone()

        if user:
            user_id = user['id']
        else:
            fields = []
            params = []

            # بعضی DBها name/idea NOT NULL دارند
            if "name" in ucols:
                fields.append("name")
                params.append(username)
            if "idea" in ucols:
                fields.append("idea")
                params.append(idea)
            if "username" in ucols:
                fields.append("username")
                params.append(username)

            if not fields:
                raise RuntimeError("users table has no usable columns")

            sql = f"INSERT INTO users ({', '.join(fields)}) VALUES ({', '.join(['?']*len(fields))})"
            cursor.execute(sql, tuple(params))
            user_id = cursor.lastrowid

        # جدول games ممکن است startup_name داشته باشد یا نه
        cursor.execute("PRAGMA table_info(games)")
        gcols = {row[1] for row in cursor.fetchall()}

        if "startup_name" in gcols:
            cursor.execute('''
                INSERT INTO games (user_id, startup_name, budget, reputation, morale, turn) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, startup_name, INITIAL_BUDGET, INITIAL_REPUTATION, INITIAL_MORALE, 1))
        else:
            cursor.execute('''
                INSERT INTO games (user_id, budget, reputation, morale, turn) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, INITIAL_BUDGET, INITIAL_REPUTATION, INITIAL_MORALE, 1))

        game_id = cursor.lastrowid
        conn.commit()

        # ✅ اطلاعات کلیدی را در session نگه می‌داریم تا به ستون‌های DB وابسته نباشیم
        session['game_id'] = game_id
        session['startup_name'] = startup_name
        session['username'] = username
        session['idea'] = idea

        # تولید اولین سناریو
        generate_dynamic_scenario(
            game_id, startup_name, 1,
            INITIAL_BUDGET, INITIAL_REPUTATION, INITIAL_MORALE
        )

        return redirect(url_for('mode'))

    except Exception as e:
        print(f"❌ خطا در ایجاد بازی: {e}")
        conn.rollback()
        return redirect(url_for('index'))
    finally:
        conn.close()


@app.route('/game')
def game():
    """صفحه اصلی بازی"""
    if 'game_id' not in session:
        return redirect(url_for('index'))

    game_id = session['game_id']
    conn = get_db_connection()

    try:
        game = conn.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()

        if not game:
            return redirect(url_for('index'))

        scenario = conn.execute('''
            SELECT * FROM scenarios 
            WHERE game_id = ? 
            ORDER BY id DESC 
            LIMIT 1
        ''', (game_id,)).fetchone()

        # اگر سناریو وجود ندارد، ایجاد کن
        if not scenario:
            generate_dynamic_scenario(
                game_id,
                (session.get('startup_name') or (game['startup_name'] if hasattr(game, 'keys') and 'startup_name' in game.keys() else 'Startup')),
                game['turn'],
                game['budget'], game['reputation'], game['morale']
            )
            scenario = conn.execute('''
                SELECT * FROM scenarios 
                WHERE game_id = ? 
                ORDER BY id DESC 
                LIMIT 1
            ''', (game_id,)).fetchone()

        choices = conn.execute('SELECT * FROM choices WHERE scenario_id = ?', (scenario['id'],)).fetchall()

        conn.close()
        return render_template('game.html', game=game, scenario=scenario, choices=choices)

    except Exception as e:
        print(f"❌ خطا در بازی: {e}")
        conn.close()
        return redirect(url_for('index'))


@app.route('/action', methods=['POST'])
def action():
    """پردازش تصمیم کاربر"""
    if 'game_id' not in session:
        return redirect(url_for('index'))

    game_id = session['game_id']
    choice_id = request.form.get('choice_id')

    if not choice_id:
        return redirect(url_for('game'))

    conn = get_db_connection()

    try:
        # دریافت اطلاعات
        choice = conn.execute('SELECT * FROM choices WHERE id = ?', (choice_id,)).fetchone()
        if not choice:
            return redirect(url_for('game'))

        scenario = conn.execute('SELECT * FROM scenarios WHERE id = ?', (choice['scenario_id'],)).fetchone()
        game = conn.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()

        # برای سازگاری با دیتابیس‌هایی که ستون startup_name ندارند
        startup_name = session.get('startup_name')
        if not startup_name:
            try:
                startup_name = game['startup_name']
            except Exception:
                startup_name = 'Startup'

        # --- Phase B: apply mode multipliers ---
        mode_key = session.get("mode", "classic")
        mult = GAME_MODES.get(mode_key, GAME_MODES["classic"])

        cost_impact = int(round(choice["cost_impact"] * mult["budget"]))
        rep_impact = int(round(choice["reputation_impact"] * mult["rep"]))
        morale_impact = int(round(choice["morale_impact"] * mult["morale"]))

        new_budget = clamp_stat(game['budget'] + cost_impact, MIN_BUDGET, MAX_BUDGET)
        new_reputation = clamp_stat(game['reputation'] + rep_impact, MIN_REPUTATION, MAX_REPUTATION)
        new_morale = clamp_stat(game['morale'] + morale_impact, MIN_MORALE, MAX_MORALE)

        new_turn = game['turn'] + 1

        budget_before = game['budget']
        reputation_before = game['reputation']
        morale_before = game['morale']

        # به‌روزرسانی بازی
        conn.execute('''
            UPDATE games 
            SET budget = ?, reputation = ?, morale = ?, turn = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (new_budget, new_reputation, new_morale, new_turn, game_id))

        # تولید داستان نتیجه با AI
        prompt_story = f"""تو راوی یک بازی شبیه‌ساز استارتاپ هستی. یک داستان کوتاه، جذاب و واقع‌گرایانه بنویس.

**وضعیت:**
- استارتاپ: {startup_name}
- چالش: {scenario['title']}
- تصمیم کاربر: {choice['text']}

**تأثیرات:**
- بودجه: {budget_before}$ → {new_budget}$ ({cost_impact:+d}$)
- شهرت: {reputation_before}% → {new_reputation}% ({rep_impact:+d}%)
- روحیه: {morale_before}% → {new_morale}% ({morale_impact:+d}%) 

**دستورالعمل:**
- داستان باید 2-4 خط باشد
- واقع‌گرایانه و قابل باور باشد
- اگر تأثیرات منفی است، توضیح بده چرا
- اگر تأثیرات مثبت است، نشان بده چطور موفق شد
- از طنز و لحن جذاب استفاده کن
- به فارسی و طبیعی بنویس

**فقط داستان را بنویس، بدون توضیح اضافی:**"""

        ai_story = call_ai_api(prompt_story, json_mode=False, temperature=0.9)
        if not ai_story:
            ai_story = f"تصمیم شما اعمال شد. بودجه: {new_budget}$, شهرت: {new_reputation}%, روحیه: {new_morale}%"

        # ذخیره لاگ (logs)
        conn.execute("""
        INSERT INTO logs (game_id, turn, scenario_id, scenario_title, choice_id, choice_text,
                          cost_impact, reputation_impact, morale_impact)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            game_id,
            game["turn"],  # نوبت قبل از افزایش (بعد از UPDATE هنوز در row قدیمی است)
            scenario["id"],
            scenario["title"],
            choice["id"],
            choice["text"],
            cost_impact,
            rep_impact,
            morale_impact
        ))
        conn.commit()

        # به‌روزرسانی بازی برای نمایش
        game = conn.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
        conn.close()

        return render_template('result.html', story=ai_story, game=game, choice=choice)

    except Exception as e:
        print(f"❌ خطا در پردازش تصمیم: {e}")
        conn.rollback()
        conn.close()
        return redirect(url_for('game'))


@app.route('/next_turn')
def next_turn():
    """تولید سناریوی جدید برای نوبت بعدی"""
    if 'game_id' not in session:
        return redirect(url_for('index'))

    game_id = session['game_id']
    conn = get_db_connection()

    try:
        game = conn.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()

        # برای سازگاری با دیتابیس‌هایی که ستون startup_name ندارند
        startup_name = session.get('startup_name')
        if not startup_name:
            try:
                startup_name = game['startup_name']
            except Exception:
                startup_name = 'Startup'

        if not game:
            return redirect(url_for('index'))

        # تولید سناریوی جدید
        generate_dynamic_scenario(
            game_id,
            (session.get('startup_name') or (game['startup_name'] if hasattr(game, 'keys') and 'startup_name' in game.keys() else 'Startup')),
            game['turn'],
            game['budget'], game['reputation'], game['morale']
        )

        conn.close()
        return redirect(url_for('game'))

    except Exception as e:
        print(f"❌ خطا در نوبت بعدی: {e}")
        conn.close()
        return redirect(url_for('game'))


@app.route("/report/<int:game_id>")
def report(game_id):
    conn = get_db_connection()
    game = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if not game:
        conn.close()
        return redirect(url_for("index"))

    # Timeline از logs (اگر ستون‌ها دقیق نبود، fallback نرم)
    try:
        rows = conn.execute(
            "SELECT * FROM logs WHERE game_id = ? ORDER BY id ASC",
            (game_id,)
        ).fetchall()
    except Exception:
        rows = []

    timeline = []
    rep_series = []
    morale_series = []
    budget_series = []

    turn = 0
    for r in rows[-10:]:
        turn += 1
        scenario_title = r["scenario_title"] if "scenario_title" in r.keys() else "سناریو"
        choice_text = r["choice_text"] if "choice_text" in r.keys() else ("انتخاب")
        db = r["budget_impact"] if "budget_impact" in r.keys() else (r["cost_impact"] if "cost_impact" in r.keys() else 0)
        dr = r["reputation_impact"] if "reputation_impact" in r.keys() else 0
        dm = r["morale_impact"] if "morale_impact" in r.keys() else 0

        timeline.append({
            "turn": r["turn"] if "turn" in r.keys() else turn,
            "scenario_title": scenario_title,
            "choice_text": choice_text,
            "budget_delta": db,
            "rep_delta": dr,
            "morale_delta": dm
        })

    conn.close()
    return render_template("report.html", game=game, timeline=timeline)


if __name__ == "__main__":
    ensure_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
