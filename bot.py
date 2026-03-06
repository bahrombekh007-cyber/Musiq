import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes
import sqlite3
from datetime import datetime, timedelta
import random
import string
import json

# Holatlar
USERNAME, CHECK_PHOTO, ADMIN_SEARCH, ADMIN_BROADCAST, ADMIN_BALANCE = range(5)

# Admin ID (o'zingizning ID ingizni yozing)
ADMIN_ID = 8735360012  # BU YERGA O'Z IDINGIZNI YOZING

# To'lov ma'lumotlari
PAYMENT_CARD = "9860350146763007"
PAYMENT_NAME = "Rustamov Bahrombek"
PAYMENT_BANK = "TBS Bank"

# Referral mukofoti
REFERRAL_BONUS = 5000

# Tariflar
TARIFFS = {
    "tg": {
        "1oy": {"name": "📱 Telegram 1 oylik", "price": 25000, "days": 30, "emoji": "📱"},
        "2oy": {"name": "📱 Telegram 2 oylik", "price": 49000, "days": 60, "emoji": "📱"},
        "3oy": {"name": "📱 Telegram 3 oylik", "price": 73000, "days": 90, "emoji": "📱"},
        "6oy": {"name": "📱 Telegram 6 oylik", "price": 140000, "days": 180, "emoji": "📱"},
        "1yil": {"name": "📱 Telegram 1 yillik", "price": 220000, "days": 365, "emoji": "📱"}
    },
    "insta": {
        "6oy": {"name": "📸 Instagram 6 oylik", "price": 36000, "days": 180, "emoji": "📸"},
        "1yil": {"name": "📸 Instagram 1 yillik", "price": 72000, "days": 365, "emoji": "📸"}
    }
}

# Ma'lumotlar bazasini sozlash
def init_db():
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    # Foydalanuvchilar
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  full_name TEXT,
                  referral_code TEXT UNIQUE,
                  referred_by INTEGER,
                  balance REAL DEFAULT 0,
                  total_earned REAL DEFAULT 0,
                  is_blocked INTEGER DEFAULT 0,
                  registered_date TEXT,
                  last_active TEXT)''')
    
    # Premium xizmatlar
    c.execute('''CREATE TABLE IF NOT EXISTS premiums
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  platform TEXT,
                  tariff TEXT,
                  price INTEGER,
                  days INTEGER,
                  start_date TEXT,
                  end_date TEXT,
                  status TEXT DEFAULT 'active',
                  payment_method TEXT)''')
    
    # To'lovlar
    c.execute('''CREATE TABLE IF NOT EXISTS payments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  payment_id TEXT UNIQUE,
                  amount REAL,
                  check_photo_id TEXT,
                  status TEXT DEFAULT 'pending',
                  date TEXT,
                  platform TEXT,
                  tariff TEXT,
                  username TEXT,
                  payment_type TEXT DEFAULT 'card')''')
    
    # Referal to'lovlar
    c.execute('''CREATE TABLE IF NOT EXISTS referral_payments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount REAL,
                  from_user_id INTEGER,
                  date TEXT,
                  status TEXT DEFAULT 'pending')''')
    
    # Admin sozlamalari
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY,
                  value TEXT)''')
    
    # Statistikalar
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (date TEXT PRIMARY KEY,
                  new_users INTEGER DEFAULT 0,
                  payments INTEGER DEFAULT 0,
                  income REAL DEFAULT 0)''')
    
    conn.commit()
    conn.close()

def generate_referral_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# Foydalanuvchini ro'yxatdan o'tkazish
async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    c.execute('SELECT * FROM users WHERE user_id=?', (user.id,))
    existing_user = c.fetchone()
    
    if not existing_user:
        referral_code = generate_referral_code()
        c.execute('''INSERT INTO users (user_id, username, full_name, referral_code, registered_date, last_active)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (user.id, user.username, user.full_name, referral_code, datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
        
        # Statistika yangilash
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute('INSERT OR IGNORE INTO stats (date) VALUES (?)', (today,))
        c.execute('UPDATE stats SET new_users = new_users + 1 WHERE date = ?', (today,))
        conn.commit()
        
        # Referralni tekshirish
        if context.args and len(context.args) > 0:
            ref_code = context.args[0]
            c.execute('SELECT user_id FROM users WHERE referral_code=?', (ref_code,))
            referrer = c.fetchone()
            if referrer:
                c.execute('UPDATE users SET referred_by=? WHERE user_id=?', (referrer[0], user.id))
                conn.commit()
                
                try:
                    await context.bot.send_message(
                        chat_id=referrer[0],
                        text=f"🎉 *Yangi referal!*\n\n👤 {user.full_name} sizning havolangiz orqali ro'yxatdan o'tdi!\n💰 Premium xarid qilganda {REFERRAL_BONUS} so'm olasiz!",
                        parse_mode='Markdown'
                    )
                except:
                    pass
    else:
        # Oxirgi faollikni yangilash
        c.execute('UPDATE users SET last_active=? WHERE user_id=?', (datetime.now().isoformat(), user.id))
        conn.commit()
    
    conn.close()

# Asosiy menyu
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Balansni olish
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM users WHERE user_id=?', (user.id,))
    result = c.fetchone()
    balance = result[0] if result else 0
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("🛍 Premium sotib olish", callback_data="buy_premium")],
        [InlineKeyboardButton("👤 Mening premiumlarim", callback_data="my_premiums")],
        [InlineKeyboardButton(f"💰 Balans: {balance:,.0f} so'm", callback_data="balance")],
        [InlineKeyboardButton("👥 Referal tizim", callback_data="referral")],
        [InlineKeyboardButton("📞 Admin bilan bog'lanish", callback_data="contact_admin")],
        [InlineKeyboardButton("ℹ️ Yordam", callback_data="help")]
    ]
    
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👨‍💼 Admin panel ⚡", callback_data="admin")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"👋 *Xush kelibsiz, {user.full_name}!*\n\n"
        f"🤖 Bu bot orqali Telegram va Instagram uchun premium xizmatlarni xarid qilishingiz mumkin.\n"
        f"💰 Do'stlaringizni taklif qiling va har bir xarid uchun *{REFERRAL_BONUS:,} so'm* mukofot oling!\n\n"
        f"📊 *Statistika:*\n"
        f"👥 Referallaringiz: {get_referral_count(user.id)} ta\n"
        f"💳 Balansingiz: {balance:,.0f} so'm"
    )
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

