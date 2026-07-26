import os
import html
import io
import asyncio
import threading
import logging
from datetime import datetime, date, timedelta
import requests
from flask import Flask
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import pymongo

# Logging ayarları (Loglarda detaylı hata görmek için)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_ID = 6073294253
LOG_CHANNEL_ID = -1004400643128
TOKEN = "8646358320:AAEj6rlEpCxX1aLOXspgbsTNpVaYtvvGrbE"
VIP_CONTACT = "@danistay"

# --- MONGO DB BAĞLANTISI (3 Saniye Timeout ile Kilitlenmeyi Önler) ---
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://KULLANICI_ADI:SIFRE@cluster0.xxx.mongodb.net/?retryWrites=True&w=majority")

try:
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    mongo_db = client["arastirx_bot"]
    users_col = mongo_db["users"]
    settings_col = mongo_db["settings"]
    # Bağlantıyı test et
    client.admin.command('ping')
    print("✅ MongoDB Bağlantısı Başarılı!")
except Exception as e:
    print(f"⚠️ MongoDB Bağlantı Uyarısı / Local Mod: {e}")

DEFAULT_CHANNELS = ["@arastirduyuru", "@arastirzorunlu"]

def get_settings():
    try:
        doc = settings_col.find_one({"_id": "config"})
        if not doc:
            default_config = {
                "_id": "config",
                "channels": list(DEFAULT_CHANNELS),
                "must_join": True,
                "maintenance_mode": False
            }
            settings_col.insert_one(default_config)
            return default_config
        return doc
    except Exception:
        return {"channels": DEFAULT_CHANNELS, "must_join": True, "maintenance_mode": False}

def update_settings(data):
    try:
        settings_col.update_one({"_id": "config"}, {"$set": data}, upsert=True)
    except Exception as e:
        print(f"Ayar güncelleme hatası: {e}")

# --- WEB SUNUCUSU (RENDER UYANIK TUTMA) ---
app = Flask('')

@app.route('/')
def home():
    return "AraştırX | Bot Aktif!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- YARDIMCI VE TEMİZLİK FONKSİYONLARI ---
async def delete_message_safe(message, delay=0):
    if delay > 0:
        await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

async def send_log(context: ContextTypes.DEFAULT_TYPE, log_text: str):
    if LOG_CHANNEL_ID:
        try:
            await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=log_text, parse_mode="HTML")
        except Exception as e:
            print(f"Log gönderme hatası (Engellenmiş olabilir): {e}")

def check_and_reset_daily_limit(user_id_str):
    try:
        today_str = date.today().isoformat()
        user = users_col.find_one({"user_id": user_id_str})
        if not user:
            return

        updates = {}
        if user.get("last_query_date") != today_str:
            updates["last_query_date"] = today_str
            updates["daily_queries"] = 0

        if updates:
            users_col.update_one({"user_id": user_id_str}, {"$set": updates})
    except Exception as e:
        print(f"Sıfırlama hatası: {e}")

async def register_user(user, referrer_id=None, context: ContextTypes.DEFAULT_TYPE = None):
    if not user:
        return
    
    user_id = user.id
    username = user.username if user.username else None
    first_name = user.first_name if user.first_name else ""
    uid_str = str(user_id)
    today_str = date.today().isoformat()
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    try:
        existing_user = users_col.find_one({"user_id": uid_str})

        if not existing_user:
            new_user = {
                "user_id": uid_str,
                "is_banned": False,
                "created_at": today_str,
                "created_at_formatted": now_str,
                "username": username,
                "first_name": first_name,
                "is_vip": False,
                "vip_until": None,
                "daily_queries": 0,
                "last_query_date": today_str,
                "invites_count": 0,
                "referred_by": referrer_id if (referrer_id and referrer_id != uid_str) else None
            }
            users_col.insert_one(new_user)

            if context:
                uname_str = f"@{username}" if username else "<i>Yok</i>"
                log_msg = (
                    "👤 <b>YENİ KULLANICI KATILDI!</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"<b>İsim:</b> {html.escape(first_name)}\n"
                    f"<b>Kullanıcı Adı:</b> {uname_str}\n"
                    f"<b>ID:</b> <code>{user_id}</code>\n"
                    f"<b>Tarih:</b> <code>{now_str}</code>"
                )
                await send_log(context, log_msg)
        else:
            users_col.update_one({"user_id": uid_str}, {"$set": {"username": username, "first_name": first_name}})

        check_and_reset_daily_limit(uid_str)
    except Exception as e:
        print(f"Kullanıcı kayıt hatası: {e}")

