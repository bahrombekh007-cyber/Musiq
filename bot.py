import os
import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import logging
from flask import Flask, request, render_template_string, jsonify
import time

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot token - Railwayda environment variable
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8418511713:AAFkb9zPXNqdwaw4sb3AmjSLQkTKeBXRMVM")
bot = telebot.TeleBot(BOT_TOKEN)

# Flask app
app = Flask(__name__)

# Database
def get_db():
    conn = sqlite3.connect('finance.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                (user_id INTEGER PRIMARY KEY,
                 username TEXT,
                 first_name TEXT,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER,
                 amount REAL,
                 description TEXT,
                 category TEXT,
                 type TEXT,
                 date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS categories
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER,
                 name TEXT,
                 type TEXT,
                 icon TEXT)''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

init_database()

# HTML Templates
MAIN_HTML = '''
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Moliya Hisobchisi</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        
        .card {
            background: white;
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            animation: slideUp 0.5s ease;
        }
        
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .balance-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 20px;
        }
        
        .balance-label {
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 10px;
        }
        
        .balance-amount {
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 15px;
        }
        
        .balance-stats {
            display: flex;
            justify-content: space-between;
        }
        
        .stat-item {
            text-align: center;
        }
        
        .stat-value {
            font-size: 18px;
            font-weight: bold;
        }
        
        .menu-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .menu-item {
            background: white;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            border: 2px solid #f0f0f0;
        }
        
        .menu-item:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            border-color: #667eea;
        }
        
        .menu-icon {
            font-size: 32px;
            margin-bottom: 10px;
        }
        
        .menu-title {
            font-weight: 600;
            color: #333;
        }
        
        .transactions-list {
            margin-top: 20px;
        }
        
        .transaction-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 12px;
            margin-bottom: 10px;
            border-left: 4px solid;
        }
        
        .transaction-income {
            border-left-color: #28a745;
        }
        
        .transaction-expense {
            border-left-color: #dc3545;
        }
        
        .transaction-info {
            flex: 1;
        }
        
        .transaction-category {
            font-weight: 600;
            color: #333;
        }
        
        .transaction-desc {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        
        .transaction-amount {
            font-weight: bold;
            font-size: 16px;
        }
        
        .transaction-date {
            font-size: 11px;
            color: #999;
            margin-top: 5px;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            width: 100%;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .text-success { color: #28a745; }
        .text-danger { color: #dc3545; }
        .text-center { text-align: center; }
        .mt-20 { margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="balance-card">
            <div class="balance-label">Jami balans</div>
            <div class="balance-amount">{{ "{:,.0f}".format(balance) }} so'm</div>
            <div class="balance-stats">
                <div class="stat-item">
                    <div class="stat-value" style="color: #a5d6a5;">+{{ "{:,.0f}".format(today_income) }}</div>
                    <div class="balance-label">Bugungi daromad</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color: #ffb3b3;">-{{ "{:,.0f}".format(today_expense) }}</div>
                    <div class="balance-label">Bugungi xarajat</div>
                </div>
            </div>
        </div>
        
        <div class="menu-grid">
            <div class="menu-item" onclick="location.href='/income/{{ user_id }}'">
                <div class="menu-icon">💰</div>
                <div class="menu-title">Daromad</div>
            </div>
            <div class="menu-item" onclick="location.href='/expense/{{ user_id }}'">
                <div class="menu-icon">💸</div>
                <div class="menu-title">Xarajat</div>
            </div>
            <div class="menu-item" onclick="location.href='/history/{{ user_id }}'">
                <div class="menu-icon">📜</div>
                <div class="menu-title">Tarix</div>
            </div>
            <div class="menu-item" onclick="location.href='/stats/{{ user_id }}'">
                <div class="menu-icon">📊</div>
                <div class="menu-title">Statistika</div>
            </div>
        </div>
        
        <div class="card">
            <h3>📋 Oxirgi operatsiyalar</h3>
            <div class="transactions-list">
                {% for t in transactions %}
                <div class="transaction-item {% if t.type == 'income' %}transaction-income{% else %}transaction-expense{% endif %}">
                    <div class="transaction-info">
                        <div class="transaction-category">{{ t.category }}</div>
                        {% if t.description %}
                        <div class="transaction-desc">{{ t.description }}</div>
                        {% endif %}
                        <div class="transaction-date">{{ t.date }}</div>
                    </div>
                    <div class="transaction-amount {% if t.type == 'income' %}text-success{% else %}text-danger{% endif %}">
                        {% if t.type == 'income' %}+{% else %}-{% endif %}{{ "{:,.0f}".format(t.amount) }}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
</body>
</html>
'''

