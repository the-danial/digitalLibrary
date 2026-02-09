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
# try:
#     from groq import Groq
# except Exception:  # برای محیط‌های تست/بدون groq
#     Groq = None

# اجرای مهاجرت دیتابیس در زمان اجرا (برای دیتابیس‌های قدیمی)
try:
    from migrate_db import migrate_database
except Exception:
    migrate_database = None



app = Flask(__name__)

# در محیط production باید از متغیر محیطی استفاده شود
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev_secret_key_change_me')

# 🔴 تنظیمات حیاتی (فقط از ENV)
# اگر کلید ست نشده باشد یا خالی باشد، AI غیرفعال است و سیستم روی fallback کار می‌کند.
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY", "gemini-3-flash-preview").strip() or None)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Client key را از env می‌گیرد اگر GEMINI_API_KEY ست باشد
gemini_client = genai.Client()

# OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
# OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "http://localhost:5000")
# OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "sandbox")
# (اختیاری) تنظیم پروکسی فقط اگر در ENV مشخص شده باشد
PROXY_URL = os.getenv('HTTP_PROXY') or os.getenv('HTTPS_PROXY') or None

# ----------new api----------

# def openrouter_chat(messages, temperature=0.3, max_tokens=700):
#     url = "https://openrouter.ai/api/v1/chat/completions"
#     headers = {
#         "Authorization": f"Bearer {GEMINI_API_KEY}",
#         "Content-Type": "application/json",

#         # Optional but recommended (app attribution)
#         "HTTP-Referer": OPENROUTER_SITE_URL,
#         "X-Title": OPENROUTER_APP_NAME,
#     }

#     payload = {
#         "model": OPENROUTER_MODEL,
#         "messages": messages,
#         "temperature": temperature,
#         "max_tokens": max_tokens,
#     }

#     r = requests.post(url, headers=headers, json=payload, timeout=45)
#     r.raise_for_status()
#     data = r.json()
#     return data["choices"][0]["message"]["content"]


# مسیر دیتابیس (برای تست و چند محیط)
DB_PATH = os.getenv('STARTUP_DB_PATH', 'startup.db')

# ========== Constants ==========

GAME_MODES = {
    "classic":  {"budget": 1.0,  "rep": 1.0,  "morale": 1.0},
    "crisis":   {"budget": 1.15, "rep": 1.10, "morale": 1.10},
    "investor": {"budget": 0.95, "rep": 1.25, "morale": 1.0},
    "bootstrap":{"budget": 1.30, "rep": 1.0,  "morale": 1.05},
}

MIN_BUDGET = 0
MIN_REPUTATION = 0
MIN_MORALE = 0
MAX_BUDGET = 10000
MAX_REPUTATION = 100
MAX_MORALE = 100

INITIAL_BUDGET = 1000
INITIAL_REPUTATION = 50
INITIAL_MORALE = 80

# ========== Database Functions ==========

_db_schema_initialized = False

def _ensure_db_schema() -> None:
    """اطمینان از سازگاری اسکیما برای دیتابیس‌های قدیمی.

    - اگر db_setup.py قبلاً اجرا شده باشد، این تابع فقط migrationهای سبک را اعمال می‌کند.
    - اگر migrate_db موجود نباشد، چیزی انجام نمی‌دهد.
    """
    # فقط یک بار در هر پروسس
    global _db_schema_initialized
    if _db_schema_initialized:
        return
    if migrate_database is None:
        return
    try:
        migrate_database(DB_PATH)
        _db_schema_initialized = True
    except Exception as e:
        # اجازه بده برنامه بالا بیاید؛ fallbackها در تولید سناریو کمک می‌کنند
        print(f"⚠️ خطا در migrate_database: {e}")


def get_db_connection():
    """ایجاد اتصال به دیتابیس با تنظیمات بهینه"""
    _ensure_db_schema()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # فعال‌سازی foreign keys
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

