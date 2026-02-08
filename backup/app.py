from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import requests
import json
import os
import re
import random

app = Flask(__name__)
app.secret_key = 'my_secret_key'

# 🔴 تنظیمات (کلید و پورت خود را چک کنید)
GOOGLE_API_KEY = "AIzaSyA1_7aaw4xwhcL6Y5OzmqwzFskmZWPc9rU"  # کلید خود را جایگزین کنید
MY_PROXY_PORT = "2080"               # پورت خود را جایگزین کنید

proxies = {
    "http": f"http://127.0.0.1:{MY_PROXY_PORT}",
    "https": f"http://127.0.0.1:{MY_PROXY_PORT}",
}

# استفاده از مدل سریع و هوشمند
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GOOGLE_API_KEY}"

def get_db_connection():
    conn = sqlite3.connect('startup.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- تابع جدید: تولید سناریو با هوش مصنوعی ---
def generate_dynamic_scenario(game_id, startup_name, turn_number):
    conn = get_db_connection()
    
    # 1. گرفتن سناریوهای قبلی برای جلوگیری از تکرار
    previous_logs = conn.execute('SELECT scenario_title FROM game_logs WHERE game_id = ?', (game_id,)).fetchall()
    previous_titles = ", ".join([row['scenario_title'] for row in previous_logs])

    # 2. نوشتن پرامپت مهندسی شده
    scenario_types = ["CRISIS", "OPPORTUNITY", "NORMAL", "DILEMMA"]
    selected_type = random.choices(scenario_types, weights=[4, 3, 2, 1], k=1)[0]
    
    prompt_text = prompt_text = f"""
    تو موتور بازی‌سازی هستی. یک سناریوی جدید برای استارتاپ "{startup_name}" بساز.
    نوبت بازی: {turn_number}
    نوع سناریو: {selected_type} (حتما طبق این نوع بساز)
    
    تعاریف انواع سناریو:
    - CRISIS: یک بحران که معمولا پول یا شهرت کم میکند. (انتخاب بین بد و بدتر).
    - OPPORTUNITY: یک فرصت طلایی که میتواند سرمایه (Budget) را زیاد کند (درآمدزا باشد).
    - DILEMMA: دوراهی اخلاقی یا استراتژیک پیچیده.
    - NORMAL: چالش‌های روزمره.

    قوانین مهم محاسبات:
    1. همه گزینه‌ها نباید پول کم کنند. اگر نوع سناریو OPPORTUNITY است، حتما گزینه‌هایی با cost مثبت (درآمد) بده.
    2. تاثیرات (Impacts) باید واقعی باشد. مثلا تبلیغات پول کم میکند (Cost منفی) ولی شهرت می‌آورد.
    3. مقادیر معمولا بین -200 تا +200 باشد.
    
    فرمت خروجی JSON (فقط همین را برگردان):
    {{
        "title": "عنوان کوتاه",
        "description": "توضیح مشکل یا فرصت (2 خط)",
        "options": [
            {{
                "text": "متن گزینه اول",
                "cost": -100,  // منفی یعنی هزینه، مثبت یعنی درآمد
                "reputation": 10, // مثبت یعنی افزایش شهرت
                "morale": -5 // منفی یعنی کاهش روحیه
            }},
            {{
                "text": "متن گزینه دوم",
                "cost": 500, 
                "reputation": -50,
                "morale": 0
            }},
            {{
                "text": "متن گزینه سوم",
                "cost": 0, 
                "reputation": 0,
                "morale": 10
            }}
        ]
    }}
    """

    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt_text}]}]}

    try:
        # ارسال به AI
        response = requests.post(API_URL, headers=headers, json=data, proxies=proxies, timeout=15)
        response.raise_for_status()
        
        # تمیزکاری خروجی (حذف ```json و این چیزها)
        raw_text = response.json()['candidates'][0]['content']['parts'][0]['text']
        clean_json = raw_text.replace("```json", "").replace("```", "").strip()
        
        scenario_data = json.loads(clean_json) # تبدیل متن به دیکشنری پایتون
        
        # ذخیره در دیتابیس
        cursor = conn.cursor()
        
        # ثبت سناریوی جدید
        cursor.execute("INSERT INTO scenarios (title, description) VALUES (?, ?)", 
                       (scenario_data['title'], scenario_data['description']))
        scenario_id = cursor.lastrowid
        
        # ثبت گزینه‌ها
        for opt in scenario_data['options']:
            cursor.execute("""
                INSERT INTO choices (scenario_id, text, cost_impact, reputation_impact, morale_impact) 
                VALUES (?, ?, ?, ?, ?)
            """, (scenario_id, opt['text'], opt['cost'], opt['reputation'], opt['morale']))
            
        conn.commit()
        return scenario_id

    except Exception as e:
        print(f"❌ خطا در تولید سناریو: {e}")
        # اگر AI کار نکرد، یک سناریوی اضطراری از دیتابیس برمی‌گرداند
        fallback = conn.execute('SELECT id FROM scenarios ORDER BY RANDOM() LIMIT 1').fetchone()
        return fallback['id'] if fallback else None
    finally:
        conn.close()

