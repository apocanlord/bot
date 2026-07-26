import logging
import requests
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

# Logging ayarları
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Token, Admin ID ve API Bilgileri
BOT_TOKEN = "8646358320:AAFuW7CHUPtCgT0wgfP9xZxf6URYTWOoYWE"
ADMIN_ID = 6073294253
BASE_URL = 'http://arastir.vip/api'

# Birden fazla zorunlu kanal listesi (Burayı panelden veya koddan yönetebilirsin)
CHANNELS = ["@arastirduyuru"] 

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

# Çoklu kanal kontrol fonksiyonu
async def check_all_channels(bot, user_id):
    not_joined = []
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                not_joined.append(ch)
        except Exception:
            not_joined.append(ch)
    return not_joined

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id in BANNED_USERS:
        await update.message.reply_text("⛔️ Bu botu kullanmanız yasaklanmıştır.")
        return

    # Tüm kanalları kontrol et
    missing_channels = await check_all_channels(context.bot, user.id)
    if missing_channels:
        ch_list = "\n".join([f"• {ch}" for ch in missing_channels])
        await update.message.reply_text(
            f"⚠️ Botu kullanabilmek için aşağıdaki kanal(lar)ımıza abone olmalısınız:\n\n{ch_list}\n\nAbone olduktan sonra tekrar /start yazabilirsiniz kanka."
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
        f"✨ Hoş Geldin {user.first_name}! Lütfen yapmak istediğin sorgu türünü seçin:",
        reply_markup=reply_markup
    )

# BUTON VE PANEL YÖNETİCİSİ
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
    
    elif data == "admin_users":
        if update.effective_user.id != ADMIN_ID:
            return
        if not USERS_DB:
            await query.message.reply_text("Henüz kayıtlı kullanıcı yok kanka.")
            return
        text = "👥 **Botu Kullananlar:**\n\n"
        for uid, uname, ufirst in USERS_DB:
            status = "⛔️ Banlı" if uid in BANNED_USERS else "✅ Aktif"
            text += f"• ID: `{uid}` | @{uname} | {ufirst} | {status}\n"
        await query.message.reply_text(text[:4000], parse_mode="Markdown")
        
    elif data == "admin_ban":
        if update.effective_user.id != ADMIN_ID:
            return
        await query.message.reply_text("⛔️ **Ban Yönetimi:**\nKullanıcıyı banlamak için:\n`/ban [Kullanici_ID]` şeklinde yazmalısın kanka.", parse_mode="Markdown")
        
    elif data == "admin_duyuru":
        if update.effective_user.id != ADMIN_ID:
            return
        await query.message.reply_text("📢 **Duyuru Yap:**\nToplu duyuru göndermek için:\n`/duyuru [Mesajın]` şeklinde yazmalısın kanka.", parse_mode="Markdown")

    elif data == "admin_kanal":
        if update.effective_user.id != ADMIN_ID:
            return
        ch_list = "\n".join([f"• {ch}" for ch in CHANNELS])
        await query.message.reply_text(
            f"📢 **Zorunlu Kanallar Listesi:**\n{ch_list}\n\n"
            f"➕ Kanal eklemek için: `/kanalekle @KanalAdi`\n"
            f"➖ Kanal silmek için: `/kanalsil @KanalAdi` şeklinde yazabilirsin kanka.",
            parse_mode="Markdown"
        )

