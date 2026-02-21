#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import logging
import time
from typing import Dict, List, Optional

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot tokeni (sizning tokeningiz)
BOT_TOKEN = "8418511713:AAFkb9zPXNqdwaw4sb3AmjSLQkTKeBXRMVM"

# Botni yaratish
bot = telebot.TeleBot(BOT_TOKEN)

# Foydalanuvchi holatlarini saqlash
user_states = {}

class FinanceBot:
    def __init__(self):
        self.init_database()
    
    def init_database(self):
        """Ma'lumotlar bazasini yaratish"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        # Foydalanuvchilar jadvali
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (user_id INTEGER PRIMARY KEY,
                     username TEXT,
                     first_name TEXT,
                     registered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Kategoriyalar jadvali
        c.execute('''CREATE TABLE IF NOT EXISTS categories
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     user_id INTEGER,
                     name TEXT,
                     type TEXT,
                     icon TEXT,
                     FOREIGN KEY (user_id) REFERENCES users (user_id))''')
        
        # Transaksiyalar jadvali
        c.execute('''CREATE TABLE IF NOT EXISTS transactions
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     user_id INTEGER,
                     amount REAL,
                     description TEXT,
                     category TEXT,
                     type TEXT,
                     date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                     FOREIGN KEY (user_id) REFERENCES users (user_id))''')
        
        conn.commit()
        conn.close()
    
    def register_user(self, user_id, username, first_name):
        """Yangi foydalanuvchini ro'yxatdan o'tkazish"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        # Foydalanuvchini qo'shish
        c.execute('''INSERT OR IGNORE INTO users (user_id, username, first_name)
                    VALUES (?, ?, ?)''', (user_id, username, first_name))
        
        # Default kategoriyalar qo'shish
        default_categories = [
            (user_id, '💰 Ish haqi', 'income', '💼'),
            (user_id, '💼 Bonus', 'income', '🎁'),
            (user_id, '📱 Freelance', 'income', '💻'),
            (user_id, '🎁 Sovg\'a', 'income', '🎀'),
            (user_id, '🍽️ Ovqat', 'expense', '🍔'),
            (user_id, '🚖 Transport', 'expense', '🚗'),
            (user_id, '🛒 Kiyim', 'expense', '👕'),
            (user_id, '🏠 Uy', 'expense', '🏡'),
            (user_id, '📞 Telefon', 'expense', '📱'),
            (user_id, '🎮 Ko\'ngilochar', 'expense', '🎮'),
            (user_id, '🏥 Sog\'liq', 'expense', '💊'),
            (user_id, '📚 Ta\'lim', 'expense', '📚')
        ]
        
        for cat in default_categories:
            c.execute('''INSERT OR IGNORE INTO categories (user_id, name, type, icon)
                        VALUES (?, ?, ?, ?)''', cat)
        
        conn.commit()
        conn.close()
    
    def get_categories(self, user_id, trans_type):
        """Foydalanuvchi kategoriyalarini olish"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        c.execute('''SELECT name, icon FROM categories 
                    WHERE user_id=? AND type=? 
                    ORDER BY name''', (user_id, trans_type))
        categories = c.fetchall()
        conn.close()
        return categories
    
    def add_transaction(self, user_id, amount, description, category, trans_type):
        """Yangi transaksiya qo'shish"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        c.execute('''INSERT INTO transactions (user_id, amount, description, category, type)
                    VALUES (?, ?, ?, ?, ?)''',
                 (user_id, amount, description, category, trans_type))
        conn.commit()
        transaction_id = c.lastrowid
        conn.close()
        return transaction_id
    
    def get_balance(self, user_id):
        """Foydalanuvchi balansini hisoblash"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='income'", (user_id,))
        income = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='expense'", (user_id,))
        expense = c.fetchone()[0] or 0
        
        conn.close()
        return income - expense, income, expense
    
    def get_today_stats(self, user_id):
        """Bugungi statistika"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute('''SELECT SUM(amount) FROM transactions 
                    WHERE user_id=? AND type='income' AND date LIKE ?''', 
                 (user_id, f"{today}%"))
        today_income = c.fetchone()[0] or 0
        
        c.execute('''SELECT SUM(amount) FROM transactions 
                    WHERE user_id=? AND type='expense' AND date LIKE ?''', 
                 (user_id, f"{today}%"))
        today_expense = c.fetchone()[0] or 0
        
        conn.close()
        return today_income, today_expense
    
    def get_today_transactions(self, user_id):
        """Bugungi transaksiyalar"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute('''SELECT amount, description, category, type, 
                    strftime('%H:%M', date) as time 
                    FROM transactions 
                    WHERE user_id=? AND date LIKE ? 
                    ORDER BY date DESC''', (user_id, f"{today}%"))
        
        transactions = c.fetchall()
        conn.close()
        return transactions
    
    def get_history(self, user_id, limit=20):
        """Oxirgi transaksiyalar"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        c.execute('''SELECT amount, description, category, type, 
                    strftime('%d.%m.%Y %H:%M', date) as datetime 
                    FROM transactions 
                    WHERE user_id=? 
                    ORDER BY date DESC 
                    LIMIT ?''', (user_id, limit))
        
        transactions = c.fetchall()
        conn.close()
        return transactions
    
    def get_stats(self, user_id):
        """Statistika ma'lumotlari"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        # Kategoriyalar bo'yicha xarajatlar
        c.execute('''SELECT category, SUM(amount), COUNT(*) 
                    FROM transactions 
                    WHERE user_id=? AND type='expense' 
                    GROUP BY category 
                    ORDER BY SUM(amount) DESC''', (user_id,))
        expense_cats = c.fetchall()
        
        # Oylik statistika
        c.execute('''SELECT strftime('%Y-%m', date) as month,
                           SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
                           SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
                    FROM transactions
                    WHERE user_id=?
                    GROUP BY month
                    ORDER BY month DESC
                    LIMIT 6''', (user_id,))
        monthly_stats = c.fetchall()
        
        conn.close()
        return expense_cats, monthly_stats
    
    def delete_transaction(self, user_id, transaction_id):
        """Transaksiyani o'chirish"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        c.execute('''DELETE FROM transactions 
                    WHERE id=? AND user_id=?''', (transaction_id, user_id))
        success = c.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def get_transactions_for_delete(self, user_id, limit=10):
        """O'chirish uchun transaksiyalar ro'yxati"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        c.execute('''SELECT id, amount, description, category, type, 
                    strftime('%d.%m %H:%M', date) as datetime 
                    FROM transactions 
                    WHERE user_id=? 
                    ORDER BY date DESC 
                    LIMIT ?''', (user_id, limit))
        
        transactions = c.fetchall()
        conn.close()
        return transactions

# FinanceBot obyektini yaratish
finance = FinanceBot()

# ==================== BOT HANDLERLARI ====================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Start komandasi"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Foydalanuvchini ro'yxatdan o'tkazish
    finance.register_user(user_id, username, first_name)
    
    # Asosiy menyu
    show_main_menu(message.chat.id, first_name)

def show_main_menu(chat_id, first_name=None):
    """Asosiy menyuni ko'rsatish"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    btn1 = types.InlineKeyboardButton("💰 Daromad", callback_data='menu_income')
    btn2 = types.InlineKeyboardButton("💸 Xarajat", callback_data='menu_expense')
    btn3 = types.InlineKeyboardButton("📊 Balans", callback_data='menu_balance')
    btn4 = types.InlineKeyboardButton("📋 Bugun", callback_data='menu_today')
    btn5 = types.InlineKeyboardButton("📜 Tarix", callback_data='menu_history')
    btn6 = types.InlineKeyboardButton("📈 Statistika", callback_data='menu_stats')
    btn7 = types.InlineKeyboardButton("🗑️ O'chirish", callback_data='menu_delete')
    btn8 = types.InlineKeyboardButton("❓ Yordam", callback_data='menu_help')
    
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)
    
    welcome_text = (
        f"👋 Assalomu alaykum, {first_name if first_name else 'foydalanuvchi'}!\n\n"
        f"💰 Moliya hisobchisi botiga xush kelibsiz!\n\n"
        f"📌 Quyidagi tugmalardan foydalaning:"
    )
    
    bot.send_message(chat_id, welcome_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Callback handler"""
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    user_id = call.from_user.id
    
    try:
        if call.data == 'menu_income':
            show_income_categories(chat_id, message_id, user_id)
        
        elif call.data == 'menu_expense':
            show_expense_categories(chat_id, message_id, user_id)
        
        elif call.data == 'menu_balance':
            show_balance(chat_id, message_id, user_id)
        
        elif call.data == 'menu_today':
            show_today(chat_id, message_id, user_id)
        
        elif call.data == 'menu_history':
            show_history(chat_id, message_id, user_id)
        
        elif call.data == 'menu_stats':
            show_stats(chat_id, message_id, user_id)
        
        elif call.data == 'menu_delete':
            show_delete_menu(chat_id, message_id, user_id)
        
        elif call.data == 'menu_help':
            show_help(chat_id, message_id)
        
        elif call.data == 'back_to_main':
            bot.delete_message(chat_id, message_id)
            show_main_menu(chat_id)
        
        elif call.data.startswith('cat_income_'):
            category = call.data.replace('cat_income_', '')
            ask_amount(chat_id, message_id, user_id, 'income', category)
        
        elif call.data.startswith('cat_expense_'):
            category = call.data.replace('cat_expense_', '')
            ask_amount(chat_id, message_id, user_id, 'expense', category)
        
        elif call.data.startswith('delete_'):
            parts = call.data.split('_')
            transaction_id = int(parts[1])
            confirm_delete(chat_id, message_id, user_id, transaction_id)
        
        elif call.data.startswith('confirm_delete_'):
            transaction_id = int(call.data.replace('confirm_delete_', ''))
            execute_delete(chat_id, message_id, user_id, transaction_id)
        
        elif call.data == 'cancel_delete':
            bot.delete_message(chat_id, message_id)
            show_main_menu(chat_id)
        
    except Exception as e:
        logger.error(f"Callback xatosi: {e}")
        bot.send_message(chat_id, "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

def show_income_categories(chat_id, message_id, user_id):
    """Daromad kategoriyalarini ko'rsatish"""
    categories = finance.get_categories(user_id, 'income')
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat_name, icon in categories:
        callback_data = f"cat_income_{cat_name}"
        markup.add(types.InlineKeyboardButton(f"{icon} {cat_name}", callback_data=callback_data))
    
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_main'))
    
    bot.edit_message_text(
        "💰 Daromad kategoriyasini tanlang:",
        chat_id,
        message_id,
        reply_markup=markup
    )

def show_expense_categories(chat_id, message_id, user_id):
    """Xarajat kategoriyalarini ko'rsatish"""
    categories = finance.get_categories(user_id, 'expense')
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat_name, icon in categories:
        callback_data = f"cat_expense_{cat_name}"
        markup.add(types.InlineKeyboardButton(f"{icon} {cat_name}", callback_data=callback_data))
    
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_main'))
    
    bot.edit_message_text(
        "💸 Xarajat kategoriyasini tanlang:",
        chat_id,
        message_id,
        reply_markup=markup
    )

def ask_amount(chat_id, message_id, user_id, trans_type, category):
    """Miqdorni so'rash"""
    user_states[user_id] = {
        'step': 'waiting_amount',
        'type': trans_type,
        'category': category
    }
    
    text = f"📝 {category} uchun miqdorni kiriting (so'm):"
    bot.delete_message(chat_id, message_id)
    msg = bot.send_message(chat_id, text)
    
    # Xabarni saqlash keyin o'chirish uchun
    user_states[user_id]['last_message_id'] = msg.message_id

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """Xabarlarni qayta ishlash"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text.strip()
    
    # Foydalanuvchi holatini tekshirish
    if user_id in user_states:
        state = user_states[user_id]
        
        if state.get('step') == 'waiting_amount':
            try:
                amount = float(text.replace(' ', ''))
                if amount <= 0:
                    bot.send_message(chat_id, "❌ Miqdor musbat son bo'lishi kerak!")
                    return
                
                state['amount'] = amount
                state['step'] = 'waiting_description'
                
                bot.send_message(chat_id, "📝 Tavsif kiriting (yoki /skip ni bosing):")
                
            except ValueError:
                bot.send_message(chat_id, "❌ Xato! Iltimos, faqat son kiriting (masalan: 50000):")
        
        elif state.get('step') == 'waiting_description':
            description = text if text != '/skip' else ''
            
            # Transaksiyani saqlash
            finance.add_transaction(
                user_id,
                state['amount'],
                description,
                state['category'],
                state['type']
            )
            
            emoji = "✅" if state['type'] == 'income' else "➖"
            type_text = "daromad" if state['type'] == 'income' else "xarajat"
            
            bot.send_message(
                chat_id,
                f"{emoji} <b>{type_text.title()} qo'shildi!</b>\n\n"
                f"💰 Miqdor: <b>{state['amount']:,.0f} so'm</b>\n"
                f"📁 Kategoriya: {state['category']}\n"
                f"📝 Tavsif: {description if description else 'yo\'q'}",
                parse_mode='HTML'
            )
            
            # Holatni tozalash
            del user_states[user_id]
            
            # Asosiy menyuni ko'rsatish
            show_main_menu(chat_id)
    
    else:
        # Agar holat bo'lmasa, start komandasini eslatish
        bot.send_message(chat_id, "❌ Noto'g'ri buyruq. /start ni bosing.")

@bot.message_handler(commands=['skip'])
def handle_skip(message):
    """Skip komandasi"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if user_id in user_states and user_states[user_id].get('step') == 'waiting_description':
        description = ''
        
        state = user_states[user_id]
        
        # Transaksiyani saqlash
        finance.add_transaction(
            user_id,
            state['amount'],
            description,
            state['category'],
            state['type']
        )
        
        emoji = "✅" if state['type'] == 'income' else "➖"
        type_text = "daromad" if state['type'] == 'income' else "xarajat"
        
        bot.send_message(
            chat_id,
            f"{emoji} <b>{type_text.title()} qo'shildi!</b>\n\n"
            f"💰 Miqdor: <b>{state['amount']:,.0f} so'm</b>\n"
            f"📁 Kategoriya: {state['category']}",
            parse_mode='HTML'
        )
        
        # Holatni tozalash
        del user_states[user_id]
        
        # Asosiy menyuni ko'rsatish
        show_main_menu(chat_id)

def show_balance(chat_id, message_id, user_id):
    """Balansni ko'rsatish"""
    balance, total_income, total_expense = finance.get_balance(user_id)
    today_income, today_expense = finance.get_today_stats(user_id)
    
    text = (
        f"💰 <b>SIZNING BALANSINGIZ</b>\n\n"
        f"💵 Jami balans: <b>{balance:+,.0f} so'm</b>\n\n"
        f"📊 <b>Bugungi statistika:</b>\n"
        f"   ➕ Daromad: {today_income:,.0f} so'm\n"
        f"   ➖ Xarajat: {today_expense:,.0f} so'm\n"
        f"   📍 Farq: {today_income - today_expense:+,.0f} so'm\n\n"
        f"📈 <b>Jami:</b>\n"
        f"   ➕ Jami daromad: {total_income:,.0f} so'm\n"
        f"   ➖ Jami xarajat: {total_expense:,.0f} so'm"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_main'))
    
    bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML', reply_markup=markup)

def show_today(chat_id, message_id, user_id):
    """Bugungi operatsiyalarni ko'rsatish"""
    transactions = finance.get_today_transactions(user_id)
    
    if not transactions:
        text = "📭 Bugun hech qanday operatsiya bo'lmagan."
    else:
        text = "📋 <b>BUGUNGI OPERATSIYALAR</b>\n\n"
        for amount, desc, cat, typ, time in transactions:
            emoji = "➕" if typ == 'income' else "➖"
            color = "✅" if typ == 'income' else "❌"
            text += f"{emoji} <b>{amount:,.0f} so'm</b> - {cat}\n"
            if desc:
                text += f"   📝 {desc}\n"
            text += f"   🕐 {time}\n\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_main'))
    
    bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML', reply_markup=markup)

def show_history(chat_id, message_id, user_id):
    """Operatsiyalar tarixini ko'rsatish"""
    transactions = finance.get_history(user_id, 20)
    
    if not transactions:
        text = "📭 Hech qanday operatsiya topilmadi."
    else:
        text = "📜 <b>SO'NGI 20 OPERATSIYA</b>\n\n"
        for amount, desc, cat, typ, dt in transactions:
            emoji = "➕" if typ == 'income' else "➖"
            text += f"{emoji} <b>{amount:,.0f} so'm</b> - {cat}\n"
            text += f"   🕐 {dt}\n"
            if desc:
                text += f"   📝 {desc}\n"
            text += "\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_main'))
    
    bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML', reply_markup=markup)

def show_stats(chat_id, message_id, user_id):
    """Statistikani ko'rsatish"""
    balance, total_income, total_expense = finance.get_balance(user_id)
    expense_cats, monthly_stats = finance.get_stats(user_id)
    
    text = (
        f"📊 <b>STATISTIKA</b>\n\n"
        f"💰 <b>Umumiy:</b>\n"
        f"   ➕ Jami daromad: {total_income:,.0f} so'm\n"
        f"   ➖ Jami xarajat: {total_expense:,.0f} so'm\n"
        f"   💵 Tejam: {total_income - total_expense:+,.0f} so'm\n\n"
    )
    
    if expense_cats:
        text += "📉 <b>Xarajatlar kategoriyalari:</b>\n"
        for cat, amount, count in expense_cats:
            percent = (amount / total_expense * 100) if total_expense > 0 else 0
            bar = "█" * int(percent / 5)
            text += f"   {cat}: {amount:,.0f} so'm ({percent:.1f}%)\n"
            text += f"      {bar} {count} marta\n\n"
    
    if monthly_stats:
        text += "📅 <b>Oxirgi 6 oy:</b>\n"
        for month, income, expense in monthly_stats:
            year, month_num = month.split('-')
            month_names = ['Yan', 'Fev', 'Mar', 'Apr', 'May', 'Iyun',
                          'Iyul', 'Avg', 'Sen', 'Okt', 'Noy', 'Dek']
            month_name = month_names[int(month_num) - 1]
            text += f"   {month_name} {year}: +{income:,.0f} | -{expense:,.0f} = {income - expense:+,.0f}\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_main'))
    
    bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML', reply_markup=markup)

def show_delete_menu(chat_id, message_id, user_id):
    """O'chirish menyusini ko'rsatish"""
    transactions = finance.get_transactions_for_delete(user_id, 10)
    
    if not transactions:
        bot.edit_message_text(
            "📭 O'chirish uchun operatsiyalar mavjud emas.",
            chat_id,
            message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_main')
            )
        )
        return
    
    text = "🗑️ <b>O'CHIRISH UCHUN OPERATSIYA TANLANG</b>\n\n"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for tid, amount, desc, cat, typ, dt in transactions:
        emoji = "➕" if typ == 'income' else "➖"
        btn_text = f"{emoji} {amount:,.0f} so'm - {cat} ({dt})"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"delete_{tid}"))
    
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_main'))
    
    bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML', reply_markup=markup)

def confirm_delete(chat_id, message_id, user_id, transaction_id):
    """O'chirishni tasdiqlash"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Ha", callback_data=f"confirm_delete_{transaction_id}"),
        types.InlineKeyboardButton("❌ Yo'q", callback_data='cancel_delete')
    )
    
    bot.edit_message_text(
        "⚠️ Bu operatsiyani o'chirmoqchimisiz?",
        chat_id,
        message_id,
        reply_markup=markup
    )

def execute_delete(chat_id, message_id, user_id, transaction_id):
    """Transaksiyani o'chirish"""
    success = finance.delete_transaction(user_id, transaction_id)
    
    if success:
        text = "✅ Operatsiya muvaffaqiyatli o'chirildi!"
    else:
        text = "❌ Operatsiyani o'chirishda xatolik yuz berdi."
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Menyu", callback_data='back_to_main'))
    
    bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)

def show_help(chat_id, message_id):
    """Yordam ma'lumotlarini ko'rsatish"""
    help_text = (
        "❓ <b>YORDAM</b>\n\n"
        "💰 <b>Daromad qo'shish:</b>\n"
        "   Daromad tugmasini bosing -> kategoriya tanlang -> miqdor kiriting\n\n"
        "💸 <b>Xarajat qo'shish:</b>\n"
        "   Xarajat tugmasini bosing -> kategoriya tanlang -> miqdor kiriting\n\n"
        "📊 <b>Balans:</b>\n"
        "   Jami balans va bugungi statistikani ko'rish\n\n"
        "📋 <b>Bugun:</b>\n"
        "   Bugungi barcha operatsiyalar ro'yxati\n\n"
        "📜 <b>Tarix:</b>\n"
        "   So'nggi 20 operatsiya\n\n"
        "📈 <b>Statistika:</b>\n"
        "   Kategoriyalar bo'yicha tahlil\n\n"
        "🗑️ <b>O'chirish:</b>\n"
        "   Xato kiritilgan operatsiyani o'chirish\n\n"
        "🤖 <b>Bot haqida:</b>\n"
        "   Versiya: 1.0\n"
        "   Yaratilgan: 2024"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_main'))
    
    bot.edit_message_text(help_text, chat_id, message_id, parse_mode='HTML', reply_markup=markup)

@bot.message_handler(commands=['help'])
def send_help(message):
    """Help komandasi"""
    show_help(message.chat.id, message.message_id)

# ==================== BOTNI ISHGA TUSHIRISH ====================

def main():
    """Asosiy funksiya"""
    print("=" * 50)
    print("💰 MOLIYA HISOBCHISI BOTI")
    print("=" * 50)
    print(f"🤖 Bot token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-5:]}")
    print("✅ Bot ishga tushmoqda...")
    
    try:
        bot_info = bot.get_me()
        print(f"✅ Bot nomi: {bot_info.first_name}")
        print(f"✅ Bot username: @{bot_info.username}")
        print("=" * 50)
        print("🟢 Bot ishlamoqda...")
        print("=" * 50)
        
        # Botni ishga tushirish
        bot.infinity_polling()
        
    except Exception as e:
        print(f"❌ Xatolik: {e}")
        print("⚠️ Bot to'xtatildi.")

if __name__ == "__main__":
    main()