# --- روت‌های سایت ---

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # اینجا همان منطق شروع بازی/ساخت user/game که قبلاً داشتی را صدا بزن
        return redirect(url_for("new_game"))  # یا هر روتی که شروع بازی است
    return render_template("index.html")


@app.route('/new_game', methods=['POST'])
def new_game():
    username = request.form['username']
    startup_name = request.form['startup_name']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users (username) VALUES (?)', (username,))
    user_id = cursor.lastrowid
    cursor.execute('INSERT INTO games (user_id, startup_name) VALUES (?, ?)', (user_id, startup_name))
    game_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    session['game_id'] = game_id
    
    # تولید اولین سناریو بلافاصله بعد از شروع
    generate_dynamic_scenario(game_id, startup_name, 1)
    
    return redirect(url_for('game'))

@app.route('/game')
def game():
    if 'game_id' not in session: return redirect(url_for('index'))
    game_id = session['game_id']
    conn = get_db_connection()
    game = conn.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
    
    # شرط باخت
    if game['budget'] <= 0 or game['reputation'] <= 0:
        return render_template('game_over.html', game=game) # صفحه باخت (باید بسازید یا ساده ریترن کنید)

    # گرفتن آخرین سناریوی تولید شده (نه رندوم!)
    # ما فرض می‌کنیم آخرین سناریوی اضافه شده به دیتابیس مال این بازی است
    # برای دقت بیشتر در پروژه واقعی باید game_id رو به scenarios اضافه کنیم، ولی اینجا ساده می‌گیریم:
    scenario = conn.execute('SELECT * FROM scenarios ORDER BY id DESC LIMIT 1').fetchone()
    choices = conn.execute('SELECT * FROM choices WHERE scenario_id = ?', (scenario['id'],)).fetchall()
    
    conn.close()
    return render_template('game.html', game=game, scenario=scenario, choices=choices)

@app.route('/action', methods=['POST'])
def action():
    game_id = session['game_id']
    choice_id = request.form['choice_id']
    
    conn = get_db_connection()
    choice = conn.execute('SELECT * FROM choices WHERE id = ?', (choice_id,)).fetchone()
    scenario = conn.execute('SELECT * FROM scenarios WHERE id = ?', (choice['scenario_id'],)).fetchone()
    game = conn.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()

    # آپدیت وضعیت بازی
    conn.execute('''
        UPDATE games 
        SET budget = budget + ?, reputation = reputation + ?, morale = morale + ?, turn = turn + 1
        WHERE id = ?
    ''', (choice['cost_impact'], choice['reputation_impact'], choice['morale_impact'], game_id))
    
    # تولید نتیجه داستان (کوتاه)
    prompt_story = f"""
    راوی بازی هستی. کوتاه فارسی بنویس.
    استارتاپ: {game['startup_name']}
    چالش: {scenario['title']}
    تصمیم: {choice['text']}
    نتیجه چی شد؟
    """
    
    # اینجا درخواست جداگانه برای متن نتیجه می‌زنیم
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt_story}]}]}
    try:
        res = requests.post(API_URL, headers=headers, json=data, proxies=proxies, timeout=5)
        ai_story = res.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        ai_story = "تصمیم ثبت شد."

    conn.execute('INSERT INTO game_logs (game_id, scenario_title, user_choice, ai_response) VALUES (?, ?, ?, ?)', 
                 (game_id, scenario['title'], choice['text'], ai_story))
    conn.commit()
    conn.close()
    
    return render_template('result.html', story=ai_story, game=game)

@app.route('/next_turn')
def next_turn():
    # این روت وقتی زده میشه که کاربر دکمه "مرحله بعد" رو توی صفحه نتیجه میزنه
    game_id = session['game_id']
    conn = get_db_connection()
    game = conn.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
    
    # تولید سناریوی جدید برای نوبت بعدی
    generate_dynamic_scenario(game_id, game['startup_name'], game['turn'])
    
    conn.close()
    return redirect(url_for('game'))

if __name__ == '__main__':
    app.run(debug=True)