ADD_HTML = '''
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 500px;
            margin: 0 auto;
        }
        
        .card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            animation: slideUp 0.5s ease;
        }
        
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        h1 {
            color: #333;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 500;
        }
        
        input, select, textarea {
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            font-size: 16px;
            transition: all 0.3s;
        }
        
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .btn {
            padding: 15px 30px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            width: 100%;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        
        .btn-group {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
        
        .btn-group .btn {
            flex: 1;
        }
        
        .success-message {
            background: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>{{ emoji }} {{ title }}</h1>
            
            {% if success %}
            <div class="success-message">
                ✅ {{ success }}
            </div>
            {% endif %}
            
            <form method="POST">
                <div class="form-group">
                    <label>Kategoriya</label>
                    <select name="category" required>
                        {% for cat in categories %}
                        <option value="{{ cat }}">{{ cat }}</option>
                        {% endfor %}
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Miqdor (so'm)</label>
                    <input type="number" name="amount" placeholder="Masalan: 50000" required min="1">
                </div>
                
                <div class="form-group">
                    <label>Tavsif (ixtiyoriy)</label>
                    <textarea name="description" rows="3" placeholder="Tavsif kiriting..."></textarea>
                </div>
                
                <div class="btn-group">
                    <button type="submit" class="btn btn-primary">💾 Saqlash</button>
                    <button type="button" class="btn btn-secondary" onclick="location.href='/user/{{ user_id }}'">❌ Bekor qilish</button>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
'''

HISTORY_HTML = '''
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Operatsiyalar tarixi</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        
        .card {
            background: white;
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            animation: slideUp 0.5s ease;
        }
        
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        h1 {
            color: #333;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .filter-buttons {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .filter-btn {
            flex: 1;
            padding: 10px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
            background: #f0f0f0;
        }
        
        .filter-btn.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .transaction-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 12px;
            margin-bottom: 10px;
            border-left: 4px solid;
        }
        
        .transaction-income {
            border-left-color: #28a745;
        }
        
        .transaction-expense {
            border-left-color: #dc3545;
        }
        
        .transaction-info {
            flex: 1;
        }
        
        .transaction-category {
            font-weight: 600;
            color: #333;
        }
        
        .transaction-desc {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        
        .transaction-amount {
            font-weight: bold;
            font-size: 16px;
        }
        
        .transaction-date {
            font-size: 11px;
            color: #999;
            margin-top: 5px;
        }
        
        .text-success { color: #28a745; }
        .text-danger { color: #dc3545; }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            width: 100%;
            margin-top: 20px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>📜 Operatsiyalar tarixi</h1>
            
            <div class="filter-buttons">
                <button class="filter-btn active" onclick="filterTransactions('all', this)">Hammasi</button>
                <button class="filter-btn" onclick="filterTransactions('income', this)">Daromad</button>
                <button class="filter-btn" onclick="filterTransactions('expense', this)">Xarajat</button>
            </div>
            
            <div id="transactions-list">
                {% for t in transactions %}
                <div class="transaction-item {% if t.type == 'income' %}transaction-income{% else %}transaction-expense{% endif %}" data-type="{{ t.type }}">
                    <div class="transaction-info">
                        <div class="transaction-category">{{ t.category }}</div>
                        {% if t.description %}
                        <div class="transaction-desc">{{ t.description }}</div>
                        {% endif %}
                        <div class="transaction-date">{{ t.date }}</div>
                    </div>
                    <div class="transaction-amount {% if t.type == 'income' %}text-success{% else %}text-danger{% endif %}">
                        {% if t.type == 'income' %}+{% else %}-{% endif %}{{ "{:,.0f}".format(t.amount) }}
                    </div>
                </div>
                {% endfor %}
            </div>
            
            <button class="btn" onclick="location.href='/user/{{ user_id }}'">
                🔙 Orqaga
            </button>
        </div>
    </div>
    
    <script>
        function filterTransactions(type, btn) {
            const items = document.querySelectorAll('.transaction-item');
            const buttons = document.querySelectorAll('.filter-btn');
            
            buttons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            items.forEach(item => {
                if (type === 'all' || item.dataset.type === type) {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });
        }
    </script>
</body>
</html>
'''