# YÖNETİCİ PANELİ KOMUTU
async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Bu komutu kullanmaya yetkin yok kanka!")
        return

    total_users = len(USERS_DB)
    total_banned = len(BANNED_USERS)
    
    keyboard = [
        [InlineKeyboardButton("👥 Kullanıcıları Gör", callback_data="admin_users")],
        [InlineKeyboardButton("📢 Kanal Zorunlulukları", callback_data="admin_kanal")],
        [InlineKeyboardButton("⛔️ Ban Yönetimi", callback_data="admin_ban")],
        [InlineKeyboardButton("🚀 Duyuru Yap", callback_data="admin_duyuru")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🛠 **Yönetici Paneli**\n\n"
        f"👥 **Toplam Aktif Üye:** {total_users}\n"
        f"⛔️ **Banlanan Üye Sayısı:** {total_banned}\n\n"
        f"Aşağıdaki yönetim butonlarını kullanabilirsin kanka:",
        reply_markup=reply_markup
    )

# KANAL EKLEME / SİLME KOMUTLARI
async def kanal_ekle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Kullanım: `/kanalekle @KanalKullaniciAdi` şeklinde yaz kanka.")
        return
    
    new_ch = args[0]
    if not new_ch.startswith("@"):
        new_ch = "@" + new_ch
        
    if new_ch in CHANNELS:
        await update.message.reply_text(f"⚠️ `{new_ch}` zaten zorunlu kanallar listesinde var kanka.", parse_mode="Markdown")
    else:
        CHANNELS.append(new_ch)
        await update.message.reply_text(f"✅ `{new_ch}` başarıyla zorunlu kanallara eklendi kanka!", parse_mode="Markdown")

async def kanal_sil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Kullanım: `/kanalsil @KanalKullaniciAdi` şeklinde yaz kanka.")
        return
    
    target_ch = args[0]
    if not target_ch.startswith("@"):
        target_ch = "@" + target_ch
        
    if target_ch in CHANNELS:
        CHANNELS.remove(target_ch)
        await update.message.reply_text(f"✅ `{target_ch}` zorunlu kanallardan kaldırıldı kanka.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ `{target_ch}` listede bulunamadı kanka.", parse_mode="Markdown")

# API SORGULAMA FONKSİYONLARI (.php Uzantılı)
async def adsoyad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Kullanım: `/adsoyad [Ad] [Soyad]` şeklinde yaz kanka.")
        return
    
    name = args[0]
    surname = " ".join(args[1:])
    msg = await update.message.reply_text("🔍 Sorgulanıyor, lütfen bekleyin...")
    
    try:
        response = requests.get(f"{BASE_URL}/adsoyad.php?ad={name}&soyad={surname}", headers=HEADERS, timeout=10)
        data = response.json()
        await msg.edit_text(f"📊 **Sonuçlar:**\n```json\n{data}\n```", parse_mode="Markdown")
    except Exception:
        await msg.edit_text("❌ Sorgulama sırasında bir hata oluştu veya API yanıt vermedi.")

async def tc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Kullanım: `/tc [TCno]` şeklinde yaz kanka.")
        return
    
    tc = args[0]
    msg = await update.message.reply_text("🔍 Sorgulanıyor...")
    try:
        response = requests.get(f"{BASE_URL}/tc.php?tc={tc}", headers=HEADERS, timeout=10)
        data = response.json()
        await msg.edit_text(f"📊 **Sonuçlar:**\n```json\n{data}\n```", parse_mode="Markdown")
    except Exception:
        await msg.edit_text("❌ Sorgulama başarısız oldu.")

# PERİYODİK KANAL KONTROLÜ (Tüm kanalları tarar)
async def periodic_channel_check(app):
    with app.bot:
        for uid, uname, _ in list(USERS_DB):
            if uid in BANNED_USERS:
                continue
            missing_channels = await check_all_channels(app.bot, uid)
            if missing_channels:
                LEFT_COUNTS[uid] = LEFT_COUNTS.get(uid, 0) + 1
                count = LEFT_COUNTS[uid]
                try:
                    if count == 1:
                        await app.bot.send_message(chat_id=uid, text="⚠️ Dikkat! Zorunlu kanal(lar)ımızdan çıktığınız tespit edildi. Lütfen tekrar katılın!")
                    elif count >= 2:
                        BANNED_USERS.add(uid)
                        await app.bot.send_message(chat_id=uid, text="⛔️ Kanallardan çıktığınız için sistem tarafından banlandınız!")
                except Exception:
                    pass

async def duyuru_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Kullanım: `/duyuru [Mesajın]` şeklinde yaz kanka.")
        return
    announcement_text = " ".join(args)
    success = 0
    for uid, _, _ in USERS_DB:
        if uid in BANNED_USERS:
            continue
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 **Duyuru:**\n\n{announcement_text}", parse_mode="Markdown")
            success += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ Duyuru başarıyla {success} kişiye gönderildi kanka.")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Kullanım: `/ban [Kullanici_ID]` şeklinde yaz kanka.")
        return
    try:
        target_id = int(args[0])
        BANNED_USERS.add(target_id)
        await update.message.reply_text(f"✅ `{target_id}` ID'li kullanıcı banlandı kanka.", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("Geçerli bir ID gir kanka.")

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
    app.add_handler(CommandHandler("kanalekle", kanal_ekle))
    app.add_handler(CommandHandler("kanalsil", kanal_sil))
    app.add_handler(CommandHandler("duyuru", duyuru_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("adsoyad", adsoyad_command))
    app.add_handler(CommandHandler("tc", tc_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()