# ========== AI API Functions ==========
# def call_ai_api(prompt_text, json_mode=False, temperature=0.8):
#     """فراخوانی API Groq با مدیریت خطا"""
#     try:
#         if not OPENROUTER_API_KEY or OPENROUTER_API_KEY.strip() == "":
#             return None
#         client = openrouter_chat(prompt_text)
        
#         chat_completion = client.chat.completions.create(
#             messages=[{
#                 "role": "user",
#                 "content": prompt_text,
#             }],
#             model="llama-3.3-70b-versatile",
#             temperature=temperature,
#             response_format={"type": "json_object"} if json_mode else {"type": "text"},
#             max_tokens=1500 if json_mode else 500
#         )

#         return chat_completion.choices[0].message.content

#     except Exception as e:
#         print(f"❌ خطا در اتصال به Groq: {e}")
#         return None

def _extract_json_object(text: str) -> str | None:
    """اولین آبجکت JSON را از داخل متن بیرون می‌کشد."""
    if not text:
        return None
    s = text.strip()
    # اگر کل متن JSON است
    if s.startswith("{") and s.endswith("}"):
        return s
    # در غیر این صورت بین اولین { و آخرین } را بگیر
    a = s.find("{")
    b = s.rfind("}")
    if a != -1 and b != -1 and b > a:
        return s[a:b+1]
    return None


def call_ai_api(prompt_text: str, json_mode: bool = False, temperature: float = 0.3):
    """
    Gemini call (replaces Groq/OpenRouter).
    - json_mode=True => expects JSON-only output, validates it, otherwise returns None (so fallback works)
    """
    try:
        # اگر کلید ست نشده باشد، بگذار fallback کار کند
        if not os.getenv("GEMINI_API_KEY"):
            return None

        system_rules = (
            "تو یک راوی شبیه‌ساز مدیریت استارتاپ هستی. "
            "فقط و فقط فارسی بنویس و از هیچ زبان دیگری استفاده نکن. "
        )
        if json_mode:
            system_rules += "خروجی را فقط به صورت JSON معتبر برگردان و هیچ متن اضافه‌ای ننویس."

        # Gemini: contents را مثل یک متن ترکیبی می‌فرستیم (system + user)
        contents = f"{system_rules}\n\n{prompt_text}"

        resp = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents
        )

        text = getattr(resp, "text", None)
        if not text:
            return None

        if not json_mode:
            return text

        candidate = _extract_json_object(text)
        if not candidate:
            return None

        json.loads(candidate)  # validate
        return candidate

    except Exception as e:
        print(f"❌ خطا در اتصال به Gemini: {e}")
        return None


# ========== Game Logic Functions ==========
def check_game_over(game):
    """بررسی شرایط پایان بازی"""
    reasons = []
    
    if game['budget'] <= MIN_BUDGET:
        reasons.append("BUDGET")
    if game['reputation'] <= MIN_REPUTATION:
        reasons.append("REPUTATION")
    if game['morale'] <= MIN_MORALE:
        reasons.append("MORALE")
    
    return reasons if reasons else None

def clamp_stat(value, min_val, max_val):
    """محدود کردن مقدار آمار بین min و max"""
    return max(min_val, min(max_val, value))

def calculate_difficulty(turn_number, current_budget, current_reputation):
    """محاسبه سطح سختی بر اساس پیشرفت بازی"""
    base_difficulty = 1
    
    # افزایش سختی با پیشرفت بازی
    if turn_number > 10:
        base_difficulty = 3
    elif turn_number > 5:
        base_difficulty = 2
    
    # اگر وضعیت خوب است، چالش‌ها سخت‌تر می‌شوند
    if current_budget > 2000 and current_reputation > 70:
        base_difficulty += 1
    
    return min(base_difficulty, 5)

