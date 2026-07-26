import logging
import requests
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

# Logging ayarları
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Token, Admin ID, Kanal ve API Bilgileri
BOT_TOKEN = "8646358320:AAFuW7CHUPtCgT0wgfP9xZxf6URYTWOoYWE"
ADMIN_ID = 6073294253
CHANNEL = "@arastirduyuru"
BASE_URL = 'http://arastir.vip/api'

USERS_DB = set()
LEFT_COUNTS = {}
BANNED_USERS = set()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Bot aktif ve çalışıyor!"

async def check_channel_membership(bot, user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception:
        return False

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id in BANNED_USERS:
        await update.message.reply_text("⛔️ Bu botu kullanmanız yasaklanmıştır.")
        return

    is_in_channel = await check_channel_membership(context.bot, user.id)
    if not is_in_channel:
        await update.message.reply_text(
            f"⚠️ Botu kullanabilmek için öncelikle {CHANNEL} kanalımıza abone olmalısınız!\n\nAbone olduktan sonra tekrar /start yazabilirsiniz."
        )
        return

    USERS_DB.add((user.id, user.username or "Kullanıcı adı yok", user.first_name))
    
    keyboard = [
        [InlineKeyboardButton("🆔 TC Sorgu", callback_data="tc"), InlineKeyboardButton("👤 Ad Soyad", callback_data="adsoyad")],
        [InlineKeyboardButton("👥 Aile", callback_data="aile"), InlineKeyboardButton("🌳 Sülale", callback_data="sulale")],
        [InlineKeyboardButton("👶 Çocuklar", callback_data="cocuklar"), InlineKeyboardButton("🏠 Adres", callback_data="adres")],
        [InlineKeyboardButton("📱 GSM -> TC", callback_data="gsm_tc"), InlineKeyboardButton("☎️ TC -> GSM", callback_data="tc_gsm")],
        [InlineKeyboardButton("🏢 İşyeri", callback_data="isyeri")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✨ Hoş Geldin {user.first_name}! Lütfen yapmak istediğin sorgu türünü seçin veya komut kullanın:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "tc":
        await query.message.reply_text("🆔 **TC Sorgu için:**\n`/tc [TCno]` şeklinde yazmalısın kanka.", parse_mode="Markdown")
    elif data == "adsoyad":
        await query.message.reply_text("👤 **Ad Soyad Sorgu için:**\n`/adsoyad [Ad] [Soyad]` şeklinde yazmalısın kanka.", parse_mode="Markdown")
    elif data == "aile":
        await query.message.reply_text("👥 **Aile Sorgu için:**\n`/aile [TCno]` şeklinde yazmalısın kanka.", parse_mode="Markdown")
    elif data == "sulale":
        await query.message.reply_text("🌳 **Sülale Sorgu için:**\n`/sulale [TCno]` şeklinde yazmalısın kanka.", parse_mode="Markdown")
    elif data == "cocuklar":
        await query.message.reply_text("👶 **Çocuklar Sorgu için:**\n`/cocuklar [TCno]` şeklinde yazmalısın kanka.", parse_mode="Markdown")
    elif data == "adres":
        await query.message.reply_text("🏠 **Adres Sorgu için:**\n`/adres [TCno]` şeklinde yazmalısın kanka.", parse_mode="Markdown")
    elif data == "gsm_tc":
        await query.message.reply_text("📱 **GSM -> TC için:**\n`/gsmtc [Telefon]` şeklinde yazmalısın kanka.", parse_mode="Markdown")
    elif data == "tc_gsm":
        await query.message.reply_text("☎️ **TC -> GSM için:**\n`/tcgsm [TCno]` şeklinde yazmalısın kanka.", parse_mode="Markdown")
    elif data == "isyeri":
        await query.message.reply_text("🏢 **İşyeri Sorgu için:**\n`/isyeri [TCno]` şeklinde yazmalısın kanka.", parse_mode="Markdown")

# --- GERÇEK API SORGULAMA FONKSİYONLARI ---

async def adsoyad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Kullanım: `/adsoyad [Ad] [Soyad]` şeklinde yaz kanka.")
        return
    
    name = args[0]
    surname = " ".join(args[1:])
    msg = await update.message.reply_text("🔍 Sorgulanıyor, lütfen bekleyin...")
    
    try:
        # API isteği (endpoint yapına göre burayı şekillendirebilirsin)
        response = requests.get(f"{BASE_URL}/adsoyad?ad={name}&soyad={surname}", headers=HEADERS, timeout=10)
        data = response.json()
        await msg.edit_text(f"📊 **Sonuçlar:**\n```json\n{data}\n```", parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Sorgulama sırasında bir hata oluştu veya API yanıt vermedi.")

async def tc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Kullanım: `/tc [TCno]` şeklinde yaz kanka.")
        return
    
    tc = args[0]
    msg = await update.message.reply_text("🔍 Sorgulanıyor...")
    try:
        response = requests.get(f"{BASE_URL}/tc?tc={tc}", headers=HEADERS, timeout=10)
        data = response.json()
        await msg.edit_text(f"📊 **Sonuçlar:**\n```json\n{data}\n```", parse_mode="Markdown")
    except Exception:
        await msg.edit_text("❌ Sorgulama başarısız oldu.")

# --- YÖNETİCİ VE KONTROL KOMUTLARI ---

async def periodic_channel_check(app):
    with app.bot:
        for uid, uname, _ in list(USERS_DB):
            if uid in BANNED_USERS:
                continue
            is_in = await check_channel_membership(app.bot, uid)
            if not is_in:
                LEFT_COUNTS[uid] = LEFT_COUNTS.get(uid, 0) + 1
                count = LEFT_COUNTS[uid]
                try:
                    if count == 1:
                        await app.bot.send_message(chat_id=uid, text=f"⚠️ Dikkat! {CHANNEL} kanalımızdan çıktığınız tespit edildi.")
                    elif count >= 2:
                        BANNED_USERS.add(uid)
                        await app.bot.send_message(chat_id=uid, text="⛔️ Kanaldan tekrar çıktığınız için banlandınız!")
                except Exception:
                    pass

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(f"🛠 **Panel**\nAktif Üye: {len(USERS_DB)}\nBanlı: {len(BANNED_USERS)}")

async def kullanicilar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    text = "👥 **Kullanıcılar:**\n"
    for uid, uname, ufirst in USERS_DB:
        text += f"• `{uid}` | @{uname}\n"
    await update.message.reply_text(text[:4000], parse_mode="Markdown")

async def duyuru_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if not args:
        return
    text = " ".join(args)
    for uid, _, _ in USERS_DB:
        if uid in BANNED_USERS:
            continue
        try:
            await context.bot.send_message(chat_id=uid, text=text)
        except Exception:
            pass
    await update.message.reply_text("✅ Duyuru bitti.")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if args:
        BANNED_USERS.add(int(args[0]))
        await update.message.reply_text("✅ Banlandı.")

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

if __name__ == '__main__':
    from threading import Thread
    t = Thread(target=run_flask)
    t.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: app.job_queue.run_once(lambda ctx: periodic_channel_check(app), 0), 'interval', hours=6)
    scheduler.start()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("panel", panel_command))
    app.add_handler(CommandHandler("kullanicilar", kullanicilar_command))
    app.add_handler(CommandHandler("duyuru", duyuru_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("adsoyad", adsoyad_command))
    app.add_handler(CommandHandler("tc", tc_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()