STATS_HTML = '''
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Statistika</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        
        .card {
            background: white;
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            animation: slideUp 0.5s ease;
        }
        
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        h1 {
            color: #333;
            margin-bottom: 20px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 30px;
        }
        
        .stats-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
        }
        
        .stats-label {
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 10px;
        }
        
        .stats-value {
            font-size: 24px;
            font-weight: bold;
        }
        
        .category-list {
            margin-top: 20px;
        }
        
        .category-item {
            margin-bottom: 15px;
        }
        
        .category-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
        }
        
        .category-name {
            font-weight: 600;
        }
        
        .category-amount {
            color: #666;
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            border-radius: 4px;
            transition: width 0.3s;
        }
        
        .monthly-list {
            margin-top: 20px;
        }
        
        .month-item {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #e0e0e0;
        }
        
        .month-name {
            font-weight: 600;
        }
        
        .month-income {
            color: #28a745;
            margin-right: 10px;
        }
        
        .month-expense {
            color: #dc3545;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            width: 100%;
            margin-top: 20px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>📊 Statistika</h1>
            
            <div class="stats-grid">
                <div class="stats-card">
                    <div class="stats-label">Jami daromad</div>
                    <div class="stats-value">{{ "{:,.0f}".format(total_income) }} so'm</div>
                </div>
                <div class="stats-card">
                    <div class="stats-label">Jami xarajat</div>
                    <div class="stats-value">{{ "{:,.0f}".format(total_expense) }} so'm</div>
                </div>
            </div>
            
            <div class="card" style="padding: 20px;">
                <h3>📉 Xarajatlar kategoriyalari</h3>
                <div class="category-list">
                    {% for cat, amount, percent in expense_cats %}
                    <div class="category-item">
                        <div class="category-header">
                            <span class="category-name">{{ cat }}</span>
                            <span class="category-amount">{{ "{:,.0f}".format(amount) }} so'm ({{ "%.1f"|format(percent) }}%)</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: {{ percent }}%"></div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            
            <div class="card" style="padding: 20px;">
                <h3>📅 Oylik statistika</h3>
                <div class="monthly-list">
                    {% for month, income, expense in monthly_stats %}
                    <div class="month-item">
                        <span class="month-name">{{ month }}</span>
                        <span>
                            <span class="month-income">+{{ "{:,.0f}".format(income) }}</span>
                            <span class="month-expense">-{{ "{:,.0f}".format(expense) }}</span>
                        </span>
                    </div>
                    {% endfor %}
                </div>
            </div>
            
            <button class="btn" onclick="location.href='/user/{{ user_id }}'">
                🔙 Orqaga
            </button>
        </div>
    </div>
</body>
</html>
'''

# Database functions
def get_user_data(user_id):
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='income'", (user_id,))
    income = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='expense'", (user_id,))
    expense = c.fetchone()[0] or 0
    balance = income - expense
    
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='income' AND date LIKE ?", 
             (user_id, f"{today}%"))
    today_income = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='expense' AND date LIKE ?", 
             (user_id, f"{today}%"))
    today_expense = c.fetchone()[0] or 0
    
    c.execute('''SELECT amount, description, category, type, 
                strftime('%d.%m.%Y %H:%M', date) as datetime 
                FROM transactions WHERE user_id=? ORDER BY date DESC LIMIT 10''', (user_id,))
    transactions = []
    for row in c.fetchall():
        transactions.append({
            'amount': row[0],
            'description': row[1],
            'category': row[2],
            'type': row[3],
            'date': row[4]
        })
    
    conn.close()
    return balance, today_income, today_expense, transactions

def get_categories(user_id, trans_type):
    conn = get_db()
    c = conn.cursor()
    
    default_cats = {
        'income': ['💰 Ish haqi', '💼 Bonus', '📱 Freelance', '🎁 Sovg\'a', '💹 Investitsiya'],
        'expense': ['🍽️ Ovqat', '🚖 Transport', '🛒 Kiyim', '🏠 Uy', '📞 Telefon', 
                    '🎮 Ko\'ngilochar', '🏥 Sog\'liq', '📚 Ta\'lim', '🐾 Boshqa']
    }
    
    c.execute("SELECT name FROM categories WHERE user_id=? AND type=?", (user_id, trans_type))
    db_cats = [row[0] for row in c.fetchall()]
    
    if not db_cats:
        for cat in default_cats[trans_type]:
            c.execute("INSERT INTO categories (user_id, name, type) VALUES (?, ?, ?)",
                     (user_id, cat, trans_type))
        conn.commit()
        categories = default_cats[trans_type]
    else:
        categories = db_cats
    
    conn.close()
    return categories

