#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time
import threading

# Telegram bot uchun
import telebot
from telebot import types

# Konsol uchun ranglar
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class FinanceManager:
    def __init__(self):
        self.bot_token = "8418511713:AAFkb9zPXNqdwaw4sb3AmjSLQkTKeBXRMVM"
        self.bot = None
        self.user_id = 1  # Default user ID
        self.init_database()
        self.init_bot()
        
    def init_database(self):
        """Ma'lumotlar bazasini yaratish"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        # Foydalanuvchilar jadvali
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     username TEXT UNIQUE,
                     password TEXT,
                     bot_token TEXT,
                     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Kategoriyalar jadvali
        c.execute('''CREATE TABLE IF NOT EXISTS categories
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     user_id INTEGER,
                     name TEXT,
                     type TEXT,
                     icon TEXT,
                     FOREIGN KEY (user_id) REFERENCES users (id))''')
        
        # Transaksiyalar jadvali
        c.execute('''CREATE TABLE IF NOT EXISTS transactions
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     user_id INTEGER,
                     amount REAL,
                     description TEXT,
                     category TEXT,
                     type TEXT,
                     date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                     FOREIGN KEY (user_id) REFERENCES users (id))''')
        
        # Default user yaratish
        c.execute("INSERT OR IGNORE INTO users (id, username, password, bot_token) VALUES (1, 'admin', 'admin123', ?)",
                 (self.bot_token,))
        
        # Default kategoriyalar
        default_categories = [
            (1, '💰 Ish haqi', 'income', '💼'),
            (1, '💼 Bonus', 'income', '🎁'),
            (1, '📱 Freelance', 'income', '💻'),
            (1, '🎁 Sovg\'a', 'income', '🎀'),
            (1, '🍽️ Ovqat', 'expense', '🍔'),
            (1, '🚖 Transport', 'expense', '🚗'),
            (1, '🛒 Kiyim', 'expense', '👕'),
            (1, '🏠 Uy', 'expense', '🏡'),
            (1, '🎮 Ko\'ngilochar', 'expense', '🎮'),
            (1, '📞 Telefon', 'expense', '📱')
        ]
        
        for cat in default_categories:
            c.execute("INSERT OR IGNORE INTO categories (user_id, name, type, icon) VALUES (?, ?, ?, ?)",
                     cat)
        
        conn.commit()
        conn.close()
    
    def init_bot(self):
        """Telegram botni ishga tushirish"""
        try:
            self.bot = telebot.TeleBot(self.bot_token)
            self.setup_bot_handlers()
            print(f"{Colors.GREEN}✅ Telegram bot muvaffaqiyatli ishga tushdi!{Colors.END}")
            print(f"{Colors.CYAN}🤖 Bot username: @{self.bot.get_me().username}{Colors.END}")
        except Exception as e:
            print(f"{Colors.FAIL}❌ Bot ishga tushmadi: {e}{Colors.END}")
            self.bot = None
    
    def setup_bot_handlers(self):
        """Bot handlerlarini sozlash"""
        
        @self.bot.message_handler(commands=['start'])
        def send_welcome(message):
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            btn1 = types.InlineKeyboardButton("💰 Daromad", callback_data='income')
            btn2 = types.InlineKeyboardButton("💸 Xarajat", callback_data='expense')
            btn3 = types.InlineKeyboardButton("📊 Balans", callback_data='balance')
            btn4 = types.InlineKeyboardButton("📋 Bugun", callback_data='today')
            btn5 = types.InlineKeyboardButton("📜 Tarix", callback_data='history')
            btn6 = types.InlineKeyboardButton("📈 Statistika", callback_data='stats')
            
            markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
            
            welcome_text = (
                f"👋 Assalomu alaykum, {message.from_user.first_name}!\n\n"
                f"💰 Moliya hisobchisi botiga xush kelibsiz!\n\n"
                f"📌 Quyidagi tugmalardan foydalaning:"
            )
            
            self.bot.send_message(message.chat.id, welcome_text, reply_markup=markup)
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call):
            if call.data == 'income':
                self.show_categories(call.message, 'income')
            elif call.data == 'expense':
                self.show_categories(call.message, 'expense')
            elif call.data == 'balance':
                self.show_balance(call.message)
            elif call.data == 'today':
                self.show_today(call.message)
            elif call.data == 'history':
                self.show_history(call.message)
            elif call.data == 'stats':
                self.show_stats(call.message)
            elif call.data.startswith('cat_'):
                self.ask_amount(call.message, call.data)
            elif call.data == 'back':
                self.send_main_menu(call.message)
            elif call.data.startswith('del_'):
                self.delete_transaction(call.message, call.data)
            
            self.bot.answer_callback_query(call.id)
        
        @self.bot.message_handler(func=lambda message: True)
        def handle_message(message):
            if message.chat.id in self.user_states:
                if self.user_states[message.chat.id].get('awaiting_amount'):
                    self.save_transaction_amount(message)
                elif self.user_states[message.chat.id].get('awaiting_description'):
                    self.save_transaction_description(message)
    
    def user_states(self):
        """Foydalanuvchi holatlarini boshqarish"""
        if not hasattr(self, '_user_states'):
            self._user_states = {}
        return self._user_states
    
    def send_main_menu(self, message):
        """Asosiy menyuni yuborish"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("💰 Daromad", callback_data='income'),
            types.InlineKeyboardButton("💸 Xarajat", callback_data='expense'),
            types.InlineKeyboardButton("📊 Balans", callback_data='balance'),
            types.InlineKeyboardButton("📋 Bugun", callback_data='today'),
            types.InlineKeyboardButton("📜 Tarix", callback_data='history'),
            types.InlineKeyboardButton("📈 Statistika", callback_data='stats')
        )
        self.bot.send_message(message.chat.id, "📌 Asosiy menyu:", reply_markup=markup)
    
    def show_categories(self, message, trans_type):
        """Kategoriyalarni ko'rsatish"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        c.execute("SELECT name, icon FROM categories WHERE user_id=? AND type=?", (1, trans_type))
        categories = c.fetchall()
        conn.close()
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        for cat_name, icon in categories:
            markup.add(types.InlineKeyboardButton(
                f"{icon} {cat_name}", 
                callback_data=f"cat_{trans_type}_{cat_name}"
            ))
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data='back'))
        
        text = "💰 Kategoriyani tanlang:" if trans_type == 'income' else "💸 Kategoriyani tanlang:"
        self.bot.send_message(message.chat.id, text, reply_markup=markup)
    
    def ask_amount(self, message, callback_data):
        """Miqdorni so'rash"""
        chat_id = message.chat.id
        if chat_id not in self.user_states():
            self.user_states()[chat_id] = {}
        
        parts = callback_data.split('_')
        self.user_states()[chat_id]['type'] = parts[1]
        self.user_states()[chat_id]['category'] = parts[2]
        self.user_states()[chat_id]['awaiting_amount'] = True
        
        self.bot.send_message(chat_id, "💰 Miqdorni kiriting (so'm):")
    
    def save_transaction_amount(self, message):
        """Miqdorni saqlash va tavsif so'rash"""
        try:
            amount = float(message.text.replace(' ', ''))
            chat_id = message.chat.id
            
            self.user_states()[chat_id]['amount'] = amount
            self.user_states()[chat_id]['awaiting_amount'] = False
            self.user_states()[chat_id]['awaiting_description'] = True
            
            self.bot.send_message(chat_id, "📝 Tavsif kiriting (yoki 'skip' yozing):")
        except ValueError:
            self.bot.send_message(message.chat.id, "❌ Xato! Iltimos, faqat son kiriting:")
    
    def save_transaction_description(self, message):
        """Tavsifni saqlash va transaksiyani yakunlash"""
        chat_id = message.chat.id
        description = message.text if message.text.lower() != 'skip' else ''
        
        state = self.user_states()[chat_id]
        
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        c.execute('''INSERT INTO transactions (user_id, amount, description, category, type)
                    VALUES (?, ?, ?, ?, ?)''',
                 (1, state['amount'], description, state['category'], state['type']))
        conn.commit()
        conn.close()
        
        emoji = "✅" if state['type'] == 'income' else "➖"
        type_text = "daromad" if state['type'] == 'income' else "xarajat"
        
        self.bot.send_message(
            chat_id,
            f"{emoji} <b>{type_text.title()} qo'shildi!</b>\n\n"
            f"💰 Miqdor: <b>{state['amount']:,.0f} so'm</b>\n"
            f"📁 Kategoriya: {state['category']}\n"
            f"📝 Tavsif: {description or 'yo\'q'}",
            parse_mode='HTML'
        )
        
        # Holatni tozalash
        del self.user_states()[chat_id]
        self.send_main_menu(message)
    
    def show_balance(self, message):
        """Balansni ko'rsatish"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='income'", (1,))
        income = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='expense'", (1,))
        expense = c.fetchone()[0] or 0
        
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='income' AND date LIKE ?", 
                 (1, f"{today}%"))
        today_income = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='expense' AND date LIKE ?", 
                 (1, f"{today}%"))
        today_expense = c.fetchone()[0] or 0
        
        conn.close()
        
        balance = income - expense
        
        text = (
            f"💰 <b>SIZNING BALANSINGIZ</b>\n\n"
            f"💵 Jami balans: <b>{balance:+,.0f} so'm</b>\n\n"
            f"📊 <b>Bugungi statistika:</b>\n"
            f"   ➕ Daromad: {today_income:,.0f} so'm\n"
            f"   ➖ Xarajat: {today_expense:,.0f} so'm\n"
            f"   📍 Farq: {today_income - today_expense:+,.0f} so'm"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data='back'))
        
        self.bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=markup)
    
    def show_today(self, message):
        """Bugungi operatsiyalarni ko'rsatish"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute('''SELECT amount, description, category, type, 
                    strftime('%H:%M', date) as time 
                    FROM transactions 
                    WHERE user_id=? AND date LIKE ? 
                    ORDER BY date DESC''', (1, f"{today}%"))
        
        transactions = c.fetchall()
        conn.close()
        
        if not transactions:
            text = "📭 Bugun hech qanday operatsiya bo'lmagan."
        else:
            text = "📋 <b>BUGUNGI OPERATSIYALAR</b>\n\n"
            for amount, desc, cat, typ, time in transactions:
                emoji = "➕" if typ == 'income' else "➖"
                text += f"{emoji} <b>{amount:,.0f} so'm</b> - {cat}\n"
                if desc:
                    text += f"   📝 {desc}\n"
                text += f"   🕐 {time}\n\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data='back'))
        
        self.bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=markup)
    
    def show_history(self, message):
        """Operatsiyalar tarixini ko'rsatish"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        c.execute('''SELECT amount, description, category, type, 
                    strftime('%d.%m.%Y %H:%M', date) as datetime 
                    FROM transactions 
                    WHERE user_id=? 
                    ORDER BY date DESC 
                    LIMIT 20''', (1,))
        
        transactions = c.fetchall()
        conn.close()
        
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
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data='back'))
        
        self.bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=markup)
    
    def show_stats(self, message):
        """Statistikani ko'rsatish"""
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        # Umumiy statistika
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='income'", (1,))
        total_income = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='expense'", (1,))
        total_expense = c.fetchone()[0] or 0
        
        # Kategoriyalar bo'yicha
        c.execute('''SELECT category, SUM(amount), COUNT(*) 
                    FROM transactions 
                    WHERE user_id=? AND type='expense' 
                    GROUP BY category 
                    ORDER BY SUM(amount) DESC''', (1,))
        expense_cats = c.fetchall()
        
        conn.close()
        
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
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data='back'))
        
        self.bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=markup)
    
    def delete_transaction(self, message, callback_data):
        """Transaksiyani o'chirish"""
        # Bu funksiyani keyinroq qo'shamiz
        pass
    
    # ============ KONSOL INTERFEYSI ============
    
    def clear_screen(self):
        """Konsolni tozalash"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self):
        """Header chiqarish"""
        print(f"{Colors.HEADER}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}💰 MOLIYA HISOBCHISI v1.0{Colors.END}".center(60))
        print(f"{Colors.HEADER}{'='*60}{Colors.END}")
        print()
    
    def print_menu(self):
        """Asosiy menyuni chiqarish"""
        print(f"{Colors.BOLD}📌 ASOSIY MENYU:{Colors.END}")
        print()
        print(f"  {Colors.GREEN}1.{Colors.END} ➕ Daromad qo'shish")
        print(f"  {Colors.FAIL}2.{Colors.END} ➖ Xarajat qo'shish")
        print(f"  {Colors.CYAN}3.{Colors.END} 📊 Balans ko'rish")
        print(f"  {Colors.CYAN}4.{Colors.END} 📋 Bugungi operatsiyalar")
        print(f"  {Colors.CYAN}5.{Colors.END} 📜 Operatsiyalar tarixi")
        print(f"  {Colors.CYAN}6.{Colors.END} 📈 Statistika")
        print(f"  {Colors.WARNING}7.{Colors.END} 🗑️  Operatsiyani o'chirish")
        print(f"  {Colors.WARNING}8.{Colors.END} 🤖 Bot statusi")
        print(f"  {Colors.FAIL}9.{Colors.END} 🚪 Chiqish")
        print()
        print(f"{'='*60}")
    
    def add_transaction_console(self, trans_type):
        """Konsoldan transaksiya qo'shish"""
        self.clear_screen()
        self.print_header()
        
        type_name = "DAROMAD" if trans_type == 'income' else "XARAJAT"
        print(f"{Colors.BOLD}➕ {type_name} QO'SHISH{Colors.END}")
        print()
        
        # Kategoriyalarni olish
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        c.execute("SELECT name, icon FROM categories WHERE user_id=? AND type=?", (1, trans_type))
        categories = c.fetchall()
        conn.close()
        
        print(f"{Colors.BOLD}Kategoriyalar:{Colors.END}")
        for i, (cat_name, icon) in enumerate(categories, 1):
            print(f"  {i}. {icon} {cat_name}")
        print()
        
        try:
            # Kategoriya tanlash
            cat_choice = int(input("Kategoriya raqamini tanlang: ")) - 1
            if cat_choice < 0 or cat_choice >= len(categories):
                print(f"{Colors.FAIL}❌ Noto'g'ri tanlov!{Colors.END}")
                input("Davom etish uchun Enter bosing...")
                return
            
            category = categories[cat_choice][0]
            
            # Miqdor kiritish
            amount = float(input("💰 Miqdorni kiriting (so'm): ").replace(' ', ''))
            if amount <= 0:
                print(f"{Colors.FAIL}❌ Miqdor musbat bo'lishi kerak!{Colors.END}")
                input("Davom etish uchun Enter bosing...")
                return
            
            # Tavsif kiritish
            description = input("📝 Tavsif (ixtiyoriy): ").strip()
            
            # Saqlash
            conn = sqlite3.connect('finance_data.db')
            c = conn.cursor()
            c.execute('''INSERT INTO transactions (user_id, amount, description, category, type)
                        VALUES (?, ?, ?, ?, ?)''',
                     (1, amount, description, category, trans_type))
            conn.commit()
            conn.close()
            
            emoji = "✅" if trans_type == 'income' else "➖"
            print(f"\n{Colors.GREEN}{emoji} {type_name} muvaffaqiyatli qo'shildi!{Colors.END}")
            
        except ValueError:
            print(f"{Colors.FAIL}❌ Xato! Iltimos, to'g'ri ma'lumot kiriting.{Colors.END}")
        except Exception as e:
            print(f"{Colors.FAIL}❌ Xatolik: {e}{Colors.END}")
        
        input("\nDavom etish uchun Enter bosing...")
    
    def show_balance_console(self):
        """Konsolda balansni ko'rsatish"""
        self.clear_screen()
        self.print_header()
        
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        # Umumiy balans
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='income'", (1,))
        total_income = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='expense'", (1,))
        total_expense = c.fetchone()[0] or 0
        
        # Bugungi statistika
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='income' AND date LIKE ?", 
                 (1, f"{today}%"))
        today_income = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='expense' AND date LIKE ?", 
                 (1, f"{today}%"))
        today_expense = c.fetchone()[0] or 0
        
        conn.close()
        
        balance = total_income - total_expense
        
        print(f"{Colors.BOLD}💰 BALANS MA'LUMOTLARI{Colors.END}")
        print()
        print(f"  Jami balans: {Colors.BOLD}{balance:+,.0f} so'm{Colors.END}")
        print()
        print(f"  {Colors.GREEN}Jami daromad: {total_income:,.0f} so'm{Colors.END}")
        print(f"  {Colors.FAIL}Jami xarajat: {total_expense:,.0f} so'm{Colors.END}")
        print()
        print(f"{Colors.CYAN}📊 BUGUNGI STATISTIKA:{Colors.END}")
        print(f"  {Colors.GREEN}➨ Daromad: {today_income:,.0f} so'm{Colors.END}")
        print(f"  {Colors.FAIL}➨ Xarajat: {today_expense:,.0f} so'm{Colors.END}")
        print(f"  ➨ Farq: {today_income - today_expense:+,.0f} so'm")
        
        input("\nDavom etish uchun Enter bosing...")
    
    def show_today_console(self):
        """Konsolda bugungi operatsiyalarni ko'rsatish"""
        self.clear_screen()
        self.print_header()
        
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute('''SELECT amount, description, category, type, 
                    strftime('%H:%M', date) as time 
                    FROM transactions 
                    WHERE user_id=? AND date LIKE ? 
                    ORDER BY date DESC''', (1, f"{today}%"))
        
        transactions = c.fetchall()
        conn.close()
        
        print(f"{Colors.BOLD}📋 BUGUNGI OPERATSIYALAR{Colors.END}")
        print()
        
        if not transactions:
            print(f"{Colors.WARNING}📭 Bugun hech qanday operatsiya bo'lmagan.{Colors.END}")
        else:
            for amount, desc, cat, typ, time in transactions:
                if typ == 'income':
                    print(f"  {Colors.GREEN}➕ {amount:,.0f} so'm{Colors.END} - {cat}")
                else:
                    print(f"  {Colors.FAIL}➖ {amount:,.0f} so'm{Colors.END} - {cat}")
                if desc:
                    print(f"     📝 {desc}")
                print(f"     🕐 {time}")
                print()
        
        input("\nDavom etish uchun Enter bosing...")
    
    def show_history_console(self):
        """Konsolda operatsiyalar tarixini ko'rsatish"""
        self.clear_screen()
        self.print_header()
        
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        c.execute('''SELECT amount, description, category, type, 
                    strftime('%d.%m.%Y %H:%M', date) as datetime 
                    FROM transactions 
                    WHERE user_id=? 
                    ORDER BY date DESC 
                    LIMIT 30''', (1,))
        
        transactions = c.fetchall()
        conn.close()
        
        print(f"{Colors.BOLD}📜 SO'NGI 30 OPERATSIYA{Colors.END}")
        print()
        
        if not transactions:
            print(f"{Colors.WARNING}📭 Hech qanday operatsiya topilmadi.{Colors.END}")
        else:
            for amount, desc, cat, typ, dt in transactions:
                if typ == 'income':
                    print(f"  {Colors.GREEN}➕ {amount:,.0f} so'm{Colors.END} - {cat}")
                else:
                    print(f"  {Colors.FAIL}➖ {amount:,.0f} so'm{Colors.END} - {cat}")
                print(f"     🕐 {dt}")
                if desc:
                    print(f"     📝 {desc}")
                print()
        
        input("\nDavom etish uchun Enter bosing...")
    
    def show_stats_console(self):
        """Konsolda statistikani ko'rsatish"""
        self.clear_screen()
        self.print_header()
        
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        # Umumiy statistika
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='income'", (1,))
        total_income = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='expense'", (1,))
        total_expense = c.fetchone()[0] or 0
        
        # Kategoriyalar bo'yicha
        c.execute('''SELECT category, SUM(amount), COUNT(*) 
                    FROM transactions 
                    WHERE user_id=? AND type='expense' 
                    GROUP BY category 
                    ORDER BY SUM(amount) DESC''', (1,))
        expense_cats = c.fetchall()
        
        # Oylik statistika
        c.execute('''SELECT strftime('%Y-%m', date) as month,
                           SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
                           SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
                    FROM transactions
                    WHERE user_id=?
                    GROUP BY month
                    ORDER BY month DESC
                    LIMIT 6''', (1,))
        monthly_stats = c.fetchall()
        
        conn.close()
        
        print(f"{Colors.BOLD}📊 STATISTIKA{Colors.END}")
        print()
        print(f"{Colors.CYAN}UMUMIY:{Colors.END}")
        print(f"  {Colors.GREEN}Jami daromad: {total_income:,.0f} so'm{Colors.END}")
        print(f"  {Colors.FAIL}Jami xarajat: {total_expense:,.0f} so'm{Colors.END}")
        print(f"  {Colors.BOLD}Tejam: {total_income - total_expense:+,.0f} so'm{Colors.END}")
        print()
        
        if expense_cats:
            print(f"{Colors.CYAN}XARAJATLAR KATEGORIYALARI:{Colors.END}")
            for cat, amount, count in expense_cats:
                percent = (amount / total_expense * 100) if total_expense > 0 else 0
                bar = "█" * int(percent / 4)
                print(f"  {cat}:")
                print(f"    {bar} {amount:,.0f} so'm ({percent:.1f}%) - {count} marta")
            print()
        
        if monthly_stats:
            print(f"{Colors.CYAN}OXIRGI 6 OY:{Colors.END}")
            for month, income, expense in monthly_stats:
                year, month_num = month.split('-')
                month_names = ['Yan', 'Fev', 'Mar', 'Apr', 'May', 'Iyun',
                              'Iyul', 'Avg', 'Sen', 'Okt', 'Noy', 'Dek']
                month_name = month_names[int(month_num) - 1]
                print(f"  {month_name} {year}: {Colors.GREEN}+{income:,.0f}{Colors.END} | {Colors.FAIL}-{expense:,.0f}{Colors.END} = {income - expense:+,.0f}")
        
        input("\nDavom etish uchun Enter bosing...")
    
    def delete_transaction_console(self):
        """Konsoldan operatsiyani o'chirish"""
        self.clear_screen()
        self.print_header()
        
        conn = sqlite3.connect('finance_data.db')
        c = conn.cursor()
        
        c.execute('''SELECT id, amount, description, category, type, 
                    strftime('%d.%m.%Y %H:%M', date) as datetime 
                    FROM transactions 
                    WHERE user_id=? 
                    ORDER BY date DESC 
                    LIMIT 20''', (1,))
        
        transactions = c.fetchall()
        conn.close()
        
        if not transactions:
            print(f"{Colors.WARNING}📭 Hech qanday operatsiya topilmadi.{Colors.END}")
            input("Davom etish uchun Enter bosing...")
            return
        
        print(f"{Colors.BOLD}🗑️ OPERATSIYANI O'CHIRISH{Colors.END}")
        print()
        print("So'ngi 20 operatsiya:")
        print()
        
        for i, (tid, amount, desc, cat, typ, dt) in enumerate(transactions, 1):
            if typ == 'income':
                print(f"  {i}. {Colors.GREEN}[ID: {tid}] {amount:,.0f} so'm - {cat}{Colors.END}")
            else:
                print(f"  {i}. {Colors.FAIL}[ID: {tid}] {amount:,.0f} so'm - {cat}{Colors.END}")
            print(f"     📅 {dt}")
            if desc:
                print(f"     📝 {desc}")
            print()
        
        try:
            choice = input("O'chirmoqchi bo'lgan operatsiya raqamini kiriting (0 - bekor qilish): ")
            if choice == '0':
                return
            
            idx = int(choice) - 1
            if 0 <= idx < len(transactions):
                tid = transactions[idx][0]
                
                confirm = input(f"Haqiqatan ham bu operatsiyani o'chirmoqchimisiz? (ha/yo'q): ")
                if confirm.lower() == 'ha':
                    conn = sqlite3.connect('finance_data.db')
                    c = conn.cursor()
                    c.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (tid, 1))
                    conn.commit()
                    conn.close()
                    
                    print(f"{Colors.GREEN}✅ Operatsiya muvaffaqiyatli o'chirildi!{Colors.END}")
                else:
                    print(f"{Colors.WARNING}❌ Bekor qilindi.{Colors.END}")
            else:
                print(f"{Colors.FAIL}❌ Noto'g'ri tanlov!{Colors.END}")
        
        except ValueError:
            print(f"{Colors.FAIL}❌ Noto'g'ri format!{Colors.END}")
        except Exception as e:
            print(f"{Colors.FAIL}❌ Xatolik: {e}{Colors.END}")
        
        input("\nDavom etish uchun Enter bosing...")
    
    def show_bot_status(self):
        """Bot statusini ko'rsatish"""
        self.clear_screen()
        self.print_header()
        
        print(f"{Colors.BOLD}🤖 TELEGRAM BOT STATUSI{Colors.END}")
        print()
        
        if self.bot:
            try:
                bot_info = self.bot.get_me()
                print(f"  {Colors.GREEN}✅ Bot faol{Colors.END}")
                print(f"  🤖 Nomi: {bot_info.first_name}")
                print(f"  🔑 Username: @{bot_info.username}")
                print(f"  🆔 ID: {bot_info.id}")
                print(f"  📦 Token: {self.bot_token[:10]}...{self.bot_token[-5:]}")
            except:
                print(f"  {Colors.FAIL}❌ Bot ishlamayapti{Colors.END}")
                print(f"  📦 Token: {self.bot_token[:10]}...{self.bot_token[-5:]}")
        else:
            print(f"  {Colors.FAIL}❌ Bot ishga tushmagan{Colors.END}")
            print(f"  📦 Token: {self.bot_token[:10]}...{self.bot_token[-5:]}")
        
        print()
        print(f"{Colors.CYAN}📌 Botdan foydalanish:{Colors.END}")
        print("  1. Telegramda @{} ni qidiring".format(self.bot.get_me().username if self.bot else "bot"))
        print("  2. /start buyrug'ini yuboring")
        print("  3. Tugmalar orqali operatsiyalarni bajaring")
        
        input("\nDavom etish uchun Enter bosing...")
    
    def run_bot_thread(self):
        """Botni alohida threadda ishga tushirish"""
        if self.bot:
            try:
                self.bot.infinity_polling()
            except Exception as e:
                print(f"{Colors.FAIL}❌ Bot xatosi: {e}{Colors.END}")
    
    def run(self):
        """Asosiy dastur"""
        # Botni alohida threadda ishga tushirish
        if self.bot:
            bot_thread = threading.Thread(target=self.run_bot_thread, daemon=True)
            bot_thread.start()
        
        while True:
            self.clear_screen()
            self.print_header()
            self.print_menu()
            
            choice = input(f"{Colors.BOLD}Tanlovingiz: {Colors.END}")
            
            if choice == '1':
                self.add_transaction_console('income')
            elif choice == '2':
                self.add_transaction_console('expense')
            elif choice == '3':
                self.show_balance_console()
            elif choice == '4':
                self.show_today_console()
            elif choice == '5':
                self.show_history_console()
            elif choice == '6':
                self.show_stats_console()
            elif choice == '7':
                self.delete_transaction_console()
            elif choice == '8':
                self.show_bot_status()
            elif choice == '9':
                print(f"\n{Colors.GREEN}👋 Xayr!{Colors.END}")
                sys.exit(0)
            else:
                print(f"{Colors.FAIL}❌ Noto'g'ri tanlov!{Colors.END}")
                time.sleep(1)

if __name__ == "__main__":
    try:
        app = FinanceManager()
        app.run()
    except KeyboardInterrupt:
        print(f"\n{Colors.GREEN}👋 Dastur to'xtatildi.{Colors.END}")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.FAIL}❌ Xatolik: {e}{Colors.END}")
        input("Davom etish uchun Enter bosing...")
