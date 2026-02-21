import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
import sqlite3
from dataclasses import dataclass
import json

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation
AMOUNT, DESCRIPTION, CATEGORY, DELETE_SELECTION = range(4)

# Categories
INCOME_CATEGORIES = ['💰 Ish haqi', '💼 Bonus', '🎁 Sovg\'a', '📱 Freelance', '🔄 Qaytarib berildi']
EXPENSE_CATEGORIES = ['🍽️ Ovqat', '🚖 Transport', '🛒 Kiyim', '📱 Internet', '🎮 Ko\'ngilochar', '🏠 Uy']

@dataclass
class Transaction:
    id: int
    amount: float
    description: str
    category: str
    type: str  # 'income' or 'expense'
    date: str
    user_id: int

class FinanceBot:
    def __init__(self):
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect('finance_bot.db')
        c = conn.cursor()
        
        # Create transactions table
        c.execute('''CREATE TABLE IF NOT EXISTS transactions
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     user_id INTEGER,
                     amount REAL,
                     description TEXT,
                     category TEXT,
                     type TEXT,
                     date TEXT)''')
        
        # Create users table for settings
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (user_id INTEGER PRIMARY KEY,
                     username TEXT,
                     first_name TEXT,
                     last_name TEXT,
                     registered_date TEXT)''')
        
        conn.commit()
        conn.close()
    
    def add_transaction(self, user_id: int, amount: float, description: str, category: str, trans_type: str):
        """Add a new transaction"""
        conn = sqlite3.connect('finance_bot.db')
        c = conn.cursor()
        
        date = datetime.now().strftime("%Y-%m-%d %H:%M")
        c.execute('''INSERT INTO transactions (user_id, amount, description, category, type, date)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                 (user_id, amount, description, category, trans_type, date))
        
        transaction_id = c.lastrowid
        conn.commit()
        conn.close()
        return transaction_id
    
    def get_user_balance(self, user_id: int) -> float:
        """Calculate user's current balance"""
        conn = sqlite3.connect('finance_bot.db')
        c = conn.cursor()
        
        # Get total income
        c.execute('''SELECT SUM(amount) FROM transactions 
                    WHERE user_id = ? AND type = 'income' ''', (user_id,))
        income = c.fetchone()[0] or 0
        
        # Get total expenses
        c.execute('''SELECT SUM(amount) FROM transactions 
                    WHERE user_id = ? AND type = 'expense' ''', (user_id,))
        expense = c.fetchone()[0] or 0
        
        conn.close()
        return income - expense
    
    def get_today_transactions(self, user_id: int) -> List[Transaction]:
        """Get today's transactions"""
        conn = sqlite3.connect('finance_bot.db')
        c = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute('''SELECT id, amount, description, category, type, date FROM transactions 
                    WHERE user_id = ? AND date LIKE ? ORDER BY date DESC''', 
                 (user_id, f"{today}%"))
        
        transactions = []
        for row in c.fetchall():
            transactions.append(Transaction(row[0], row[1], row[2], row[3], row[4], row[5], user_id))
        
        conn.close()
        return transactions
    
    def get_transaction_history(self, user_id: int, days: int = 7) -> List[Transaction]:
        """Get transaction history for last N days"""
        conn = sqlite3.connect('finance_bot.db')
        c = conn.cursor()
        
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        c.execute('''SELECT id, amount, description, category, type, date FROM transactions 
                    WHERE user_id = ? AND date >= ? ORDER BY date DESC''', 
                 (user_id, date_from))
        
        transactions = []
        for row in c.fetchall():
            transactions.append(Transaction(row[0], row[1], row[2], row[3], row[4], row[5], user_id))
        
        conn.close()
        return transactions
    
    def delete_transaction(self, user_id: int, transaction_id: int) -> bool:
        """Delete a transaction"""
        conn = sqlite3.connect('finance_bot.db')
        c = conn.cursor()
        
        c.execute('''DELETE FROM transactions WHERE id = ? AND user_id = ?''', 
                 (transaction_id, user_id))
        
        success = c.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def register_user(self, user_id: int, username: str, first_name: str, last_name: str = None):
        """Register or update user"""
        conn = sqlite3.connect('finance_bot.db')
        c = conn.cursor()
        
        date = datetime.now().strftime("%Y-%m-%d %H:%M")
        c.execute('''INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, registered_date)
                    VALUES (?, ?, ?, ?, ?)''',
                 (user_id, username, first_name, last_name, date))
        
        conn.commit()
        conn.close()