async def check_channel_subscription(user_id, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_settings()
    if not cfg.get("must_join") or not cfg.get("channels"):
        return True, []

    missing_channels = []
    for channel in cfg["channels"]:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                missing_channels.append(channel)
        except Exception:
            pass

    if missing_channels:
        return False, missing_channels

    return True, []

def build_subscription_markup(missing):
    keyboard = []
    for ch in missing:
        clean_ch = ch.replace("@", "")
        keyboard.append([InlineKeyboardButton(f"📢 Katıl: {ch}", url=f"https://t.me/{clean_ch}")])
    keyboard.append([InlineKeyboardButton("✅ Katıldım, Onayla", callback_data="check_subs")])
    return InlineKeyboardMarkup(keyboard)

# --- MENÜLER ---
def build_main_menu(user_id):
    try:
        u_data = users_col.find_one({"user_id": str(user_id)}) or {}
    except Exception:
        u_data = {}
        
    is_vip = u_data.get("is_vip", False) or (user_id == ADMIN_ID)
    daily = u_data.get("daily_queries", 0)
    kalan = "Sınırsız ♾️" if is_vip else f"{max(0, 7 - daily)} / 7"

    text = (
        "🔍 <b>AraştırX | Analiz Botu</b> Paneline Hoş Geldiniz!\n\n"
        f"📊 <b>Kalan Günlük Sorgu Hakkınız:</b> <code>{kalan}</code>\n"
        "İşlem yapmak için aşağıdaki menüden bir kategori seçin:"
    )
    keyboard = [
        [InlineKeyboardButton("🤵 Ad Soyad Sorgula", callback_data="query_adsoyad"), InlineKeyboardButton("🖨️ TC Sorgula", callback_data="query_tc")],
        [InlineKeyboardButton("🏢 İşyeri Sorgula", callback_data="query_isyeri"), InlineKeyboardButton("📍 Adres Sorgula", callback_data="query_adres")],
        [InlineKeyboardButton("👥 Aile Sorgula", callback_data="query_aile"), InlineKeyboardButton("👥 Sülale Sorgula", callback_data="query_sulale")],
        [InlineKeyboardButton("👶 Çocuk Sorgula", callback_data="query_cocuk")],
        [InlineKeyboardButton("📱 TC-GSM Sorgula", callback_data="query_tcgsm"), InlineKeyboardButton("📱 GSM-TC Sorgula", callback_data="query_gsmtc")],
        [InlineKeyboardButton("👤 Profil Kartım", callback_data="user_profile"), InlineKeyboardButton("🔗 Davet Et / VIP Kazan", callback_data="user_ref")],
        [InlineKeyboardButton("👑 VIP Satın Al / Fiyatlar", callback_data="vip_prices")]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def build_profile_card(user):
    uid_str = str(user.id)
    check_and_reset_daily_limit(uid_str)
    try:
        u_data = users_col.find_one({"user_id": uid_str}) or {}
    except Exception:
        u_data = {}

    first_name = html.escape(u_data.get("first_name", user.first_name or "Bilinmiyor"))
    uname = u_data.get("username")
    uname_str = f"@{uname}" if uname else "<i>Yok</i>"
    
    is_admin = (user.id == ADMIN_ID)
    role_str = "Yönetici 👑" if is_admin else "Kullanıcı 👤"
    
    is_vip = u_data.get("is_vip", False) or is_admin
    vip_str = "✅ Aktif" if is_vip else "❌ Pasif"

    invites = u_data.get("invites_count", 0)
    created = u_data.get("created_at_formatted", u_data.get("created_at", "Bilinmiyor"))

    card_text = (
        "👤 <b>Profesyonel Profil Kartı</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Ad Soyad:</b> {first_name}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
        f"🔗 <b>Kullanıcı Adı:</b> {uname_str}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <b>Rol:</b> {role_str}\n"
        f"👑 <b>Bot VIP:</b> {vip_str}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🔔 <b>Davet Sayısı:</b> <code>{invites}</code>\n"
        f"⏰ <b>İlk Giriş:</b> <code>{created}</code>"
    )
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Ana Menü", callback_data="menu_home")]])
    return card_text, keyboard

def build_admin_panel():
    try:
        total_users = users_col.count_documents({})
        banned_users = users_col.count_documents({"is_banned": True})
        vip_users = users_col.count_documents({"is_vip": True})
    except Exception:
        total_users, banned_users, vip_users = 0, 0, 0

    cfg = get_settings()
    channels = cfg.get("channels", [])
    channels_str = "\n".join([f"• {c}" for c in channels]) if channels else "<i>Ekli kanal yok.</i>"
    must_join_status = "🟢 AÇIK" if cfg.get("must_join") else "🔴 KAPALI"
    maint_status = "🟢 AÇIK" if cfg.get("maintenance_mode") else "🔴 KAPALI"

    panel_text = (
        "⚙️ <b>AraştırX | Yönetici Paneli</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Toplam Kullanıcı:</b> <code>{total_users}</code>\n"
        f"👑 <b>VIP:</b> <code>{vip_users}</code> | 🚫 <b>Banlı:</b> <code>{banned_users}</code>\n"
        f"🛠️ <b>Bakım Modu:</b> {maint_status} | 📢 <b>Kanal Şartı:</b> {must_join_status}\n\n"
        f"📌 <b>Kanallar:</b>\n{channels_str}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    
    keyboard = [
        [InlineKeyboardButton("👑 VIP Ver", callback_data="btn_add_vip"), InlineKeyboardButton("❌ VIP Kaldır", callback_data="btn_del_vip")],
        [InlineKeyboardButton(f"Bakım Modu: {maint_status}", callback_data="toggle_maintenance"), InlineKeyboardButton(f"Kanal Şartı: {must_join_status}", callback_data="toggle_channel_req")],
        [InlineKeyboardButton("🔄 Paneli Yenile", callback_data="refresh_admin")]
    ]
    return panel_text, InlineKeyboardMarkup(keyboard)

# --- START & PANEL ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    asyncio.create_task(delete_message_safe(update.message))

    referrer_id = None
    if context.args and context.args[0].startswith("ref_"):
        referrer_id = context.args[0].replace("ref_", "")

    await register_user(update.effective_user, referrer_id, context)
    user_id = update.effective_user.id
    cfg = get_settings()

    if cfg.get("maintenance_mode") and user_id != ADMIN_ID:
        try:
            msg = await update.message.reply_text("⚙️ <b>SİSTEM BAKIMDA!</b>", parse_mode="HTML")
            asyncio.create_task(delete_message_safe(msg, 5))
        except Exception: pass
        return

    is_ok, missing = await check_channel_subscription(user_id, context)
    if not is_ok:
        text = "⚠️ <b>ZORUNLU KANAL ÜYELİĞİ EKSİK!</b>\n\nLütfen aşağıdaki kanallara katılıp onaylayın:"
        try:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=build_subscription_markup(missing))
        except Exception: pass
        return

    menu_text, keyboard = build_main_menu(user_id)
    try:
        await update.message.reply_text(menu_text, parse_mode="HTML", reply_markup=keyboard)
    except Exception: pass

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    asyncio.create_task(delete_message_safe(update.message))
    await register_user(update.effective_user, context=context)
    if update.effective_user.id != ADMIN_ID:
        return

    text, keyboard = build_admin_panel()
    try:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception: pass

# --- BUTON YÖNETİMİ ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await register_user(query.from_user, context=context)
    user_id = query.from_user.id
    data = query.data
    cfg = get_settings()

    try:
        if data == "check_subs":
            is_ok, missing = await check_channel_subscription(user_id, context)
            if is_ok:
                await query.answer("✅ Üyelikler onaylandı!")
                text, keyboard = build_main_menu(user_id)
                await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
            else:
                await query.answer("⚠️ Hâlâ eksik kanallar var!", show_alert=True)
            return

        elif data == "user_profile":
            await query.answer()
            text, keyboard = build_profile_card(query.from_user)
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "vip_prices":
            await query.answer()
            vip_text = (
                "⚡ <b>AĞUSTOS AYINA ÖZEL VIP KAMPANYASI!</b> ⚡\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "👑 <b>1 Aylık VIP:</b> <b>1.250 ₺</b>\n"
                "🔥 <b>3 Aylık VIP:</b> <b>2.500 ₺</b>\n"
                "♾️ <b>Sınırsız VIP:</b> <b>12.500 ₺</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"📲 <b>İletişim:</b> {VIP_CONTACT}"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Yetkili İle İletişime Geç", url=f"https://t.me/{VIP_CONTACT.replace('@','')}")],
                [InlineKeyboardButton("⬅️ Ana Menü", callback_data="menu_home")]
            ])
            await query.edit_message_text(text=vip_text, parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "menu_home":
            await query.answer()
            context.user_data['waiting_for_query'] = False
            text, keyboard = build_main_menu(user_id)
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
            return

        if data.startswith("query_"):
            q_type = data.split("_")[1]
            context.user_data['waiting_for_query'] = True
            context.user_data['current_query_type'] = q_type
            context.user_data['menu_message_id'] = query.message.message_id
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ İptal Et", callback_data="menu_home")]])
            await query.edit_message_text(
                f"🔍 <b>{q_type.upper()} Sorgulama Ekranı</b>\n\nLütfen sorgulamak istediğiniz bilgiyi mesaja yazıp gönderin:",
                parse_mode="HTML",
                reply_markup=keyboard
            )
    except Exception as e:
        print(f"Buton Hatasi: {e}")

# --- GENEL HATA YAKALAYICI (BOTUN KANIP KİLİTLENMESİNİ ÖNLER) ---
async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Botta yakalanmayan bir hata oluştu:", exc_info=context.error)

if __name__ == '__main__':
    keep_alive()
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Global Hata Yakalayıcıyı Ekle
    application.add_error_handler(global_error_handler)
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("panel", panel_command))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("🚀 Bot Polling Başlatıldı...")
    application.run_polling()
