import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes
import sqlite3
from datetime import datetime, timedelta

# Holatlar
USERNAME, PLATFORM, TARIFF, CHECK_PHOTO = range(4)

# Admin ID (o'zingizning ID ingizni yozing)
ADMIN_ID = 8735360012  # BU YERGA O'Z IDINGIZNI YOZING

# To'lov ma'lumotlari
PAYMENT_CARD = "9860350146763007"
PAYMENT_NAME = "Rustamov Bahrombek"
PAYMENT_BANK = "TBS Bank"

# Tariflar
TARIFFS = {
    "tg": {
        "1oy": {"name": "Telegram 1 oylik", "price": 25000},
        "2oy": {"name": "Telegram 2 oylik", "price": 49000},
        "3oy": {"name": "Telegram 3 oylik", "price": 73000},
        "6oy": {"name": "Telegram 6 oylik", "price": 140000},
        "1yil": {"name": "Telegram 1 yillik", "price": 220000}
    },
    "insta": {
        "1oy": {"name": "Instagram 1 oylik", "price": 6000},
        "6oy": {"name": "Instagram 6 oylik", "price": 36000},
        "1yil": {"name": "Instagram 1 yillik", "price": 72000}
    }
}

# Ma'lumotlar bazasini sozlash
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                  username TEXT,
                  platform TEXT,
                  tariff TEXT,
                  price INTEGER,
                  status TEXT,
                  start_date TEXT,
                  end_date TEXT,
                  payment_status TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS payments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  check_photo_id TEXT,
                  amount INTEGER,
                  status TEXT,
                  date TEXT)''')
    conn.commit()
    conn.close()

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Assalomu alaykum! Premium xizmatlarni olish uchun quyidagi amallarni bajaring:\n\n"
        "1️⃣ Telegram username'ingizni yuboring (masalan: @username)"
    )
    return USERNAME

# Username ni olish
async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text
    context.user_data['username'] = username
    context.user_data['user_id'] = update.effective_user.id
    
    # Platformani tanlash
    keyboard = [
        [InlineKeyboardButton("📱 Telegram Premium", callback_data="tg")],
        [InlineKeyboardButton("📸 Instagram Premium", callback_data="insta")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Platformani tanlang:",
        reply_markup=reply_markup
    )
    return PLATFORM

# Platformani tanlash
async def platform_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    platform = query.data
    context.user_data['platform'] = platform
    
    # Tariflarni ko'rsatish
    keyboard = []
    for key, value in TARIFFS[platform].items():
        keyboard.append([InlineKeyboardButton(
            f"{value['name']} - {value['price']} so'm",
            callback_data=key
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Tarifni tanlang:",
        reply_markup=reply_markup
    )
    return TARIFF

# Tarifni tanlash
async def tariff_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    tariff_key = query.data
    platform = context.user_data['platform']
    tariff = TARIFFS[platform][tariff_key]
    
    context.user_data['tariff'] = tariff_key
    context.user_data['price'] = tariff['price']
    
    # To'lov ma'lumotlarini ko'rsatish
    payment_info = (
        f"✅ To'lov uchun ma'lumotlar:\n\n"
        f"💳 Karta: {PAYMENT_CARD}\n"
        f"👤 Ism: {PAYMENT_NAME}\n"
        f"🏦 Bank: {PAYMENT_BANK}\n"
        f"💰 Summa: {tariff['price']} so'm\n\n"
        f"📌 {tariff['name']}\n"
        f"👤 Username: {context.user_data['username']}\n\n"
        f"To'lovni amalga oshirib, chekni (skrinshot) yuboring!"
    )
    
    await query.edit_message_text(payment_info)
    await query.message.reply_text("Chekni (skrinshot) yuboring:")
    return CHECK_PHOTO

# Chekni qabul qilish
async def get_check_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo = update.message.photo[-1]
        photo_id = photo.file_id
        
        # Ma'lumotlarni saqlash
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('''INSERT INTO payments (user_id, check_photo_id, amount, status, date)
                     VALUES (?, ?, ?, ?, ?)''',
                  (context.user_data['user_id'], photo_id, context.user_data['price'], 'pending', datetime.now().isoformat()))
        payment_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # Adminga yuborish
        admin_text = (
            f"🆕 Yangi to'lov tekshiruvi!\n\n"
            f"👤 Foydalanuvchi: @{update.effective_user.username or 'no_username'}\n"
            f"🆔 User ID: {context.user_data['user_id']}\n"
            f"📱 Platforma: {context.user_data['platform']}\n"
            f"📦 Tarif: {context.user_data['tariff']}\n"
            f"💰 Summa: {context.user_data['price']} so'm\n"
            f"👤 Username: {context.user_data['username']}\n"
            f"🆔 Payment ID: {payment_id}\n\n"
            f"Tasdiqlash uchun /approve_{payment_id}\n"
            f"Bekor qilish uchun /reject_{payment_id}"
        )
        
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_id,
            caption=admin_text
        )
        
        await update.message.reply_text(
            "✅ Chek adminga yuborildi! Tez orada premium xizmatingiz faollashtiriladi."
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("Iltimos, rasm yuboring!")
        return CHECK_PHOTO

# Admin tomonidan tasdiqlash
async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Siz admin emassiz!")
        return
    
    text = update.message.text
    payment_id = int(text.replace('/approve_', ''))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Payment ma'lumotlarini olish
    c.execute('SELECT user_id, amount FROM payments WHERE id=?', (payment_id,))
    payment = c.fetchone()
    
    if payment:
        user_id, amount = payment
        
        # Payment statusini yangilash
        c.execute('UPDATE payments SET status="approved" WHERE id=?', (payment_id,))
        
        # Foydalanuvchiga xabar yuborish
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ To'lovingiz tasdiqlandi! Premium xizmatingiz faollashtirildi!"
            )
        except:
            pass
        
        await update.message.reply_text(f"✅ To'lov tasdiqlandi! User ID: {user_id}")
    
    conn.commit()
    conn.close()

# Admin tomonidan bekor qilish
async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Siz admin emassiz!")
        return
    
    text = update.message.text
    payment_id = int(text.replace('/reject_', ''))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute('SELECT user_id FROM payments WHERE id=?', (payment_id,))
    payment = c.fetchone()
    
    if payment:
        user_id = payment[0]
        c.execute('UPDATE payments SET status="rejected" WHERE id=?', (payment_id,))
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ To'lovingiz tasdiqlanmadi. Iltimos, qaytadan urinib ko'ring yoki admin bilan bog'laning."
            )
        except:
            pass
        
        await update.message.reply_text(f"❌ To'lov bekor qilindi! User ID: {user_id}")
    
    conn.commit()
    conn.close()

# /cancel komandasi
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Jarayon bekor qilindi. Qaytadan boshlash uchun /start")
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
        entry_points=[CommandHandler('start', start)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
            PLATFORM: [CallbackQueryHandler(platform_choice)],
            TARIFF: [CallbackQueryHandler(tariff_choice)],
            CHECK_PHOTO: [MessageHandler(filters.PHOTO, get_check_photo)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("approve", approve_payment))
    application.add_handler(CommandHandler("reject", reject_payment))
    
    # Botni ishga tushirish
    print("Bot ishga tushdi...")
    application.run_polling()

if __name__ == '__main__':
    main()