# Initialize bot
finance_bot = FinanceBot()

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    finance_bot.register_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = (
        f"👋 Assalomu alaykum, {user.first_name}!\n\n"
        "💰 Bu bot orqali kunlik daromad va xarajatlaringizni kuzatib boring.\n\n"
        "📌 Quyidagi tugmalardan foydalaning:"
    )
    
    keyboard = [
        [InlineKeyboardButton("➕ Daromad qo'shish", callback_data="add_income")],
        [InlineKeyboardButton("➖ Xarajat qo'shish", callback_data="add_expense")],
        [InlineKeyboardButton("📊 Balans", callback_data="show_balance")],
        [InlineKeyboardButton("📋 Bugungi operatsiyalar", callback_data="show_today")],
        [InlineKeyboardButton("📜 Tarix (7 kun)", callback_data="show_history")],
        [InlineKeyboardButton("❌ Operatsiyani o'chirish", callback_data="delete_transaction")],
        [InlineKeyboardButton("📈 Statistika", callback_data="show_stats")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "add_income":
        context.user_data['transaction_type'] = 'income'
        keyboard = []
        for cat in INCOME_CATEGORIES:
            keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat_income_{cat}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "💰 Daromad turini tanlang:",
            reply_markup=reply_markup
        )
        return CATEGORY
    
    elif query.data == "add_expense":
        context.user_data['transaction_type'] = 'expense'
        keyboard = []
        for cat in EXPENSE_CATEGORIES:
            keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat_expense_{cat}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "💸 Xarajat turini tanlang:",
            reply_markup=reply_markup
        )
        return CATEGORY
    
    elif query.data == "show_balance":
        balance = finance_bot.get_user_balance(query.from_user.id)
        
        # Get today's summary
        today_trans = finance_bot.get_today_transactions(query.from_user.id)
        today_income = sum(t.amount for t in today_trans if t.type == 'income')
        today_expense = sum(t.amount for t in today_trans if t.type == 'expense')
        
        text = (
            f"💰 <b>Sizning balansingiz</b>\n\n"
            f"💵 Jami balans: <b>{balance:,.0f} so'm</b>\n\n"
            f"📊 <b>Bugungi statistika:</b>\n"
            f"   ➕ Daromad: {today_income:,.0f} so'm\n"
            f"   ➖ Xarajat: {today_expense:,.0f} so'm\n"
            f"   📍 Farq: {today_income - today_expense:+,.0f} so'm"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data == "show_today":
        transactions = finance_bot.get_today_transactions(query.from_user.id)
        
        if not transactions:
            text = "📭 Bugun hech qanday operatsiya bo'lmagan."
        else:
            text = "📋 <b>Bugungi operatsiyalar:</b>\n\n"
            for t in transactions:
                emoji = "➕" if t.type == 'income' else "➖"
                text += f"{emoji} <b>{t.amount:,.0f} so'm</b> - {t.category}\n"
                if t.description:
                    text += f"   📝 {t.description}\n"
                text += f"   🕐 {t.date.split()[1]}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data == "show_history":
        transactions = finance_bot.get_transaction_history(query.from_user.id, 7)
        
        if not transactions:
            text = "📭 So'nggi 7 kun ichida hech qanday operatsiya bo'lmagan."
        else:
            text = "📜 <b>So'nggi 7 kunlik tarix:</b>\n\n"
            current_date = ""
            for t in transactions:
                date = t.date.split()[0]
                if date != current_date:
                    current_date = date
                    text += f"\n📅 <b>{date}</b>\n"
                
                emoji = "➕" if t.type == 'income' else "➖"
                text += f"  {emoji} {t.amount:,.0f} so'm - {t.category}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data == "show_stats":
        transactions = finance_bot.get_transaction_history(query.from_user.id, 30)
        
        total_income = sum(t.amount for t in transactions if t.type == 'income')
        total_expense = sum(t.amount for t in transactions if t.type == 'expense')
        
        # Category statistics
        income_by_cat = {}
        expense_by_cat = {}
        
        for t in transactions:
            if t.type == 'income':
                income_by_cat[t.category] = income_by_cat.get(t.category, 0) + t.amount
            else:
                expense_by_cat[t.category] = expense_by_cat.get(t.category, 0) + t.amount
        
        text = (
            f"📊 <b>Statistika (30 kun)</b>\n\n"
            f"💰 <b>Umumiy:</b>\n"
            f"   ➕ Daromad: {total_income:,.0f} so'm\n"
            f"   ➖ Xarajat: {total_expense:,.0f} so'm\n"
            f"   📍 Tejam: {total_income - total_expense:,.0f} so'm\n\n"
        )
        
        if expense_by_cat:
            text += "📉 <b>Xarajatlar bo'yicha:</b>\n"
            for cat, amount in sorted(expense_by_cat.items(), key=lambda x: x[1], reverse=True):
                percent = (amount / total_expense * 100) if total_expense > 0 else 0
                text += f"   {cat}: {amount:,.0f} so'm ({percent:.1f}%)\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data == "delete_transaction":
        transactions = finance_bot.get_transaction_history(query.from_user.id, 7)
        
        if not transactions:
            await query.edit_message_text(
                "📭 O'chirish uchun operatsiyalar mavjud emas.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")]])
            )
            return
        
        keyboard = []
        for t in transactions[:10]:  # Show last 10 transactions
            emoji = "➕" if t.type == 'income' else "➖"
            text = f"{emoji} {t.amount:,.0f} so'm - {t.category} ({t.date.split()[0]})"
            keyboard.append([InlineKeyboardButton(text, callback_data=f"del_{t.id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❌ O'chirmoqchi bo'lgan operatsiyangizni tanlang:",
            reply_markup=reply_markup
        )
        return DELETE_SELECTION
    
    elif query.data == "back_to_menu":
        await show_menu(query, context)
    
    elif query.data.startswith("del_"):
        transaction_id = int(query.data.split("_")[1])
        success = finance_bot.delete_transaction(query.from_user.id, transaction_id)
        
        if success:
            text = "✅ Operatsiya muvaffaqiyatli o'chirildi!"
        else:
            text = "❌ Operatsiyani o'chirishda xatolik yuz berdi."
        
        keyboard = [[InlineKeyboardButton("🔙 Menyu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    elif query.data.startswith("cat_"):
        parts = query.data.split("_")
        trans_type = parts[1]
        category = "_".join(parts[2:])
        
        context.user_data['category'] = category
        context.user_data['transaction_type'] = trans_type
        
        await query.edit_message_text(
            f"📝 {category} uchun miqdorni kiriting (so'm):"
        )
        return AMOUNT

async def show_menu(query, context):
    """Show main menu"""
    keyboard = [
        [InlineKeyboardButton("➕ Daromad qo'shish", callback_data="add_income")],
        [InlineKeyboardButton("➖ Xarajat qo'shish", callback_data="add_expense")],
        [InlineKeyboardButton("📊 Balans", callback_data="show_balance")],
        [InlineKeyboardButton("📋 Bugungi operatsiyalar", callback_data="show_today")],
        [InlineKeyboardButton("📜 Tarix (7 kun)", callback_data="show_history")],
        [InlineKeyboardButton("❌ Operatsiyani o'chirish", callback_data="delete_transaction")],
        [InlineKeyboardButton("📈 Statistika", callback_data="show_stats")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "💰 Asosiy menyu. Kerakli bo'limni tanlang:",
        reply_markup=reply_markup
    )

async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle amount input"""
    try:
        amount = float(update.message.text.replace(' ', ''))
        context.user_data['amount'] = amount
        
        await update.message.reply_text(
            "📝 Tavsif kiriting (yoki /skip ni bosing):"
        )
        return DESCRIPTION
    except ValueError:
        await update.message.reply_text(
            "❌ Noto'g'ri format. Iltimos, faqat son kiriting (masalan: 50000):"
        )
        return AMOUNT

async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle description input"""
    description = update.message.text
    context.user_data['description'] = description
    
    await save_transaction(update, context)
    return ConversationHandler.END

async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip description input"""
    context.user_data['description'] = ""
    await save_transaction(update, context)
    return ConversationHandler.END

async def save_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save transaction to database"""
    user_id = update.effective_user.id
    amount = context.user_data['amount']
    description = context.user_data['description']
    category = context.user_data['category']
    trans_type = context.user_data['transaction_type']
    
    transaction_id = finance_bot.add_transaction(user_id, amount, description, category, trans_type)
    
    emoji = "✅" if trans_type == 'income' else "➖"
    type_text = "daromad" if trans_type == 'income' else "xarajat"
    
    text = (
        f"{emoji} <b>{type_text.title()} qo'shildi!</b>\n\n"
        f"💰 Miqdor: <b>{amount:,.0f} so'm</b>\n"
        f"📁 Kategoriya: {category}\n"
    )
    if description:
        text += f"📝 Tavsif: {description}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Menyu", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    # Clear user data
    context.user_data.clear()

async def handle_delete_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle transaction deletion"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("del_"):
        transaction_id = int(query.data.split("_")[1])
        success = finance_bot.delete_transaction(query.from_user.id, transaction_id)
        
        if success:
            text = "✅ Operatsiya muvaffaqiyatli o'chirildi!"
        else:
            text = "❌ Operatsiyani o'chirishda xatolik yuz berdi."
        
        keyboard = [[InlineKeyboardButton("🔙 Menyu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text(
        "❌ Amal bekor qilindi.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menyu", callback_data="back_to_menu")]])
    )
    return ConversationHandler.END

def main():
    """Main function to run the bot"""
    # Replace 'YOUR_BOT_TOKEN' with your actual bot token
    application = Application.builder().token('8418511713:AAFkb9zPXNqdwaw4sb3AmjSLQkTKeBXRMVM').build()
    
    # Conversation handler for adding transactions
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^(add_income|add_expense)$')],
        states={
            CATEGORY: [CallbackQueryHandler(button_handler, pattern='^cat_')],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description),
                CommandHandler('skip', skip_description)
            ],
            DELETE_SELECTION: [CallbackQueryHandler(handle_delete_selection, pattern='^del_|back_to_menu$')]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Start the bot
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