def get_scenario_type_weights(turn_number, current_budget, current_reputation, current_morale):
    """تعیین وزن انواع سناریو بر اساس وضعیت بازی"""
    # اگر بودجه کم است، فرصت‌ها بیشتر
    if current_budget < 300:
        return {"CRISIS": 3, "OPPORTUNITY": 5, "NORMAL": 2, "DILEMMA": 2, "EXTREME_CRISIS": 1}
    
    # اگر شهرت کم است، بحران‌ها بیشتر
    if current_reputation < 30:
        return {"CRISIS": 5, "OPPORTUNITY": 2, "NORMAL": 2, "DILEMMA": 3, "EXTREME_CRISIS": 2}
    
    # اگر روحیه کم است، بحران‌های شدید بیشتر
    if current_morale < 30:
        return {"CRISIS": 4, "OPPORTUNITY": 2, "NORMAL": 1, "DILEMMA": 3, "EXTREME_CRISIS": 4}
    
    # حالت عادی
    if turn_number < 5:
        return {"CRISIS": 3, "OPPORTUNITY": 4, "NORMAL": 3, "DILEMMA": 2, "EXTREME_CRISIS": 1}
    else:
        return {"CRISIS": 4, "OPPORTUNITY": 3, "NORMAL": 2, "DILEMMA": 3, "EXTREME_CRISIS": 2}

