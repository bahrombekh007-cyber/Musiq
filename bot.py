import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes
import sqlite3
from datetime import datetime, timedelta
import random
import string

# Holatlar
USERNAME, PLATFORM, TARIFF, CHECK_PHOTO, REFERRAL = range(5)

# Admin ID (o'zingizning ID ingizni yozing)
ADMIN_ID = 8735360012  # BU YERGA O'Z IDINGIZNI YOZING

# To'lov ma'lumotlari
PAYMENT_CARD = "9860350146763007"
PAYMENT_NAME = "Rustamov Bahrombek"
PAYMENT_BANK = "TBS Bank"

# Referral mukofoti
REFERRAL_BONUS = 1000  # 1000 so'm

# Tariflar
TARIFFS = {
    "tg": {
        "1oy": {"name": "📱 Telegram 1 oylik", "price": 25000, "days": 30},
        "2oy": {"name": "📱 Telegram 2 oylik", "price": 49000, "days": 60},
        "3oy": {"name": "📱 Telegram 3 oylik", "price": 73000, "days": 90},
        "6oy": {"name": "📱 Telegram 6 oylik", "price": 140000, "days": 180},
        "1yil": {"name": "📱 Telegram 1 yillik", "price": 220000, "days": 365}
    },
    "insta": {
        "1oy": {"name": "📸 Instagram 1 oylik", "price": 6000, "days": 30},
        "6oy": {"name": "📸 Instagram 6 oylik", "price": 36000, "days": 180},
        "1yil": {"name": "📸 Instagram 1 yillik", "price": 72000, "days": 365}
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
                  registered_date TEXT,
                  FOREIGN KEY (referred_by) REFERENCES users(user_id))''')
    
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
                  FOREIGN KEY (user_id) REFERENCES users(user_id))''')
    
    # To'lovlar
    c.execute('''CREATE TABLE IF NOT EXISTS payments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  payment_id TEXT UNIQUE,
                  amount REAL,
                  check_photo_id TEXT,
                  status TEXT DEFAULT 'pending',
                  date TEXT,
                  FOREIGN KEY (user_id) REFERENCES users(user_id))''')
    
    # Referal to'lovlar
    c.execute('''CREATE TABLE IF NOT EXISTS referral_payments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount REAL,
                  from_user_id INTEGER,
                  date TEXT,
                  FOREIGN KEY (user_id) REFERENCES users(user_id),
                  FOREIGN KEY (from_user_id) REFERENCES users(user_id))''')
    
    conn.commit()
    conn.close()

# Referral kod yaratish
def generate_referral_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# Foydalanuvchini ro'yxatdan o'tkazish
async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    # Foydalanuvchi borligini tekshirish
    c.execute('SELECT * FROM users WHERE user_id=?', (user.id,))
    existing_user = c.fetchone()
    
    if not existing_user:
        referral_code = generate_referral_code()
        c.execute('''INSERT INTO users (user_id, username, full_name, referral_code, registered_date)
                     VALUES (?, ?, ?, ?, ?)''',
                  (user.id, user.username, user.full_name, referral_code, datetime.now().isoformat()))
        conn.commit()
        
        # Referralni tekshirish
        if context.args and len(context.args) > 0:
            ref_code = context.args[0]
            c.execute('SELECT user_id FROM users WHERE referral_code=?', (ref_code,))
            referrer = c.fetchone()
            if referrer:
                c.execute('UPDATE users SET referred_by=? WHERE user_id=?', (referrer[0], user.id))
                conn.commit()
                
                # Referrerga xabar
                try:
                    await context.bot.send_message(
                        chat_id=referrer[0],
                        text=f"🎉 Tabriklaymiz! Sizning referal havolangiz orqali yangi foydalanuvchi qo'shildi!\n"
                             f"👤 Yangi foydalanuvchi: {user.full_name}\n"
                             f"💰 Mukofot: {REFERRAL_BONUS} so'm (to'lov amalga oshirilganda beriladi)"
                    )
                except:
                    pass
    
    conn.close()

