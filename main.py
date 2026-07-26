import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from apscheduler.schedulers.background import BackgroundScheduler

# Logging ayarları
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Token, Admin ID, Kanal ve API Bilgileri
BOT_TOKEN = "8646358320:AAFuW7CHUPtCgT0wgfP9i2X1v2K9j8a5V4M"
ADMIN_ID = 6073294253
CHANNEL = "@arastirduyuru"
BASE_URL = 'http://arastir.vip/api'

# Veritabanı simülasyonları
USERS_DB = set() # (user_id, username, first_name)
LEFT_COUNTS = {} # Kullanıcıların kanaldan kaç kez çıktığını takip etmek için: {user_id: sayi}
BANNED_USERS = set() # Banlanan kullanıcılar

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

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

    # Kanalda mi kontrolü
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

# Periyodik Kontrol (6 Saatte Bir Çalışır ve Kanaldan Çıkanları Yakalar)
async def periodic_channel_check(app):
    with app.bot:
        for uid, uname, _ in list(USERS_DB):
            if uid in BANNED_USERS:
                continue
            
            is_in = await check_channel_membership(app.bot, uid)
            if not is_in:
                # Kanaldan çıkmış demektir! Sayacı artıralım.
                LEFT_COUNTS[uid] = LEFT_COUNTS.get(uid, 0) + 1
                count = LEFT_COUNTS[uid]
                
                try:
                    if count == 1:
                        # 1. İhlal: Uyarı gönder
                        await app.bot.send_message(
                            chat_id=uid,
                            text=f"⚠️ Dikkat! {CHANNEL} kanalımızdan çıktığınız tespit edildi. Botu kullanmaya devam edebilmek için lütfen tekrar kanalımıza katılın. Tekrarı halinde sistem tarafından banlanacaksınız!"
                        )
                    elif count >= 2:
                        # 2. İhlal ve üzeri: Banla
                        BANNED_USERS.add(uid)
                        await app.bot.send_message(
                            chat_id=uid,
                            text="⛔️ Kanaldan tekrar çıktığınız için sistem tarafından kalıcı olarak banlandınız!"
                        )
                except Exception:
                    pass

# Yönetici Paneli Komutu
async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("Bu komutu kullanmaya yetkin yok kanka!")
        return

    total_users = len(USERS_DB)
    total_banned = len(BANNED_USERS)
    await update.message.reply_text(
        f"🛠 **Yönetici Paneli**\n\n"
        f"👥 **Toplam Aktif Üye:** {total_users}\n"
        f"⛔️ **Banlanan Üye Sayısı:** {total_banned}\n\n"
        f"Komutlar:\n"
        f"• /kullanicilar - Tüm kullanıcıları listele\n"
        f"• /duyuru [mesaj] - Toplu duyuru gönder\n"
        f"• /ban [user_id] - Kullanıcıyı manuel banla"
    )

# Kullanıcı Listesi
async def kullanicilar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not USERS_DB:
        await update.message.reply_text("Henüz kayıtlı kullanıcı yok.")
        return

    text = "👥 **Botu Kullananlar:**\n\n"
    for uid, uname, ufirst in USERS_DB:
        status = "⛔️ Banlı" if uid in BANNED_USERS else "✅ Aktif"
        text += f"• ID: `{uid}` | @{uname} | {ufirst} | {status}\n"
    
    if len(text) > 4096:
        text = text[:4000] + "\n...ve diğerleri."
    
    await update.message.reply_text(text, parse_mode="Markdown")

# Toplu Duyuru
async def duyuru_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("Kullanım: `/duyuru Göndermek istediğin mesaj` şeklinde yaz kanka.", parse_mode="Markdown")
        return
    
    announcement_text = " ".join(args)
    success = 0
    fail = 0

    status_msg = await update.message.reply_text("🚀 Duyuru gönderilmeye başlandı...")

    for uid, _, _ in USERS_DB:
        if uid in BANNED_USERS:
            continue
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 **Duyuru:**\n\n{announcement_text}", parse_mode="Markdown")
            success += 1
        except Exception:
            fail += 1

    await status_msg.edit_text(f"✅ Duyuru tamamlandı!\n\nBaşarılı: {success}\nBaşarısız: {fail}")

# Manuel Ban Komutu
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("Kullanım: `/ban [kullanici_id]` şeklinde yaz kanka.", parse_mode="Markdown")
        return
    
    try:
        target_id = int(args[0])
        BANNED_USERS.add(target_id)
        await update.message.reply_text(f"✅ `{target_id}` ID'li kullanıcı başarıyla banlandı.")
    except ValueError:
        await update.message.reply_text("Geçerli bir ID girmelisin kanka.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Zamanlayıcı (Her 6 saatte bir kanaldan çıkanları kontrol eder)
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: app.job_queue.run_once(lambda ctx: periodic_channel_check(app), 0), 'interval', hours=6)
    scheduler.start()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("panel", panel_command))
    app.add_handler(CommandHandler("kullanicilar", kullanicilar_command))
    app.add_handler(CommandHandler("duyuru", duyuru_command))
    app.add_handler(CommandHandler("ban", ban_command))

    print("Bot ve 6 saatlik kanal kontrol mekanizması aktif...")
    app.run_polling()

if __name__ == '__main__':
    main()