# ========== Scenario Generation ==========
def generate_dynamic_scenario(game_id, startup_name, turn_number, current_budget, current_reputation, current_morale):
    """تولید سناریوی پویا و چالشی با AI"""
    conn = get_db_connection()
    
    try:
        # دریافت تاریخچه سناریوهای قبلی
        previous_logs = conn.execute('''
            SELECT scenario_title, scenario_type 
            FROM logs 
            WHERE game_id = ? 
            ORDER BY turn_number DESC 
            LIMIT 5
        ''', (game_id,)).fetchall()
        
        previous_titles = ", ".join([f"{row['scenario_title']} ({row['scenario_type']})" for row in previous_logs])
    except:
        previous_titles = ""
    
    # تعیین نوع سناریو
    scenario_types = ["CRISIS", "OPPORTUNITY", "NORMAL", "DILEMMA", "EXTREME_CRISIS"]
    weights = get_scenario_type_weights(turn_number, current_budget, current_reputation, current_morale)
    weights_list = [weights.get(st, 1) for st in scenario_types]
    selected_type = random.choices(scenario_types, weights=weights_list, k=1)[0]
    
    difficulty = calculate_difficulty(turn_number, current_budget, current_reputation)
    
    # پرامپت پیشرفته و واقع‌گرایانه
    prompt_text = f"""تو یک متخصص کسب‌وکار و مشاور استارتاپ هستی که سناریوهای واقعی و چالشی برای شبیه‌ساز استارتاپ می‌سازی.

    تو یک راوی شبیه‌ساز مدیریت استارتاپ هستی. 
    فقط و فقط فارسی بنویس. از هیچ زبان دیگری استفاده نکن. 
    خروجی را فقط به صورت JSON معتبر برگردان و هیچ متن اضافی ننویس.

**مشخصات بازی:**
- نام استارتاپ: {startup_name}
- نوبت بازی: {turn_number}
- بودجه فعلی: {current_budget}$ (حداکثر: {MAX_BUDGET}$)
- شهرت فعلی: {current_reputation}% (حداکثر: {MAX_REPUTATION}%)
- روحیه تیم: {current_morale}% (حداکثر: {MAX_MORALE}%)
- سطح سختی: {difficulty}/5
- نوع سناریو: {selected_type}

**وضعیت فعلی:**
- بودجه: {'کم' if current_budget < 500 else 'متوسط' if current_budget < 2000 else 'خوب'}
- شهرت: {'بحرانی' if current_reputation < 20 else 'پایین' if current_reputation < 40 else 'متوسط' if current_reputation < 70 else 'عالی'}
- روحیه: {'بحرانی' if current_morale < 20 else 'پایین' if current_morale < 40 else 'متوسط' if current_morale < 70 else 'عالی'}

**سناریوهای قبلی (تکراری نساز):**
{previous_titles if previous_titles else "هیچ سناریوی قبلی وجود ندارد"}

**دستورالعمل‌های مهم:**

1. **واقع‌گرایی**: سناریو باید کاملاً واقعی و قابل باور باشد. از مشکلات واقعی استارتاپ‌ها استفاده کن:
   - مشکلات مالی (نقدینگی، پرداخت حقوق، هزینه‌های غیرمنتظره)
   - مشکلات تیم (استعفا، تعارض، خستگی)
   - مشکلات بازار (رقیب جدید، تغییر قوانین، بحران اقتصادی)
   - مشکلات فنی (باگ، خرابی سرور، امنیت)
   - مشکلات مشتری (شکایت، لغو اشتراک، بازخورد منفی)

2. **چالش‌گرایی**: سناریو باید چالشی و سخت باشد:
   - گزینه‌ها نباید واضح باشند (همه گزینه‌ها باید trade-off داشته باشند)
   - بعضی گزینه‌ها باید ریسک بالایی داشته باشند
   - سناریوهای {selected_type} باید واقعاً {selected_type} باشند

3. **تعادل**: 
   - همه گزینه‌ها نباید منفی باشند (حداقل یک گزینه باید قابل قبول باشد)
   - اما هیچ گزینه‌ای نباید کاملاً مثبت باشد (همه باید هزینه‌ای داشته باشند)

4. **تأثیرات واقع‌گرایانه**:
   - بودجه: بین -500 تا +1000 (بسته به نوع سناریو)
   - شهرت: بین -50 تا +30 (تغییرات شهرت کندتر است)
   - روحیه: بین -40 تا +25 (روحیه حساس‌تر است)

5. **نوع سناریو {selected_type}**:
   - CRISIS: بحران واقعی که معمولاً بودجه یا شهرت را کاهش می‌دهد
   - OPPORTUNITY: فرصت طلایی که می‌تواند درآمدزا باشد اما ریسک دارد
   - NORMAL: چالش روزمره با تأثیرات متوسط
   - DILEMMA: دوراهی اخلاقی یا استراتژیک پیچیده (همه گزینه‌ها هزینه دارند)
   - EXTREME_CRISIS: بحران شدید که می‌تواند بازی را تمام کند (تأثیرات بزرگ منفی)

6. **سطح سختی {difficulty}**: 
   - سطح 1-2: تأثیرات کوچک تا متوسط
   - سطح 3-4: تأثیرات متوسط تا بزرگ
   - سطح 5: تأثیرات بسیار بزرگ (می‌تواند باعث شکست شود)

**فرمت خروجی JSON (فقط JSON برگردان، بدون توضیح اضافی):**
{{
    "title": "عنوان کوتاه و جذاب (حداکثر 50 کاراکتر)",
    "description": "توضیح کامل و واقع‌گرایانه مشکل یا فرصت (2-4 خط، حداقل 100 کاراکتر)",
    "options": [
        {{
            "text": "گزینه اول - توضیح کوتاه و واضح",
            "cost": -200,
            "reputation": -15,
            "morale": -10,
            "risk_level": 3
        }},
        {{
            "text": "گزینه دوم - توضیح کوتاه و واضح",
            "cost": 300,
            "reputation": -25,
            "morale": -5,
            "risk_level": 4
        }},
        {{
            "text": "گزینه سوم - توضیح کوتاه و واضح",
            "cost": -50,
            "reputation": 10,
            "morale": 15,
            "risk_level": 2
        }}
    ]
}}

**مهم**: 
- حتماً 3 گزینه بده
- همه اعداد را به صورت عدد (نه رشته) بده
- risk_level بین 1 تا 5 باشد
- برای EXTREME_CRISIS، حداقل یک گزینه باید تأثیرات بسیار منفی داشته باشد (مثلاً -300 بودجه یا -30 شهرت)
- برای OPPORTUNITY، حداقل یک گزینه باید cost مثبت داشته باشد
- برای DILEMMA، همه گزینه‌ها باید trade-off داشته باشند (هیچ گزینه کاملاً مثبت نباشد)
"""
    
    # درخواست از AI
    raw_text = call_ai_api(prompt_text, json_mode=True, temperature=0.85)
    
    if raw_text:
        try:
            # پاک کردن markdown code blocks اگر وجود دارد
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()
            
            scenario_data = json.loads(raw_text)
            
            # اعتبارسنجی داده‌ها
            if not scenario_data.get('title') or not scenario_data.get('description'):
                raise ValueError("عنوان یا توضیحات خالی است")
            
            if len(scenario_data.get('options', [])) < 3:
                raise ValueError("حداقل 3 گزینه لازم است")
            
            # ذخیره در دیتابیس
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scenarios (game_id, scenario_type, title, description, difficulty_level, turn_number) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (game_id, selected_type, scenario_data['title'], scenario_data['description'], difficulty, turn_number))
            scenario_id = cursor.lastrowid
            
            for opt in scenario_data['options']:
                # محدود کردن مقادیر
                cost = clamp_stat(opt.get('cost', 0), -1000, 2000)
                reputation = clamp_stat(opt.get('reputation', 0), -50, 50)
                morale = clamp_stat(opt.get('morale', 0), -50, 50)
                risk = clamp_stat(opt.get('risk_level', 3), 1, 5)
                
                cursor.execute("""
                    INSERT INTO choices (scenario_id, text, cost_impact, reputation_impact, morale_impact, risk_level) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (scenario_id, opt['text'], cost, reputation, morale, risk))
            
            conn.commit()
            return scenario_id
            
        except json.JSONDecodeError as e:
            print(f"❌ خطای JSON: {e}")
            print(f"متن دریافتی: {raw_text[:200]}")
        except Exception as e:
            print(f"❌ خطا در پردازش سناریو: {e}")
        finally:
            # conn را نبندیم چون ممکن است fallback نیاز داشته باشد
            pass
    
    # Fallback: استفاده از سناریوی پیش‌فرض
    print("⚠️ استفاده از سناریوی fallback")
    # اطمینان از اینکه conn باز است
    try:
        if conn:
            conn.execute("SELECT 1")
    except:
        conn = get_db_connection()
    if not conn:
        conn = get_db_connection()
    scenario_id = create_fallback_scenario(conn, game_id, selected_type, difficulty, turn_number)
    conn.close()
    return scenario_id

def create_fallback_scenario(conn, game_id, scenario_type, difficulty, turn_number):
    """ایجاد سناریوی fallback در صورت خطای AI"""
    fallback_scenarios = {
        "CRISIS": {
            "title": "مشکل نقدینگی فوری",
            "description": "یک هزینه غیرمنتظره پیش آمده و شما باید فوراً تصمیم بگیرید. تیم شما منتظر حقوق است و مشتریان هم درخواست بازگشت وجه دارند.",
            "options": [
                {"text": "استقراض از دوستان (سریع اما شرم‌آور)", "cost": 200, "rep": -10, "morale": -15, "risk": 3},
                {"text": "تأخیر در پرداخت حقوق (صرفه‌جویی اما کاهش روحیه)", "cost": -300, "rep": -5, "morale": -25, "risk": 4},
                {"text": "فروش بخشی از سهام (پول زیاد اما از دست دادن کنترل)", "cost": 500, "rep": -20, "morale": -10, "risk": 5}
            ]
        },
        "EXTREME_CRISIS": {
            "title": "بحران اعتماد عمومی",
            "description": "یک خبر منفی درباره استارتاپ شما در رسانه‌ها منتشر شده و مشتریان در حال لغو اشتراک هستند. شهرت شما به شدت در خطر است.",
            "options": [
                {"text": "سکوت و انتظار (هیچ کاری نکن)", "cost": 0, "rep": -35, "morale": -30, "risk": 5},
                {"text": "عذرخواهی عمومی و جبران (هزینه‌بر اما مؤثر)", "cost": -400, "rep": 15, "morale": 10, "risk": 2},
                {"text": "مقابله و انکار (ریسکی اما ممکن است کار کند)", "cost": -100, "rep": -20, "morale": -15, "risk": 4}
            ]
        },
        "OPPORTUNITY": {
            "title": "فرصت همکاری استراتژیک",
            "description": "یک شرکت بزرگ پیشنهاد همکاری داده که می‌تواند درآمد خوبی داشته باشد، اما نیاز به سرمایه‌گذاری اولیه دارد.",
            "options": [
                {"text": "قبول همکاری (سرمایه‌گذاری 300 دلار)", "cost": -300, "rep": 20, "morale": 15, "risk": 3},
                {"text": "رد پیشنهاد (هیچ هزینه‌ای ندارد)", "cost": 0, "rep": -5, "morale": -5, "risk": 2},
                {"text": "مذاکره برای شرایط بهتر", "cost": -150, "rep": 10, "morale": 5, "risk": 4}
            ]
        },
        "DILEMMA": {
            "title": "دوراهی اخلاقی",
            "description": "شما باید بین منافع کوتاه‌مدت و ارزش‌های بلندمدت انتخاب کنید. هر تصمیمی هزینه‌ای دارد.",
            "options": [
                {"text": "انتخاب منافع کوتاه‌مدت", "cost": 200, "rep": -25, "morale": -20, "risk": 4},
                {"text": "پایبندی به ارزش‌ها", "cost": -200, "rep": 20, "morale": 25, "risk": 2},
                {"text": "جستجوی راه میانه", "cost": -50, "rep": 5, "morale": 10, "risk": 3}
            ]
        },
        "NORMAL": {
            "title": "چالش روزمره",
            "description": "یک مشکل معمولی پیش آمده که نیاز به تصمیم‌گیری دارد. نه خیلی بزرگ است و نه خیلی کوچک.",
            "options": [
                {"text": "راه حل سریع (هزینه‌بر)", "cost": -150, "rep": 5, "morale": 0, "risk": 2},
                {"text": "راه حل ارزان (زمان‌بر)", "cost": -50, "rep": 0, "morale": -5, "risk": 3},
                {"text": "انجام ندادن (هیچ هزینه‌ای ندارد)", "cost": 0, "rep": -10, "morale": -10, "risk": 4}
            ]
        }
    }
    
    scenario_data = fallback_scenarios.get(scenario_type, fallback_scenarios["CRISIS"])
    
    # بررسی وجود فیلد game_id
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(scenarios)")
        columns = [row[1] for row in cursor.fetchall()]
        has_game_id = 'game_id' in columns
        
        if has_game_id:
            cursor.execute("""
                INSERT INTO scenarios (game_id, scenario_type, title, description, difficulty_level, turn_number) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (game_id, scenario_type, scenario_data["title"], scenario_data["description"], difficulty, turn_number))
        else:
            # اگر فیلد game_id وجود ندارد، بدون آن insert کن
            cursor.execute("""
                INSERT INTO scenarios (scenario_type, title, description, difficulty_level) 
                VALUES (?, ?, ?, ?)
            """, (scenario_type, scenario_data["title"], scenario_data["description"], difficulty))
        
        scenario_id = cursor.lastrowid
        
        # بررسی وجود فیلد risk_level
        cursor.execute("PRAGMA table_info(choices)")
        choice_columns = [row[1] for row in cursor.fetchall()]
        has_risk_level = 'risk_level' in choice_columns
        
        for opt in scenario_data["options"]:
            if has_risk_level:
                cursor.execute("""
                    INSERT INTO choices (scenario_id, text, cost_impact, reputation_impact, morale_impact, risk_level) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (scenario_id, opt["text"], opt["cost"], opt["rep"], opt["morale"], opt["risk"]))
            else:
                cursor.execute("""
                    INSERT INTO choices (scenario_id, text, cost_impact, reputation_impact, morale_impact) 
                    VALUES (?, ?, ?, ?, ?)
                """, (scenario_id, opt["text"], opt["cost"], opt["rep"], opt["morale"]))
        
        conn.commit()
        return scenario_id
        
    except Exception as e:
        print(f"❌ خطا در ایجاد fallback scenario: {e}")
        conn.rollback()
        raise

# ========== Routes ==========
@app.route("/mode", methods=["GET", "POST"])
def mode():
    if "game_id" not in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        selected = request.form.get("mode", "classic")
        if selected not in GAME_MODES:
            selected = "classic"
        session["mode"] = selected
        return redirect(url_for("game"))

    return render_template("mode.html")



@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")



@app.route('/new_game', methods=['POST'])
def new_game():
    """شروع بازی جدید"""
    username = request.form.get('username', '').strip()
    startup_name = request.form.get('startup_name', '').strip()
    
    if not username or not startup_name:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # ایجاد یا به‌روزرسانی کاربر
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        if user:
            user_id = user['id']
        else:
            cursor.execute('INSERT INTO users (username) VALUES (?)', (username,))
            user_id = cursor.lastrowid
        
        # ایجاد بازی جدید
        cursor.execute('''
            INSERT INTO games (user_id, startup_name, budget, reputation, morale, turn) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, startup_name, INITIAL_BUDGET, INITIAL_REPUTATION, INITIAL_MORALE, 1))
        game_id = cursor.lastrowid
        
        conn.commit()
        session['game_id'] = game_id
        
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
        
        # بررسی شرایط پایان بازی
        game_over_reasons = check_game_over(game)
        if game_over_reasons:
            # به‌روزرسانی وضعیت بازی
            reason_text = ", ".join(game_over_reasons)
            conn.execute('''
                UPDATE games 
                SET is_game_over = 1, game_over_reason = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (reason_text, game_id))
            conn.commit()
            conn.close()
            return render_template('game_over.html', game=game, reasons=game_over_reasons)
        
        # دریافت سناریوی فعلی
        scenario = conn.execute('''
            SELECT * FROM scenarios 
            WHERE game_id = ? 
            ORDER BY id DESC 
            LIMIT 1
        ''', (game_id,)).fetchone()
        
        # اگر سناریو وجود ندارد، ایجاد کن
        if not scenario:
            generate_dynamic_scenario(
                game_id, game['startup_name'], game['turn'],
                game['budget'], game['reputation'], game['morale']
            )
            scenario = conn.execute('''
                SELECT * FROM scenarios 
                WHERE game_id = ? 
                ORDER BY id DESC 
                LIMIT 1
            ''', (game_id,)).fetchone()
        
        # دریافت گزینه‌ها
        choices = conn.execute('''
            SELECT * FROM choices 
            WHERE scenario_id = ? 
            ORDER BY id
        ''', (scenario['id'],)).fetchall()
        
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

        # --- Phase B: apply mode multipliers ---
        mode_key = session.get("mode", "classic")
        mult = GAME_MODES.get(mode_key, GAME_MODES["classic"])

        cost_impact = int(round(choice["cost_impact"] * mult["budget"]))
        rep_impact  = int(round(choice["reputation_impact"] * mult["rep"]))
        morale_impact = int(round(choice["morale_impact"] * mult["morale"]))


        new_budget = clamp_stat(game['budget'] + cost_impact, MIN_BUDGET, MAX_BUDGET)
        new_reputation = clamp_stat(game['reputation'] + rep_impact, MIN_REPUTATION, MAX_REPUTATION)
        new_morale = clamp_stat(game['morale'] + morale_impact, MIN_MORALE, MAX_MORALE)

        # محاسبه مقادیر جدید
        # new_budget = clamp_stat(game['budget'] + choice['cost_impact'], MIN_BUDGET, MAX_BUDGET)
        # new_reputation = clamp_stat(game['reputation'] + choice['reputation_impact'], MIN_REPUTATION, MAX_REPUTATION)
        # new_morale = clamp_stat(game['morale'] + choice['morale_impact'], MIN_MORALE, MAX_MORALE)
        
        new_turn = game['turn'] + 1

        

        
        # ذخیره مقادیر قبل از تغییر
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
- استارتاپ: {game['startup_name']}
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
        
        # ذخیره لاگ
        conn.execute('''
            INSERT INTO logs 
            (game_id, turn, scenario_id, scenario_title, user_choice, choice_id,
             budget_before, reputation_before, morale_before,
             budget_after, reputation_after, morale_after, ai_response)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            game_id, game['turn'], scenario['id'], scenario['title'], scenario['scenario_type'],
            choice['text'], choice_id,
            budget_before, reputation_before, morale_before,
            new_budget, new_reputation, new_morale, ai_story
        ))
        
        conn.commit()

        conn.execute("""
        INSERT INTO logs (game_id, turn, scenario_id, scenario_title, choice_id, choice_text,
                          cost_impact, reputation_impact, morale_impact)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            game_id,
            game["turn"],               # یا new_turn بسته به کدت
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
        
        if not game:
            return redirect(url_for('index'))
        
        # بررسی شرایط پایان بازی
        if check_game_over(game):
            conn.close()
            return redirect(url_for('game'))
        
        # تولید سناریوی جدید
        generate_dynamic_scenario(
            game_id, game['startup_name'], game['turn'],
            game['budget'], game['reputation'], game['morale']
        )
        
        conn.close()
        return redirect(url_for('game'))
        
    except Exception as e:
        print(f"❌ خطا در نوبت بعدی: {e}")
        conn.close()
        return redirect(url_for('game'))

def _pct_series(values, clamp_min=0, clamp_max=100):
    # values -> list[int]
    out = []
    for v in values:
        v2 = v
        if clamp_min is not None:
            v2 = max(clamp_min, v2)
        if clamp_max is not None:
            v2 = min(clamp_max, v2)
        pct = 0 if clamp_max == 0 else int(round((v2 - (clamp_min or 0)) / ((clamp_max - (clamp_min or 0)) or 1) * 100))
        out.append({"v": v, "pct": max(0, min(100, pct))})
    return out


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

    # تلاش برای گرفتن مقادیر از لاگ‌ها، اگر نبود فقط از game نهایی پر می‌کنیم
    turn = 0
    for r in rows[-10:]:
        turn += 1
        scenario_title = r["scenario_title"] if "scenario_title" in r.keys() else "سناریو"
        choice_text = r["choice_text"] if "choice_text" in r.keys() else (r["choice"] if "choice" in r.keys() else "انتخاب")
        db = r["budget_impact"] if "budget_impact" in r.keys() else (r["cost_impact"] if "cost_impact" in r.keys() else 0)
        dr = r["reputation_impact"] if "reputation_impact" in r.keys() else 0
        dm = r["morale_impact"] if "morale_impact" in r.keys() else 0

        timeline.append({
            "turn": r["turn"] if "turn" in r.keys() else turn,
            "scenario_title": scenario_title,
            "choice_text": choice_text,
            "db": f"{db:+d}",
            "dr": f"{dr:+d}",
            "dm": f"{dm:+d}",
        })

        # اگر ستون‌های “بعد از اعمال” نداریم، فعلاً سری‌ها رو از impactها می‌سازیم
        rep_series.append(int(dr))
        morale_series.append(int(dm))
        budget_series.append(int(db))

    conn.close()

    # اگر سری‌ها بر اساس impact ساخته شده، فقط نمودار “شدت تصمیم‌ها” می‌شه؛ برای دانشجویی خوبه.
    # Clamp برای rep/morale: 0..100، budget: 0..2000
    rep_points = _pct_series([abs(x) for x in rep_series], 0, 100)
    morale_points = _pct_series([abs(x) for x in morale_series], 0, 100)
    budget_points = _pct_series([abs(x) for x in budget_series], 0, 2000)

    return render_template(
        "report.html",
        mode=session.get("mode", "classic"),
        turns=len(rows),
        final_budget=game["budget"],
        final_rep=game["reputation"],
        final_morale=game["morale"],
        timeline=timeline,
        rep_series=rep_points,
        morale_series=morale_points,
        budget_series=budget_points
    )


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