def get_referral_count(user_id):
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users WHERE referred_by=?', (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

# Referal tizim
async def referral_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    # Ma'lumotlarni olish
    c.execute('SELECT referral_code, balance, total_earned FROM users WHERE user_id=?', (user_id,))
    user_data = c.fetchone()
    
    c.execute('SELECT COUNT(*) FROM users WHERE referred_by=?', (user_id,))
    referrals_count = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM referral_payments WHERE user_id=? AND status="paid"', (user_id,))
    paid_referrals = c.fetchone()[0]
    
    c.execute('SELECT SUM(amount) FROM referral_payments WHERE user_id=? AND status="paid"', (user_id,))
    total_earned = c.fetchone()[0] or 0
    
    conn.close()
    
    bot = await context.bot.get_me()
    referral_link = f"https://t.me/{bot.username}?start={user_data[0]}"
    
    text = (
        f"👥 *Referal tizim*\n\n"
        f"🔗 *Sizning havolangiz:*\n"
        f"`{referral_link}`\n\n"
        f"📊 *Statistika:*\n"
        f"• Jami referallar: {referrals_count} ta\n"
        f"• Faol referallar: {paid_referrals} ta\n"
        f"• Umumiy daromad: {total_earned:,.0f} so'm\n"
        f"• Joriy balans: {user_data[1]:,.0f} so'm\n\n"
        f"💰 *Qanday ishlaydi?*\n"
        f"1. Havolani do'stlaringizga yuboring\n"
        f"2. Ular ro'yxatdan o'tadi\n"
        f"3. Premium xarid qilganda siz {REFERRAL_BONUS:,} so'm olasiz\n"
        f"4. Pul balansingizga tushadi va premium olishda ishlata olasiz"
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 Referallar ro'yxati", callback_data="referral_list")],
        [InlineKeyboardButton("💸 Balansni premiumga ishlatish", callback_data="use_balance")],
        [InlineKeyboardButton("◀️ Ortga", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# Referallar ro'yxati
async def referral_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    c.execute('''SELECT u.full_name, u.username, u.registered_date,
                        (SELECT COUNT(*) FROM premiums WHERE user_id=u.user_id) as purchases
                 FROM users u WHERE u.referred_by=? ORDER BY u.registered_date DESC''', (user_id,))
    referrals = c.fetchall()
    
    conn.close()
    
    if not referrals:
        text = "📭 Sizda hali referallar yo'q.\n\nDo'stlaringizni taklif qiling va pul ishlang!"
    else:
        text = "📋 *Referallaringiz:*\n\n"
        for i, ref in enumerate(referrals, 1):
            name = ref[0]
            username = f"@{ref[1]}" if ref[1] else "username yo'q"
            date = datetime.fromisoformat(ref[2]).strftime('%d.%m.%Y')
            purchases = ref[3]
            status = "✅ Faol" if purchases > 0 else "⏳ Kutilmoqda"
            text += f"{i}. {name} ({username})\n   📅 {date} | {status}\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Ortga", callback_data="referral")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# Balansdan premium olish
async def use_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM users WHERE user_id=?', (user_id,))
    balance = c.fetchone()[0]
    conn.close()
    
    if balance < 6000:  # Eng arzon tarif
        await query.edit_message_text(
            "❌ Balansingizda premium olish uchun yetarli mablag' yo'q!\n"
            f"💰 Joriy balans: {balance:,.0f} so'm\n"
            f"💳 Minimal tarif: 6,000 so'm\n\n"
            "Do'stlaringizni taklif qilib balansingizni oshiring!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Ortga", callback_data="referral")]])
        )
        return
    
    # Platforma tanlash
    keyboard = [
        [InlineKeyboardButton("📱 Telegram Premium", callback_data="balance_platform_tg")],
        [InlineKeyboardButton("📸 Instagram Premium", callback_data="balance_platform_insta")],
        [InlineKeyboardButton("◀️ Ortga", callback_data="referral")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"💰 *Balansdan premium olish*\n\n"
        f"💳 Sizning balansingiz: {balance:,.0f} so'm\n\n"
        f"Platformani tanlang:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Balansdan platforma tanlash
async def balance_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    platform = query.data.replace("balance_platform_", "")
    context.user_data['balance_platform'] = platform
    context.user_data['payment_method'] = 'balance'
    
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM users WHERE user_id=?', (user_id,))
    balance = c.fetchone()[0]
    conn.close()
    
    # Mavjud tariflarni ko'rsatish
    keyboard = []
    for key, value in TARIFFS[platform].items():
        if value['price'] <= balance:
            keyboard.append([InlineKeyboardButton(
                f"{value['name']} - {value['price']:,.0f} so'm ✅",
                callback_data=f"balance_tariff_{key}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                f"{value['name']} - {value['price']:,.0f} so'm ❌",
                callback_data="no_balance"
            )])
    
    keyboard.append([InlineKeyboardButton("◀️ Ortga", callback_data="use_balance")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📦 *Tarifni tanlang*\n\n"
        f"💳 Balans: {balance:,.0f} so'm\n"
        f"✅ - Sotib olish mumkin\n"
        f"❌ - Balans yetarli emas",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Balansdan tarif tanlash
async def balance_tariff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "no_balance":
        await query.answer("❌ Balans yetarli emas!", show_alert=True)
        return
    
    tariff_key = query.data.replace("balance_tariff_", "")
    platform = context.user_data['balance_platform']
    tariff = TARIFFS[platform][tariff_key]
    
    context.user_data['tariff'] = tariff_key
    context.user_data['price'] = tariff['price']
    context.user_data['days'] = tariff['days']
    
    await query.edit_message_text(
        f"📦 *Tanlangan tarif:*\n"
        f"{tariff['name']}\n"
        f"💰 Narxi: {tariff['price']:,.0f} so'm\n"
        f"⏱ Muddati: {tariff['days']} kun\n\n"
        f"📝 Iltimos, Telegram instagram usernameingizni yuboring (@username):",
        parse_mode='Markdown'
    )
    return USERNAME

# Username ni olish (balans uchun)
async def get_username_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text
    context.user_data['username'] = username
    
    user_id = update.effective_user.id
    platform = context.user_data['balance_platform']
    tariff_key = context.user_data['tariff']
    price = context.user_data['price']
    days = context.user_data['days']
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    # Balansni tekshirish
    c.execute('SELECT balance FROM users WHERE user_id=?', (user_id,))
    balance = c.fetchone()[0]
    
    if balance < price:
        await update.message.reply_text("❌ Balans yetarli emas!")
        conn.close()
        return ConversationHandler.END
    
    # Balansdan yechish
    new_balance = balance - price
    c.execute('UPDATE users SET balance=? WHERE user_id=?', (new_balance, user_id))
    
    # Premium qo'shish
    start_date = datetime.now()
    end_date = start_date + timedelta(days=days)
    
    c.execute('''INSERT INTO premiums (user_id, platform, tariff, price, days, start_date, end_date, payment_method)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, platform, tariff_key, price, days, start_date.isoformat(), end_date.isoformat(), 'balance'))
    
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ *Premium muvaffaqiyatli faollashtirildi!*\n\n"
        f"📱 {TARIFFS[platform][tariff_key]['name']}\n"
        f"💰 To'lov: {price:,.0f} so'm (balansdan yechildi)\n"
        f"💳 Qoldiq balans: {new_balance:,.0f} so'm\n"
        f"📅 Tugash sanasi: {end_date.strftime('%d.%m.%Y')}\n\n"
        f"Rahmat!",
        parse_mode='Markdown'
    )
    
    await show_main_menu(update, context)
    return ConversationHandler.END

# Premium sotib olish (karta orqali)
async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['payment_method'] = 'card'
    
    keyboard = [
        [InlineKeyboardButton("📱 Telegram Premium", callback_data="platform_tg")],
        [InlineKeyboardButton("📸 Instagram Premium", callback_data="platform_insta")],
        [InlineKeyboardButton("◀️ Ortga", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🛍 *Premium sotib olish*\n\n"
        "Platformani tanlang:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Platforma tanlash (karta)
async def select_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    platform = query.data.replace("platform_", "")
    context.user_data['platform'] = platform
    
    keyboard = []
    for key, value in TARIFFS[platform].items():
        keyboard.append([InlineKeyboardButton(
            f"{value['name']} - {value['price']:,.0f} so'm",
            callback_data=f"tariff_{key}"
        )])
    keyboard.append([InlineKeyboardButton("◀️ Ortga", callback_data="buy_premium")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📦 *Tarifni tanlang:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Tarif tanlash (karta)
async def select_tariff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    tariff_key = query.data.replace("tariff_", "")
    platform = context.user_data['platform']
    tariff = TARIFFS[platform][tariff_key]
    
    context.user_data['tariff'] = tariff_key
    context.user_data['price'] = tariff['price']
    context.user_data['days'] = tariff['days']
    
    await query.edit_message_text(
        f"📦 *Tanlangan tarif:*\n"
        f"{tariff['name']}\n"
        f"💰 Narxi: {tariff['price']:,.0f} so'm\n"
        f"⏱ Muddati: {tariff['days']} kun\n\n"
        f"📝 Iltimos, Telegram instagram usernameingizni yuboring (@username):",
        parse_mode='Markdown'
    )
    return USERNAME

# Username ni olish (karta)
async def get_username_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text
    context.user_data['username'] = username
    
    payment_info = (
        f"💳 *To'lov ma'lumotlari:*\n\n"
        f"🏦 Karta: `{PAYMENT_CARD}`\n"
        f"👤 Ism: {PAYMENT_NAME}\n"
        f"🏛 Bank: {PAYMENT_BANK}\n"
        f"💰 Summa: {context.user_data['price']:,.0f} so'm\n\n"
        f"📱 Xizmat: {TARIFFS[context.user_data['platform']][context.user_data['tariff']]['name']}\n"
        f"👤 Username: @{username}\n\n"
        f"✅ To'lovni amalga oshirib, chekni (skrinshot) yuboring!"
    )
    
    await update.message.reply_text(payment_info, parse_mode='Markdown')
    await update.message.reply_text("📸 Iltimos, to'lov chekini (skrinshot) yuboring:")
    return CHECK_PHOTO

# Chekni qabul qilish
async def get_check_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Iltimos, rasm yuboring!")
        return CHECK_PHOTO
    
    photo = update.message.photo[-1]
    photo_id = photo.file_id
    
    payment_id = f"PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    c.execute('''INSERT INTO payments (user_id, payment_id, amount, check_photo_id, date, platform, tariff, username)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (update.effective_user.id, payment_id, context.user_data['price'], 
               photo_id, datetime.now().isoformat(), context.user_data['platform'],
               context.user_data['tariff'], context.user_data['username']))
    
    conn.commit()
    conn.close()
    
    # Admin panelga yuborish
    user = update.effective_user
    admin_text = (
        f"🆕 *Yangi to'lov!*\n\n"
        f"🆔 *ID:* `{payment_id}`\n"
        f"👤 *Foydalanuvchi:* @{user.username or 'username7155'}\n"
        f"👤 *Ism:* {user.full_name}\n"
        f"🆔 *User ID:* `{user.id}`\n"
        f"💰 *Summa:* {context.user_data['price']:,.0f} so'm\n"
        f"📱 *Xizmat:* {TARIFFS[context.user_data['platform']][context.user_data['tariff']]['name']}\n"
        f"👤 *Username:* @{context.user_data['username']}\n"
        f"📅 *Sana:* {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"👇 *Tasdiqlash uchun tugmalar:*"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{payment_id}"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"reject_{payment_id}")
        ],
        [InlineKeyboardButton("👤 Foydalanuvchi profili", callback_data=f"user_{user.id}")]
    ])
    
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=admin_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    
    await update.message.reply_text(
        "✅ *Chek adminga yuborildi!*\n\n"
        "⏳ Tez orada premium xizmatingiz faollashtiriladi.\n"
        "📞 Agar uzoq vaqt ketayotgan bo'lsa, admin bilan bog'lanishingiz mumkin.",
        parse_mode='Markdown'
    )
    
    await show_main_menu(update, context)
    return ConversationHandler.END

# ==================== ADMIN PANEL ====================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Zamonaviy admin panel"""
    
    if update.effective_user.id != ADMIN_ID:
        if update.callback_query:
            await update.callback_query.answer("❌ Siz admin emassiz!", show_alert=True)
        else:
            await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    # Statistikani olish
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    # Umumiy statistika
    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM users WHERE DATE(registered_date) = DATE("now")')
    new_users_today = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM premiums WHERE status="active"')
    active_premiums = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM payments WHERE status="pending"')
    pending_payments = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM payments WHERE status="approved" AND DATE(date) = DATE("now")')
    payments_today = c.fetchone()[0]
    
    c.execute('SELECT SUM(amount) FROM payments WHERE status="approved"')
    total_income = c.fetchone()[0] or 0
    
    c.execute('SELECT SUM(amount) FROM payments WHERE status="approved" AND DATE(date) = DATE("now")')
    income_today = c.fetchone()[0] or 0
    
    c.execute('SELECT SUM(balance) FROM users')
    total_balance = c.fetchone()[0] or 0
    
    c.execute('SELECT COUNT(*) FROM users WHERE is_blocked=1')
    blocked_users = c.fetchone()[0]
    
    conn.close()
    
    # Admin panel UI
    text = (
        f"👨‍💼 *ADMIN PANEL* ⚡\n\n"
        f"📊 *UMUMIY STATISTIKA*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👥 Jami foydalanuvchilar: `{total_users}`\n"
        f"🆕 Yangi (bugun): `{new_users_today}`\n"
        f"🚫 Bloklangan: `{blocked_users}`\n\n"
        f"💎 *PREMIUMLAR*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"✅ Faol premiumlar: `{active_premiums}`\n"
        f"⏳ Kutilayotgan to'lovlar: `{pending_payments}`\n"
        f"💳 To'lovlar (bugun): `{payments_today}`\n\n"
        f"💰 *MOLIYA*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💵 Umumiy daromad: `{total_income:,.0f} so'm`\n"
        f"📈 Daromad (bugun): `{income_today:,.0f} so'm`\n"
        f"💳 Foydalanuvchi balanslari: `{total_balance:,.0f} so'm`\n\n"
        f"⚙️ *BOSHQARUV*"
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 TO'LOVLAR", callback_data="admin_payments")],
        [InlineKeyboardButton("👥 FOYDALANUVCHILAR", callback_data="admin_users")],
        [InlineKeyboardButton("📊 STATISTIKA", callback_data="admin_stats")],
        [InlineKeyboardButton("📨 XABAR YUBORISH", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⚙️ SOZLAMALAR", callback_data="admin_settings")],
        [InlineKeyboardButton("📤 EKSPORT", callback_data="admin_export")],
        [InlineKeyboardButton("◀️ CHIQISH", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# Admin - To'lovlar boshqaruvi
async def admin_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    keyboard = [
        [InlineKeyboardButton("⏳ Kutilayotgan to'lovlar", callback_data="admin_payments_pending")],
        [InlineKeyboardButton("✅ Tasdiqlangan to'lovlar", callback_data="admin_payments_approved")],
        [InlineKeyboardButton("❌ Bekor qilingan to'lovlar", callback_data="admin_payments_rejected")],
        [InlineKeyboardButton("📊 To'lov statistikasi", callback_data="admin_payments_stats")],
        [InlineKeyboardButton("◀️ Ortga", callback_data="admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📋 *TO'LOV BOSHQARUVI*\n\n"
        "Bo'limni tanlang:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Admin - Kutilayotgan to'lovlar
async def admin_payments_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    c.execute('''SELECT payment_id, user_id, amount, date, platform, username 
                 FROM payments WHERE status="pending" ORDER BY date DESC LIMIT 10''')
    payments = c.fetchall()
    conn.close()
    
    if not payments:
        await query.edit_message_text(
            "✅ Kutilayotgan to'lovlar yo'q!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Ortga", callback_data="admin_payments")]])
        )
        return
    
    text = "⏳ *Kutilayotgan to'lovlar:*\n\n"
    for p in payments:
        text += f"🆔 `{p[0]}`\n👤 User: {p[1]}\n💰 {p[3][:10]}: {p[2]:,.0f} so'm\n📱 {p[4]}\n\n"
    
    text += "🔍 Batafsil ko'rish uchun to'lov ID sini bosing:"
    
    # To'lovlar ro'yxati
    keyboard = []
    for p in payments[:5]:
        keyboard.append([InlineKeyboardButton(f"💰 {p[2]:,.0f} so'm - {p[3][:10]}", callback_data=f"payment_{p[0]}")])
    keyboard.append([InlineKeyboardButton("◀️ Ortga", callback_data="admin_payments")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# Admin - Foydalanuvchilar
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    keyboard = [
        [InlineKeyboardButton("👥 Barcha foydalanuvchilar", callback_data="admin_users_all")],
        [InlineKeyboardButton("✅ Faol foydalanuvchilar", callback_data="admin_users_active")],
        [InlineKeyboardButton("💰 Premium egalari", callback_data="admin_users_premium")],
        [InlineKeyboardButton("🔍 Qidirish", callback_data="admin_users_search")],
        [InlineKeyboardButton("🚫 Bloklanganlar", callback_data="admin_users_blocked")],
        [InlineKeyboardButton("◀️ Ortga", callback_data="admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👥 *FOYDALANUVCHILAR BOSHQARUVI*\n\n"
        "Bo'limni tanlang:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Admin - Barcha foydalanuvchilar
async def admin_users_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    c.execute('''SELECT user_id, username, full_name, balance, registered_date 
                 FROM users ORDER BY registered_date DESC LIMIT 10''')
    users = c.fetchall()
    conn.close()
    
    if not users:
        await query.edit_message_text(
            "📭 Foydalanuvchilar yo'q!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Ortga", callback_data="admin_users")]])
        )
        return
    
    text = "👥 *Oxirgi 10 ta foydalanuvchi:*\n\n"
    for u in users:
        date = datetime.fromisoformat(u[4]).strftime('%d.%m.%Y')
        text += f"🆔 `{u[0]}`\n👤 {u[2]}\n📱 @{u[1] or 'no_username'}\n💰 {u[3]:,.0f} so'm\n📅 {date}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("📥 Yuklash (CSV)", callback_data="export_users")],
        [InlineKeyboardButton("◀️ Ortga", callback_data="admin_users")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# Admin - Qidirish
async def admin_users_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    await query.edit_message_text(
        "🔍 *Foydalanuvchi qidirish*\n\n"
        "Qidirish uchun User ID yoki username yuboring:",
        parse_mode='Markdown'
    )
    return ADMIN_SEARCH

async def admin_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    search_text = update.message.text.strip()
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    # User ID bo'yicha qidirish
    if search_text.isdigit():
        c.execute('''SELECT user_id, username, full_name, balance, referred_by, is_blocked, registered_date 
                     FROM users WHERE user_id=?''', (int(search_text),))
    else:
        # Username bo'yicha qidirish
        search = f"%{search_text.replace('@', '')}%"
        c.execute('''SELECT user_id, username, full_name, balance, referred_by, is_blocked, registered_date 
                     FROM users WHERE username LIKE ? OR full_name LIKE ? LIMIT 5''', (search, search))
    
    users = c.fetchall()
    conn.close()
    
    if not users:
        await update.message.reply_text(
            "❌ Foydalanuvchi topilmadi!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Ortga", callback_data="admin_users")]])
        )
        return ConversationHandler.END
    
    for user in users:
        status = "🚫 Bloklangan" if user[5] else "✅ Faol"
        ref_count = get_referral_count(user[0])
        
        text = (
            f"👤 *Foydalanuvchi ma'lumotlari*\n\n"
            f"🆔 ID: `{user[0]}`\n"
            f"👤 Ism: {user[2]}\n"
            f"📱 Username: @{user[1] or 'no_username'}\n"
            f"💰 Balans: {user[3]:,.0f} so'm\n"
            f"👥 Referallar: {ref_count} ta\n"
            f"📊 Status: {status}\n"
            f"📅 Ro'yxat: {datetime.fromisoformat(user[6]).strftime('%d.%m.%Y')}"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("💰 Balans qo'shish", callback_data=f"add_balance_{user[0]}"),
                InlineKeyboardButton("🔨 Bloklash" if not user[5] else "✅ Blokdan chiqarish", 
                                    callback_data=f"toggle_block_{user[0]}")
            ],
            [InlineKeyboardButton("📋 Premiumlari", callback_data=f"user_premiums_{user[0]}")],
            [InlineKeyboardButton("◀️ Ortga", callback_data="admin_users")]
        ]
        
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    return ConversationHandler.END

# Admin - Balans qo'shish
async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    user_id = int(query.data.replace("add_balance_", ""))
    context.user_data['target_user'] = user_id
    
    await query.edit_message_text(
        f"💰 Balans qo'shish\n\n"
        f"User ID: `{user_id}`\n\n"
        f"Qancha summa qo'shmoqchisiz? (so'm):",
        parse_mode='Markdown'
    )
    return ADMIN_BALANCE

async def add_balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    try:
        amount = float(update.message.text.replace(',', '').strip())
    except:
        await update.message.reply_text("❌ Noto'g'ri format! Iltimos, son kiriting.")
        return ADMIN_BALANCE
    
    user_id = context.user_data.get('target_user')
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    c.execute('UPDATE users SET balance = balance + ? WHERE user_id=?', (amount, user_id))
    c.execute('SELECT balance FROM users WHERE user_id=?', (user_id,))
    new_balance = c.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ Balans muvaffaqiyatli qo'shildi!\n\n"
        f"User ID: `{user_id}`\n"
        f"💰 Qo'shilgan: {amount:,.0f} so'm\n"
        f"💳 Yangi balans: {new_balance:,.0f} so'm",
        parse_mode='Markdown'
    )
    
    # Foydalanuvchiga xabar
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"💰 *Balansingizga pul qo'shildi!*\n\n"
                 f"➕ {amount:,.0f} so'm qo'shildi\n"
                 f"💳 Joriy balans: {new_balance:,.0f} so'm",
            parse_mode='Markdown'
        )
    except:
        pass
    
    await admin_panel(update, context)
    return ConversationHandler.END