def add_transaction(user_id, amount, description, category, trans_type):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO transactions (user_id, amount, description, category, type)
                VALUES (?, ?, ?, ?, ?)''',
             (user_id, amount, description, category, trans_type))
    conn.commit()
    conn.close()

def get_history(user_id, limit=100):
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT amount, description, category, type, 
                strftime('%d.%m.%Y %H:%M', date) as datetime 
                FROM transactions WHERE user_id=? ORDER BY date DESC LIMIT ?''', 
             (user_id, limit))
    transactions = []
    for row in c.fetchall():
        transactions.append({
            'amount': row[0],
            'description': row[1],
            'category': row[2],
            'type': row[3],
            'date': row[4]
        })
    conn.close()
    return transactions

def get_stats(user_id):
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='income'", (user_id,))
    total_income = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='expense'", (user_id,))
    total_expense = c.fetchone()[0] or 0
    
    c.execute('''SELECT category, SUM(amount) FROM transactions 
                WHERE user_id=? AND type='expense' 
                GROUP BY category ORDER BY SUM(amount) DESC''', (user_id,))
    expense_cats = []
    for cat, amount in c.fetchall():
        percent = (amount / total_expense * 100) if total_expense > 0 else 0
        expense_cats.append((cat, amount, percent))
    
    c.execute('''SELECT strftime('%Y-%m', date) as month,
                       SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
                       SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
                FROM transactions WHERE user_id=?
                GROUP BY month ORDER BY month DESC LIMIT 6''', (user_id,))
    
    monthly_stats = []
    for row in c.fetchall():
        month = row[0]
        year, month_num = month.split('-')
        month_names = ['Yan', 'Fev', 'Mar', 'Apr', 'May', 'Iyun',
                      'Iyul', 'Avg', 'Sen', 'Okt', 'Noy', 'Dek']
        month_name = month_names[int(month_num) - 1]
        monthly_stats.append((f"{month_name} {year}", row[1] or 0, row[2] or 0))
    
    conn.close()
    return total_income, total_expense, expense_cats, monthly_stats

# Flask routes
@app.route('/')
def home():
    return '''
    <html>
    <head>
        <title>Moliya Hisobchisi</title>
        <style>
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 20px;
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
                max-width: 400px;
                width: 100%;
                animation: slideUp 0.5s ease;
            }
            @keyframes slideUp {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }
            h1 { 
                color: #333; 
                margin-bottom: 30px;
                font-size: 28px;
            }
            p {
                color: #666;
                margin-bottom: 20px;
            }
            input { 
                padding: 15px; 
                width: 100%; 
                margin-bottom: 20px;
                border: 2px solid #e0e0e0;
                border-radius: 12px;
                font-size: 16px;
                box-sizing: border-box;
            }
            input:focus {
                outline: none;
                border-color: #667eea;
            }
            button {
                padding: 15px 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                width: 100%;
                transition: transform 0.3s;
            }
            button:hover { 
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
            }
            .info {
                margin-top: 20px;
                color: #999;
                font-size: 12px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>💰 Moliya Hisobchisi</h1>
            <p>Telegram ID-ingizni kiriting:</p>
            <input type="number" id="userId" placeholder="Masalan: 123456789">
            <button onclick="goToUser()">Kirish</button>
            <div class="info">
                Telegram ID ni @userinfobot dan olishingiz mumkin
            </div>
        </div>
        <script>
            function goToUser() {
                const userId = document.getElementById('userId').value;
                if (userId) {
                    window.location.href = '/user/' + userId;
                } else {
                    alert('Iltimos, Telegram ID kiriting!');
                }
            }
        </script>
    </body>
    </html>
    '''

@app.route('/user/<int:user_id>')
def user_dashboard(user_id):
    balance, today_income, today_expense, transactions = get_user_data(user_id)
    return render_template_string(MAIN_HTML, 
                                 user_id=user_id,
                                 balance=balance,
                                 today_income=today_income,
                                 today_expense=today_expense,
                                 transactions=transactions)