# Asosiy menyu
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛍 Premium sotib olish", callback_data="buy_premium")],
        [InlineKeyboardButton("👤 Mening premiumlarim", callback_data="my_premiums")],
        [InlineKeyboardButton("💰 Balans va Referal", callback_data="balance")],
        [InlineKeyboardButton("📞 Admin bilan bog'lanish", callback_data="contact_admin")],
        [InlineKeyboardButton("ℹ️ Yordam", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"👋 Xush kelibsiz, {update.effective_user.full_name}!\n\n"
        f"🤖 Bot orqali Telegram va Instagram uchun premium xizmatlarni xarid qilishingiz mumkin.\n"
        f"💰 Do'stlaringizni taklif qiling va har bir taklif uchun {REFERRAL_BONUS} so'm mukofot oling!"
    )
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await register_user(update, context)
    await main_menu(update, context)

# Premium sotib olish
async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📱 Telegram Premium", callback_data="platform_tg")],
        [InlineKeyboardButton("📸 Instagram Premium", callback_data="platform_insta")],
        [InlineKeyboardButton("◀️ Ortga", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Platformani tanlang:",
        reply_markup=reply_markup
    )
    return PLATFORM

# Platforma tanlash
async def select_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    platform = query.data.replace("platform_", "")
    context.user_data['platform'] = platform
    
    keyboard = []
    for key, value in TARIFFS[platform].items():
        keyboard.append([InlineKeyboardButton(
            f"{value['name']} - {value['price']} so'm",
            callback_data=f"tariff_{key}"
        )])
    keyboard.append([InlineKeyboardButton("◀️ Ortga", callback_data="buy_premium")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Tarifni tanlang:",
        reply_markup=reply_markup
    )
    return TARIFF

# Tarif tanlash
async def select_tariff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    tariff_key = query.data.replace("tariff_", "")
    platform = context.user_data['platform']
    tariff = TARIFFS[platform][tariff_key]
    
    context.user_data['tariff'] = tariff_key
    context.user_data['price'] = tariff['price']
    context.user_data['days'] = tariff['days']
    
    keyboard = [
        [InlineKeyboardButton("◀️ Ortga", callback_data=f"platform_{platform}")],
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_tariff")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"📦 Tanlangan tarif:\n\n"
        f"📱 {tariff['name']}\n"
        f"💰 Narxi: {tariff['price']} so'm\n"
        f"⏱ Muddati: {tariff['days']} kun\n\n"
        f"Telegram username'ingizni yuboring:"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return USERNAME

# Username ni olish
async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text
    context.user_data['username'] = username
    
    # To'lov ma'lumotlarini ko'rsatish
    payment_info = (
        f"💳 To'lov ma'lumotlari:\n\n"
        f"🏦 Karta: `{PAYMENT_CARD}`\n"
        f"👤 Ism: {PAYMENT_NAME}\n"
        f"🏛 Bank: {PAYMENT_BANK}\n"
        f"💰 Summa: {context.user_data['price']} so'm\n\n"
        f"📱 Platforma: {context.user_data['platform']}\n"
        f"📦 Tarif: {TARIFFS[context.user_data['platform']][context.user_data['tariff']]['name']}\n"
        f"👤 Username: @{username}\n\n"
        f"✅ To'lovni amalga oshirib, chekni (skrinshot) yuboring!"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Ortga", callback_data=f"platform_{context.user_data['platform']}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(payment_info, reply_markup=reply_markup, parse_mode='Markdown')
    await update.message.reply_text("📸 Iltimos, to'lov chekini (skrinshot) yuboring:")
    return CHECK_PHOTO

# Chekni qabul qilish
async def get_check_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Iltimos, rasm yuboring!")
        return CHECK_PHOTO
    
    photo = update.message.photo[-1]
    photo_id = photo.file_id
    
    # Payment ID yaratish
    payment_id = f"PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    # To'lovni saqlash
    c.execute('''INSERT INTO payments (user_id, payment_id, amount, check_photo_id, date)
                 VALUES (?, ?, ?, ?, ?)''',
              (update.effective_user.id, payment_id, context.user_data['price'], photo_id, datetime.now().isoformat()))
    
    # Referral borligini tekshirish
    c.execute('SELECT referred_by FROM users WHERE user_id=?', (update.effective_user.id,))
    referred_by = c.fetchone()
    
    conn.commit()
    conn.close()
    
    # Adminga yuborish
    admin_text = (
        f"🆕 **Yangi to'lov tekshiruvi!**\n\n"
        f"🆔 Payment ID: `{payment_id}`\n"
        f"👤 Foydalanuvchi: @{update.effective_user.username or 'no_username'}\n"
        f"👤 Ism: {update.effective_user.full_name}\n"
        f"🆔 User ID: `{update.effective_user.id}`\n"
        f"📱 Platforma: {context.user_data['platform']}\n"
        f"📦 Tarif: {TARIFFS[context.user_data['platform']][context.user_data['tariff']]['name']}\n"
        f"💰 Summa: {context.user_data['price']} so'm\n"
        f"👤 Username: @{context.user_data['username']}\n"
        f"👥 Referral: {'Bor' if referred_by else 'Yo\'q'}\n\n"
        f"**Tasdiqlash uchun tugmalardan foydalaning:**"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{payment_id}"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"reject_{payment_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=admin_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await update.message.reply_text(
        "✅ Chek adminga yuborildi!\n"
        "⏳ Tez orada premium xizmatingiz faollashtiriladi."
    )
    
    return ConversationHandler.END

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
    
    if not premiums:
        text = "📭 Sizda hali premium xizmatlar mavjud emas."
    else:
        text = "📋 **Sizning premiumlaringiz:**\n\n"
        for p in premiums:
            platform = "📱 Telegram" if p[0] == "tg" else "📸 Instagram"
            tariff_name = TARIFFS[p[0]][p[1]]['name']
            start = datetime.fromisoformat(p[2]).strftime('%d.%m.%Y')
            end = datetime.fromisoformat(p[3]).strftime('%d.%m.%Y')
            status = "✅ Faol" if p[4] == "active" else "❌ Tugagan"
            
            text += f"{platform} - {tariff_name}\n"
            text += f"📅 {start} - {end}\n"
            text += f"📊 Status: {status}\n\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Ortga", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# Balans va Referal
async def balance_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    # Balans
    c.execute('SELECT balance, referral_code FROM users WHERE user_id=?', (update.effective_user.id,))
    user_data = c.fetchone()
    balance = user_data[0] if user_data else 0
    referral_code = user_data[1] if user_data else ""
    
    # Referallar soni
    c.execute('SELECT COUNT(*) FROM users WHERE referred_by=?', (update.effective_user.id,))
    referrals_count = c.fetchone()[0]
    
    # Referal to'lovlar
    c.execute('''SELECT SUM(amount) FROM referral_payments WHERE user_id=?''', (update.effective_user.id,))
    total_earned = c.fetchone()[0] or 0
    
    conn.close()
    
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={referral_code}"
    
    text = (
        f"💰 **Balans va Referal ma'lumotlari**\n\n"
        f"💳 Sizning balansingiz: `{balance}` so'm\n"
        f"👥 Taklif qilganlaringiz: {referrals_count} ta\n"
        f"💵 Umumiy daromad: {total_earned} so'm\n\n"
        f"🔗 **Sizning referal havolangiz:**\n"
        f"`{referral_link}`\n\n"
        f"📌 Har bir taklif uchun {REFERRAL_BONUS} so'm mukofot!\n"
        f"💰 Mukofotlar taklif qilgan odamingiz premium xarid qilganda balansingizga tushadi."
    )
    
    keyboard = [
        [InlineKeyboardButton("💸 Balansni yechish", callback_data="withdraw")],
        [InlineKeyboardButton("👥 Referallar ro'yxati", callback_data="referrals_list")],
        [InlineKeyboardButton("◀️ Ortga", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# Admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    # Statistika
    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM premiums WHERE status="active"')
    active_premiums = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM payments WHERE status="pending"')
    pending_payments = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM payments WHERE status="approved"')
    total_payments = c.fetchone()[0]
    
    c.execute('SELECT SUM(amount) FROM payments WHERE status="approved"')
    total_income = c.fetchone()[0] or 0
    
    c.execute('SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL')
    total_referrals = c.fetchone()[0]
    
    conn.close()
    
    text = (
        f"👨‍💼 **Admin Panel**\n\n"
        f"📊 **Bot statistikasi:**\n"
        f"👥 Jami foydalanuvchilar: {total_users}\n"
        f"✅ Faol premiumlar: {active_premiums}\n"
        f"⏳ Kutilayotgan to'lovlar: {pending_payments}\n"
        f"💰 Jami to'lovlar: {total_payments}\n"
        f"💵 Umumiy daromad: {total_income} so'm\n"
        f"👥 Referallar: {total_referrals}\n\n"
        f"🔽 **Admin funksiyalari:**"
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 To'lovlar ro'yxati", callback_data="admin_payments")],
        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="admin_users")],
        [InlineKeyboardButton("📊 To'liq statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📨 Xabar yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⚙️ Sozlamalar", callback_data="admin_settings")],
        [InlineKeyboardButton("◀️ Ortga", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# To'lovni tasdiqlash
async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Siz admin emassiz!")
        return
    
    payment_id = query.data.replace("approve_", "")
    
    conn = sqlite3.connect('premium_bot.db')
    c = conn.cursor()
    
    # To'lov ma'lumotlarini olish
    c.execute('''SELECT user_id, amount FROM payments WHERE payment_id=? AND status="pending"''', (payment_id,))
    payment = c.fetchone()
    
    if not payment:
        await query.edit_message_text("❌ To'lov topilmadi yoki allaqachon tasdiqlangan!")
        conn.close()
        return
    
    user_id, amount = payment
    
    # To'lov statusini yangilash
    c.execute('UPDATE payments SET status="approved" WHERE payment_id=?', (payment_id,))
    
    # Premium qo'shish
    platform = context.user_data.get('platform', 'tg')
    tariff_key = context.user_data.get('tariff', '1oy')
    days = TARIFFS[platform][tariff_key]['days']
    
    start_date = datetime.now()
    end_date = start_date + timedelta(days=days)
    
    c.execute('''INSERT INTO premiums (user_id, platform, tariff, price, days, start_date, end_date)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (user_id, platform, tariff_key, amount, days, start_date.isoformat(), end_date.isoformat()))
    
    # Referal mukofotini hisoblash
    c.execute('SELECT referred_by FROM users WHERE user_id=?', (user_id,))
    referred_by = c.fetchone()
    
    if referred_by and referred_by[0]:
        referrer_id = referred_by[0]
        
        # Referalga mukofot qo'shish
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id=?', (REFERRAL_BONUS, referrer_id))
        
        # Referal to'lovni saqlash
        c.execute('''INSERT INTO referral_payments (user_id, amount, from_user_id, date)
                     VALUES (?, ?, ?, ?)''',
                  (referrer_id, REFERRAL_BONUS, user_id, datetime.now().isoformat()))
        
        # Refererga xabar
        try:
            await context.bot.send_message(
                chat_id=referrer_id,
                text=f"🎉 Tabriklaymiz! Sizning referalingiz premium xarid qildi!\n"
                     f"💰 Balansingizga {REFERRAL_BONUS} so'm qo'shildi!\n"
                     f"💳 Joriy balans: {REFERRAL_BONUS} so'm"
            )
        except:
            pass
    
    conn.commit()
    conn.close()
    
    # Foydalanuvchiga xabar
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ **To'lovingiz tasdiqlandi!**\n\n"
                 f"🎉 Premium xizmatingiz faollashtirildi!\n"
                 f"📱 Platforma: {platform}\n"
                 f"📦 Tarif: {TARIFFS[platform][tariff_key]['name']}\n"
                 f"⏱ Muddati: {days} kun\n"
                 f"📅 Tugash sanasi: {end_date.strftime('%d.%m.%Y')}\n\n"
                 f"Rahmat!",
            parse_mode='Markdown'
        )
    except:
        pass
    
    await query.edit_message_text(f"✅ To'lov tasdiqlandi!\n👤 User ID: {user_id}\n💰 Summa: {amount} so'm")

# To'lovni bekor qilish
async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Siz admin emassiz!")
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
                text="❌ **To'lovingiz tasdiqlanmadi!**\n\n"
                     "Iltimos, qaytadan urinib ko'ring yoki admin bilan bog'laning.\n"
                     "Sabablari:\n"
                     "• Noto'g'ri summa\n"
                     "• Noto'g'ri karta\n"
                     "• Aniq emas skrinshot",
                parse_mode='Markdown'
            )
        except:
            pass
        
        await query.edit_message_text(f"❌ To'lov bekor qilindi!\n👤 User ID: {user_id}")
    else:
        await query.edit_message_text("❌ To'lov topilmadi!")
    
    conn.close()

# Callback query handler
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_main":
        await main_menu(update, context)
    
    elif query.data == "buy_premium":
        await buy_premium(update, context)
    
    elif query.data.startswith("platform_"):
        await select_platform(update, context)
    
    elif query.data.startswith("tariff_"):
        await select_tariff(update, context)
    
    elif query.data == "confirm_tariff":
        await query.edit_message_text("Iltimos, Telegram username'ingizni yuboring:")
        return USERNAME
    
    elif query.data == "my_premiums":
        await my_premiums(update, context)
    
    elif query.data == "balance":
        await balance_info(update, context)
    
    elif query.data == "contact_admin":
        keyboard = [[InlineKeyboardButton("◀️ Ortga", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"📞 Admin bilan bog'lanish uchun: @admin_username\n\n"
            f"Admin ID: {ADMIN_ID}",
            reply_markup=reply_markup
        )
    
    elif query.data == "help":
        text = (
            "ℹ️ **Yordam**\n\n"
            "🛍 **Premium sotib olish:**\n"
            "1. Platformani tanlang\n"
            "2. Tarifni tanlang\n"
            "3. Username yuboring\n"
            "4. To'lov qiling va chek yuboring\n\n"
            "💰 **Referal tizim:**\n"
            "• Do'stlaringizni taklif qiling\n"
            "• Har bir taklif uchun 1000 so'm\n"
            "• Mukofot taklif qilgan odamingiz premium xarid qilganda tushadi\n\n"
            "❓ Savollar bo'lsa, admin bilan bog'laning"
        )
        keyboard = [[InlineKeyboardButton("◀️ Ortga", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    elif query.data == "admin":
        await admin_panel(update, context)
    
    elif query.data.startswith("approve_"):
        await approve_payment(update, context)
    
    elif query.data.startswith("reject_"):
        await reject_payment(update, context)

# /admin komandasi
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await admin_panel(update, context)

# /cancel komandasi
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context)
    return ConversationHandler.END

def main():
    # Bot tokenini o'rnating
    token = "8635650689:AAH9mEr_gfkdh3qTTKeMvt75vlsCyX7u5Jc"  # BU YERGA BOT TOKENINGIZNI YOZING
    
    # Ma'lumotlar bazasini ishga tushirish
    init_db()
    
    # Application yaratish
    application = Application.builder().token(token).build()
    
    # ConversationHandler yaratish
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback_handler, pattern="^confirm_tariff$")],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
            CHECK_PHOTO: [MessageHandler(filters.PHOTO, get_check_photo)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Handlerlarni qo'shish
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('admin', admin_command))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(conv_handler)
    
    # Botni ishga tushirish
    print("🤖 Bot ishga tushdi...")
    print(f"👨‍💼 Admin ID: {ADMIN_ID}")
    application.run_polling()

if __name__ == '__main__':
    main()