# Admin - Statistika
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    # Kunlik statistika (oxirgi 7 kun)
    stats_text = "📊 *KUNLIK STATISTIKA*\n\n"
    
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        c.execute('SELECT new_users, payments, income FROM stats WHERE date=?', (date,))
        stat = c.fetchone()
        
        if stat:
            stats_text += f"📅 {date}:\n"
            stats_text += f"   👥 Yangi: {stat[0]} | 💳 To'lov: {stat[1]} | 💰 {stat[2]:,.0f} so'm\n"
    
    # Platforma bo'yicha
    c.execute('''SELECT platform, COUNT(*) FROM premiums GROUP BY platform''')
    platforms = c.fetchall()
    
    stats_text += "\n📱 *PLATFORMA BO'YICHA*\n"
    for p in platforms:
        stats_text += f"   {p[0].upper()}: {p[1]} ta\n"
    
    # Tariflar bo'yicha
    c.execute('''SELECT tariff, COUNT(*) FROM premiums GROUP BY tariff''')
    tariffs = c.fetchall()
    
    stats_text += "\n📦 *TARIFLAR BO'YICHA*\n"
    for t in tariffs:
        stats_text += f"   {t[0]}: {t[1]} ta\n"
    
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("📥 To'liq hisobot", callback_data="export_stats")],
        [InlineKeyboardButton("◀️ Ortga", callback_data="admin")]
    ]
    
    await query.edit_message_text(stats_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# To'lovni tasdiqlash
async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    payment_id = query.data.replace("approve_", "")
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    c.execute('''SELECT user_id, amount, platform, tariff, username FROM payments 
                 WHERE payment_id=? AND status="pending"''', (payment_id,))
    payment = c.fetchone()
    
    if not payment:
        await query.edit_message_text("❌ To'lov topilmadi yoki allaqachon tasdiqlangan!")
        conn.close()
        return
    
    user_id, amount, platform, tariff_key, username = payment
    
    # To'lovni tasdiqlash
    c.execute('UPDATE payments SET status="approved" WHERE payment_id=?', (payment_id,))
    
    # Premium qo'shish
    days = TARIFFS[platform][tariff_key]['days']
    start_date = datetime.now()
    end_date = start_date + timedelta(days=days)
    
    c.execute('''INSERT INTO premiums (user_id, platform, tariff, price, days, start_date, end_date, payment_method)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, platform, tariff_key, amount, days, start_date.isoformat(), end_date.isoformat(), 'card'))
    
    # Statistika yangilash
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute('INSERT OR IGNORE INTO stats (date) VALUES (?)', (today,))
    c.execute('UPDATE stats SET payments = payments + 1, income = income + ? WHERE date = ?', (amount, today))
    
    # Referal mukofot
    c.execute('SELECT referred_by FROM users WHERE user_id=?', (user_id,))
    referred_by = c.fetchone()
    
    if referred_by and referred_by[0]:
        c.execute('UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id=?', 
                  (REFERRAL_BONUS, REFERRAL_BONUS, referred_by[0]))
        c.execute('''INSERT INTO referral_payments (user_id, amount, from_user_id, date, status)
                     VALUES (?, ?, ?, ?, ?)''',
                  (referred_by[0], REFERRAL_BONUS, user_id, datetime.now().isoformat(), 'paid'))
        
        try:
            await context.bot.send_message(
                chat_id=referred_by[0],
                text=f"🎉 *Referal mukofot!*\n\n"
                     f"👤 Siz taklif qilgan foydalanuvchi premium xarid qildi!\n"
                     f"💰 Balansingizga {REFERRAL_BONUS:,} so'm qo'shildi!\n"
                     f"💳 Joriy balans: {get_balance(referred_by[0]):,.0f} so'm",
                parse_mode='Markdown'
            )
        except:
            pass
    
    conn.commit()
    conn.close()
    
    # Foydalanuvchiga xabar
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ *To'lovingiz tasdiqlandi!*\n\n"
                 f"🎉 *Premium faollashtirildi!*\n\n"
                 f"📱 Xizmat: {TARIFFS[platform][tariff_key]['name']}\n"
                 f"⏱ Muddati: {days} kun\n"
                 f"📅 Tugash sanasi: {end_date.strftime('%d.%m.%Y')}\n\n"
                 f"Rahmat!",
            parse_mode='Markdown'
        )
    except:
        pass
    
    # Admin panelda xabarni yangilash
    await query.edit_message_caption(
        caption=f"✅ *TO'LOV TASDIQLANDI!*\n\n{query.message.caption}",
        parse_mode='Markdown'
    )
    
    # Admin panelni yangilash
    await admin_panel(update, context)

def get_balance(user_id):
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM users WHERE user_id=?', (user_id,))
    balance = c.fetchone()[0]
    conn.close()
    return balance

# To'lovni bekor qilish
async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    payment_id = query.data.replace("reject_", "")
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    c.execute('SELECT user_id FROM payments WHERE payment_id=?', (payment_id,))
    payment = c.fetchone()
    
    if payment:
        user_id = payment[0]
        c.execute('UPDATE payments SET status="rejected" WHERE payment_id=?', (payment_id,))
        conn.commit()
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ *To'lovingiz tasdiqlanmadi!*\n\n"
                     "Sabablari:\n"
                     "• Noto'g'ri summa\n"
                     "• Noto'g'ri karta\n"
                     "• Aniq emas skrinshot\n\n"
                     "Iltimos, qaytadan urinib ko'ring yoki admin bilan bog'laning.",
                parse_mode='Markdown'
            )
        except:
            pass
        
        await query.edit_message_caption(
            caption=f"❌ *TO'LOV BEKOR QILINDI!*\n\n{query.message.caption}",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text("❌ To'lov topilmadi!")
    
    conn.close()

# Callback handler
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    # Admin panel
    if data == "admin":
        await admin_panel(update, context)
    elif data == "admin_payments":
        await admin_payments(update, context)
    elif data == "admin_payments_pending":
        await admin_payments_pending(update, context)
    elif data == "admin_users":
        await admin_users(update, context)
    elif data == "admin_users_all":
        await admin_users_all(update, context)
    elif data == "admin_users_search":
        await admin_users_search(update, context)
    elif data == "admin_stats":
        await admin_stats(update, context)
    elif data == "back_to_main":
        await show_main_menu(update, context)
    
    # Foydalanuvchi paneli
    elif data == "buy_premium":
        await buy_premium(update, context)
    elif data.startswith("platform_"):
        await select_platform(update, context)
    elif data.startswith("tariff_"):
        await select_tariff(update, context)
    elif data == "my_premiums":
        await my_premiums(update, context)
    elif data == "balance":
        await balance_info(update, context)
    elif data == "referral":
        await referral_system(update, context)
    elif data == "referral_list":
        await referral_list(update, context)
    elif data == "use_balance":
        await use_balance(update, context)
    elif data.startswith("balance_platform_"):
        await balance_platform(update, context)
    elif data.startswith("balance_tariff_"):
        await balance_tariff(update, context)
    elif data == "contact_admin":
        await contact_admin(update, context)
    elif data == "help":
        await help_menu(update, context)
    
    # To'lovlarni boshqarish
    elif data.startswith("approve_"):
        await approve_payment(update, context)
    elif data.startswith("reject_"):
        await reject_payment(update, context)
    elif data.startswith("add_balance_"):
        await add_balance(update, context)

# Mening premiumlarim
async def my_premiums(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    c.execute('''SELECT platform, tariff, start_date, end_date, status 
                 FROM premiums WHERE user_id=? ORDER BY start_date DESC''',
              (update.effective_user.id,))
    premiums = c.fetchall()
    conn.close()
    
    if not premiums:
        text = "📭 Sizda hali premium xizmatlar mavjud emas."
    else:
        text = "📋 *Sizning premiumlaringiz:*\n\n"
        for p in premiums:
            platform = TARIFFS[p[0]][p[1]]['emoji'] + " " + TARIFFS[p[0]][p[1]]['name']
            start = datetime.fromisoformat(p[2]).strftime('%d.%m.%Y')
            end = datetime.fromisoformat(p[3]).strftime('%d.%m.%Y')
            
            # Qolgan kunlar
            remaining = (datetime.fromisoformat(p[3]) - datetime.now()).days
            if remaining < 0:
                status = "❌ Tugagan"
            else:
                status = f"✅ Faol ({remaining} kun)"
            
            text += f"{platform}\n📅 {start} - {end}\n⏳ {status}\n\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Ortga", callback_data="back_to_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# Balans ma'lumoti
async def balance_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    c.execute('SELECT balance, total_earned FROM users WHERE user_id=?', (user_id,))
    user_data = c.fetchone()
    
    c.execute('SELECT COUNT(*) FROM users WHERE referred_by=?', (user_id,))
    referrals = c.fetchone()[0]
    
    c.execute('SELECT SUM(amount) FROM referral_payments WHERE user_id=? AND status="paid"', (user_id,))
    earned = c.fetchone()[0] or 0
    
    conn.close()
    
    text = (
        f"💰 *Balans ma'lumoti*\n\n"
        f"💳 Joriy balans: `{user_data[0]:,.0f} so'm`\n"
        f"📈 Umumiy daromad: `{earned:,.0f} so'm`\n"
        f"👥 Referallar: {referrals} ta\n\n"
        f"💸 Balansdan premium olish uchun:\n"
        f"`/use_balance`"
    )
    
    keyboard = [
        [InlineKeyboardButton("💸 Balansdan olish", callback_data="use_balance")],
        [InlineKeyboardButton("◀️ Ortga", callback_data="back_to_main")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# Admin bilan bog'lanish
async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = (
        "📞 *Admin bilan bog'lanish*\n\n"
        "Agar savollaringiz yoki muammolaringiz bo'lsa, admin bilan bog'lanishingiz mumkin:\n\n"
        f"👨‍💼 Admin: @username7155\n"
        f"⚡ Javob vaqti: 5-10 daqiqa"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Ortga", callback_data="back_to_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# Yordam
async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = (
        "ℹ️ *Yordam*\n\n"
        "🛍 *Premium sotib olish:*\n"
        "1. Platformani tanlang\n"
        "2. Tarifni tanlang\n"
        "3. Username yuboring\n"
        "4. Karta orqali to'lov qiling\n"
        "5. Chekni yuboring\n\n"
        "💰 *Referal tizim:*\n"
        "• Do'stlaringizni taklif qiling\n"
        "• Ular premium xarid qilganda 1000 so'm oling\n"
        "• To'plangan pulni premium olishda ishlating\n\n"
        "💳 *Balansdan olish:*\n"
        "• Referal pullar balansga tushadi\n"
        "• Balans orqali to'g'ridan-to'g'ri premium oling\n\n"
        "❓ Savollar bo'lsa, admin bilan bog'lang"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Ortga", callback_data="back_to_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# Start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await register_user(update, context)
    
    # Agar admin bo'lsa, admin panelga yo'naltirish
    if update.effective_user.id == ADMIN_ID and context.args and context.args[0] == "admin":
        await admin_panel(update, context)
    else:
        await show_main_menu(update, context)

# Cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context)
    return ConversationHandler.END

def main():
    # Bot tokeningizni yozing
    token = "8635650689:AAH9mEr_gfkdh3qTTKeMvt75vlsCyX7u5Jc"  # BU YERGA BOT TOKENINGIZNI YOZING
    
    # Ma'lumotlar bazasini yaratish
    init_db()
    
    # Application yaratish
    application = Application.builder().token(token).build()
    
    # ConversationHandler yaratish
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_username_card),
            CallbackQueryHandler(balance_tariff, pattern="^balance_tariff_"),
        ],
        states={
            USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_username_card),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_username_balance),
            ],
            CHECK_PHOTO: [MessageHandler(filters.PHOTO, get_check_photo)],
            ADMIN_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_search_handler)],
            ADMIN_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_balance_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False,
        per_chat=True,
        per_user=True
    )
    
    # Handlerlarni qo'shish
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(conv_handler)
    
    # Botni ishga tushirish
    print("🤖 Bot ishga tushdi...")
    print(f"👨‍💼 Admin ID: {ADMIN_ID}")
    print("⚡ Admin panel: /start admin")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