@app.route('/income/<int:user_id>', methods=['GET', 'POST'])
def add_income(user_id):
    categories = get_categories(user_id, 'income')
    
    if request.method == 'POST':
        amount = float(request.form['amount'])
        description = request.form['description']
        category = request.form['category']
        
        add_transaction(user_id, amount, description, category, 'income')
        
        return render_template_string(ADD_HTML,
                                     user_id=user_id,
                                     title="Daromad qo'shish",
                                     emoji="💰",
                                     categories=categories,
                                     success="Daromad muvaffaqiyatli qo'shildi!")
    
    return render_template_string(ADD_HTML,
                                 user_id=user_id,
                                 title="Daromad qo'shish",
                                 emoji="💰",
                                 categories=categories,
                                 success=None)

@app.route('/expense/<int:user_id>', methods=['GET', 'POST'])
def add_expense(user_id):
    categories = get_categories(user_id, 'expense')
    
    if request.method == 'POST':
        amount = float(request.form['amount'])
        description = request.form['description']
        category = request.form['category']
        
        add_transaction(user_id, amount, description, category, 'expense')
        
        return render_template_string(ADD_HTML,
                                     user_id=user_id,
                                     title="Xarajat qo'shish",
                                     emoji="💸",
                                     categories=categories,
                                     success="Xarajat muvaffaqiyatli qo'shildi!")
    
    return render_template_string(ADD_HTML,
                                 user_id=user_id,
                                 title="Xarajat qo'shish",
                                 emoji="💸",
                                 categories=categories,
                                 success=None)

@app.route('/history/<int:user_id>')
def history(user_id):
    transactions = get_history(user_id, 100)
    return render_template_string(HISTORY_HTML,
                                 user_id=user_id,
                                 transactions=transactions)

@app.route('/stats/<int:user_id>')
def stats(user_id):
    total_income, total_expense, expense_cats, monthly_stats = get_stats(user_id)
    return render_template_string(STATS_HTML,
                                 user_id=user_id,
                                 total_income=total_income,
                                 total_expense=total_expense,
                                 expense_cats=expense_cats,
                                 monthly_stats=monthly_stats)

# Telegram bot handlers
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
             (user_id, username, first_name))
    conn.commit()
    conn.close()
    
    # Railway URL ni olish (HTTPS)
    railway_url = os.environ.get('webhook-processor-production-6f0b.up.railway.app')
if railway_url:
        webapp_url = f"https://{railway_url}/user/{user_id}"
    else:
        # Local ishlatish uchun
        webapp_url = f"https://your-domain.com/user/{user_id}"
    
    markup = types.InlineKeyboardMarkup()
    web_app = types.WebAppInfo(url=webapp_url)
    btn = types.InlineKeyboardButton("🚀 Web App ni ochish", web_app=web_app)
    markup.add(btn)
    
    bot.send_message(
        message.chat.id,
        f"👋 Assalomu alaykum, {first_name}!\n\n"
        f"💰 Moliya hisobchisi botiga xush kelibsiz!\n\n"
        f"📌 Quyidagi tugmani bosib, chiroyli web interfeys orqali boshqaring:",
        reply_markup=markup
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
❓ Yordam

💰 Daromad qo'shish: Web App dan foydalaning
💸 Xarajat qo'shish: Web App dan foydalaning
📊 Balans ko'rish: Web App dan foydalaning
📜 Tarix: Web App dan foydalaning
📈 Statistika: Web App dan foydalaning

🌐 Web App: /start tugmasini bosing
    """
    bot.send_message(message.chat.id, help_text)

# Webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'OK', 200

# Health check
@app.route('/health')
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})

# Main
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    railway_url = os.environ.get('webhook-processor-production-6f0b.up.railway.app')
    
    if railway_url:
        # Webhook o'rnatish (polling emas)
        webhook_url = f"https://{railway_url}/webhook"
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    else:
        # Local development
        logger.warning("No RAILWAY_PUBLIC_DOMAIN found, using polling")
        import threading
        def run_polling():
            bot.infinity_polling()
        threading.Thread(target=run_polling, daemon=True).start()
    
    # Flask serverni ishga tushirish
    app.run(host='0.0.0.0', port=port)
