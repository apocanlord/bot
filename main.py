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

# Logging Ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_ID = 6073294253
LOG_CHANNEL_ID = -1004400643128
TOKEN = "8646358320:AAEj6rlEpCxX1aLOXspgbsTNpVaYtvvGrbE"
VIP_CONTACT = "@danistay"

# --- MONGO DB BAĞLANTISI ---
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://KULLANICI_ADI:SIFRE@cluster0.xxx.mongodb.net/?retryWrites=True&w=majority")

try:
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    mongo_db = client["arastirx_bot"]
    users_col = mongo_db["users"]
    settings_col = mongo_db["settings"]
    client.admin.command('ping')
    print("✅ MongoDB Bağlantısı Başarılı!")
except Exception as e:
    print(f"⚠️ MongoDB Bağlantı Uyarısı: {e}")

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
        return {"channels": list(DEFAULT_CHANNELS), "must_join": True, "maintenance_mode": False}

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

# --- YARDIMCI İŞLEMLER ---
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
            print(f"Log gönderme hatası: {e}")

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

        if user.get("is_vip") and user.get("vip_until"):
            try:
                vip_date = datetime.strptime(user["vip_until"], "%Y-%m-%d").date()
                if date.today() > vip_date:
                    updates["is_vip"] = False
                    updates["vip_until"] = None
            except Exception: pass

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
    if is_vip and u_data.get("vip_until"):
        vip_str += f" ({u_data['vip_until']} kadar)"

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

# BİREBİR EKRAN GÖRÜNTÜSÜNDEKİ PANEL DÜZENİ
def build_admin_panel():
    today_str = date.today().isoformat()
    cfg = get_settings()

    try:
        total_users = users_col.count_documents({})
        banned_users = users_col.count_documents({"is_banned": True})
        vip_users = users_col.count_documents({"is_vip": True})
        today_users = users_col.count_documents({"created_at": today_str})
    except Exception:
        total_users, banned_users, vip_users, today_users = 0, 0, 0, 0

    channels = cfg.get("channels", [])
    channels_str = "\n".join([f"• {c}" for c in channels]) if channels else "<i>Ekli kanal yok.</i>"
    must_join_status = "🟢 AÇIK" if cfg.get("must_join") else "🔴 KAPALI"
    maint_status = "🔴 KAPALI" if not cfg.get("maintenance_mode") else "🟢 AÇIK"
    
    maint_btn_txt = f"Bakım Modu: 🔴 K..." if not cfg.get("maintenance_mode") else "Bakım Modu: 🟢 A..."
    must_join_btn_txt = f"Kanal Şartı: {must_join_status}"

    panel_text = (
        "⚙️ <b>AraştırX | Yönetici Paneli</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Bugün Gelen:</b> {today_users} | 📊 <b>Toplam:</b> {total_users}\n"
        f"👑 <b>VIP:</b> {vip_users} | 🚫 <b>Banlı:</b> {banned_users}\n"
        f"🛠️ <b>Bakım Modu:</b> {maint_status} | 📢 <b>Kanal Şartı:</b> {must_join_status}\n\n"
        f"📌 <b>Kanallar:</b>\n{channels_str}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    
    # EKRAN GÖRÜNTÜSÜNDEKİ BİREBİR BUTON DİZİLİMİ
    keyboard = [
        [InlineKeyboardButton("👑 VIP Ver / Süre T...", callback_data="btn_add_vip"), InlineKeyboardButton("❌ VIP Kaldır", callback_data="btn_del_vip")],
        [InlineKeyboardButton(maint_btn_txt, callback_data="toggle_maintenance"), InlineKeyboardButton(must_join_btn_txt, callback_data="toggle_channel_req")],
        [InlineKeyboardButton("➕ Kanal Ekle", callback_data="btn_add_channel"), InlineKeyboardButton("➖ Kanal Sil", callback_data="btn_del_channel")],
        [InlineKeyboardButton("📢 Duyuru Gönder", callback_data="btn_broadcast"), InlineKeyboardButton("👥 Kullanıcı Listesi", callback_data="btn_user_list")],
        [InlineKeyboardButton("⛔ Banla / Ban Kaldır", callback_data="btn_ban")],
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

    if cfg.get("maintenance_mode") and user_id != ADMIN_ID:
        await query.answer("⚙️ Sistem bakımdadır!", show_alert=True)
        return

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

        elif data == "user_ref":
            await query.answer()
            bot_username = (await context.bot.get_me()).username
            ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
            try:
                u_data = users_col.find_one({"user_id": str(user_id)}) or {}
            except Exception: u_data = {}
            inv_count = u_data.get("invites_count", 0)

            ref_text = (
                "🔗 <b>KİŞİSEL DAVET (REFERANS) SİSTEMİ</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "🎁 <b>Ödül:</b> 10 Arkadaşını davet et, <b>3 GÜN ÜCRETSİZ VIP</b> kazan!\n\n"
                f"📊 <b>Toplam Davet Sayınız:</b> <code>{inv_count} / 10</code>\n\n"
                f"👉 <b>Özel Davet Linkiniz:</b>\n<code>{ref_link}</code>"
            )
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Ana Menü", callback_data="menu_home")]])
            await query.edit_message_text(text=ref_text, parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "vip_prices":
            await query.answer()
            vip_text = (
                "⚡ <b>AĞUSTOS AYINA ÖZEL VIP KAMPANYASI!</b> ⚡\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "👑 <b>1 Aylık Premium:</b> <s>2.500 ₺</s> ➡️ <b>1.250 ₺</b>\n"
                "🔥 <b>3 Aylık VIP Plus:</b> <s>5.000 ₺</s> ➡️ <b>2.500 ₺</b>\n"
                "💎 <b>6 Aylık VIP Pro:</b> <b>4.500 ₺</b>\n"
                "🎖️ <b>12 Aylık VIP:</b> <b>7.500 ₺</b>\n"
                "♾️ <b>Sınırsız VIP:</b> <b>12.500 ₺</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"📲 <b>Satın Alım İletişim:</b> {VIP_CONTACT}"
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

        # ADMIN BUTONLARI
        if user_id == ADMIN_ID:
            if data == "refresh_admin":
                await query.answer("🔄 Panel yenilendi!")
                text, keyboard = build_admin_panel()
                await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
                return

            elif data == "btn_add_vip":
                await query.answer()
                context.user_data['admin_action'] = 'add_vip'
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal", callback_data="admin_back")]])
                await query.edit_message_text("👑 VIP vereceğiniz kullanıcının <b>ID ve Gün</b> sayısını yazın:\n<i>(Örn: 6073294253 30)</i>", parse_mode="HTML", reply_markup=kb)
                return

            elif data == "btn_del_vip":
                await query.answer()
                context.user_data['admin_action'] = 'del_vip'
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal", callback_data="admin_back")]])
                await query.edit_message_text("❌ VIP kaldırılacak kullanıcının ID'sini yazın:", parse_mode="HTML", reply_markup=kb)
                return

            elif data == "btn_add_channel":
                await query.answer()
                context.user_data['admin_action'] = 'add_channel'
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal", callback_data="admin_back")]])
                await query.edit_message_text("➕ Eklemek istediğiniz kanal kullanıcı adını yazın:\n<i>(Örn: @arastirduyuru)</i>", parse_mode="HTML", reply_markup=kb)
                return

            elif data == "btn_del_channel":
                await query.answer()
                context.user_data['admin_action'] = 'del_channel'
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal", callback_data="admin_back")]])
                await query.edit_message_text("➖ Çıkarmak istediğiniz kanal adını yazın:\n<i>(Örn: @arastirduyuru)</i>", parse_mode="HTML", reply_markup=kb)
                return

            elif data == "btn_broadcast":
                await query.answer()
                context.user_data['admin_action'] = 'broadcast'
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal", callback_data="admin_back")]])
                await query.edit_message_text("📢 Tüm kullanıcılara gönderilecek <b>duyuru mesajını</b> yazın:", parse_mode="HTML", reply_markup=kb)
                return

            elif data == "btn_user_list":
                await query.answer("👥 Liste hazırlanıyor...")
                all_users = list(users_col.find({}))
                txt = f"👥 <b>KULLANICI LİSTESİ ({len(all_users)} Kişi)</b>\n━━━━━━━━━━━━━━━━━━\n"
                for idx, u in enumerate(all_users[:50], 1): # İlk 50 kişi
                    uname = f"@{u.get('username')}" if u.get('username') else "Yok"
                    txt += f"{idx}. <code>{u.get('user_id')}</code> | {uname} | VIP: {u.get('is_vip', False)}\n"
                if len(all_users) > 50:
                    txt += f"\n<i>...ve {len(all_users) - 50} kullanıcı daha.</i>"
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Panele Dön", callback_data="admin_back")]])
                await query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
                return

            elif data == "btn_ban":
                await query.answer()
                context.user_data['admin_action'] = 'ban_user'
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal", callback_data="admin_back")]])
                await query.edit_message_text("⛔ Banlanacak veya Banı kaldırılacak kullanıcının <b>ID'sini</b> yazın:", parse_mode="HTML", reply_markup=kb)
                return

            elif data == "toggle_maintenance":
                new_val = not cfg.get("maintenance_mode", False)
                update_settings({"maintenance_mode": new_val})
                text, keyboard = build_admin_panel()
                await query.answer("Bakım modu değiştirildi!")
                await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
                return

            elif data == "toggle_channel_req":
                new_val = not cfg.get("must_join", True)
                update_settings({"must_join": new_val})
                text, keyboard = build_admin_panel()
                await query.answer("Kanal şartı değiştirildi!")
                await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
                return

            elif data == "admin_back":
                context.user_data['admin_action'] = None
                await query.answer()
                text, keyboard = build_admin_panel()
                await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
                return

        # SORGU SEÇİMLERİ
        if data.startswith("query_"):
            q_type = data.split("_")[1]
            try:
                u_data = users_col.find_one({"user_id": str(user_id)}) or {}
            except Exception: u_data = {}

            is_vip = u_data.get("is_vip", False) or (user_id == ADMIN_ID)
            daily_count = u_data.get("daily_queries", 0)

            if not is_vip and daily_count >= 7:
                await query.answer("⚠️ Günlük 7 sorgu limitiniz doldu! VIP paketlerini inceleyin.", show_alert=True)
                return

            context.user_data['waiting_for_query'] = True
            context.user_data['current_query_type'] = q_type
            context.user_data['menu_message_id'] = query.message.message_id
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ İptal Et / Ana Menü", callback_data="menu_home")]])
            await query.edit_message_text(
                f"🔍 <b>{q_type.upper()} Sorgulama Ekranı</b>\n\n"
                f"Lütfen aratmak istediğiniz bilgiyi mesaja yazıp gönderin:\n"
                f"<i>(Mesajınız otomatik olarak temizlenecektir.)</i>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
    except Exception as e:
        print(f"Buton Hatasi: {e}")

def format_data_text(data, indent=0):
    text = ""
    prefix = "  " * indent
    if isinstance(data, dict):
        for k, v in data.items():
            k_safe = html.escape(str(k))
            if isinstance(v, (dict, list)):
                text += f"{prefix}🔹 <b>{k_safe.upper()}:</b>\n" + format_data_text(v, indent + 1)
            else:
                v_safe = html.escape(str(v))
                text += f"{prefix}🔹 <b>{k_safe}:</b> <code>{v_safe}</code>\n"
    elif isinstance(data, list):
        for idx, item in enumerate(data, 1):
            if isinstance(item, (dict, list)):
                text += f"{prefix}📌 <b>Kayıt {idx}:</b>\n" + format_data_text(item, indent + 1)
            else:
                item_safe = html.escape(str(item))
                text += f"{prefix}• <code>{item_safe}</code>\n"
    return text

def generate_html_file(q_type, data):
    rendered_body = format_data_text(data)
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>AraştırX - {q_type.upper()} Raporu</title>
    <style>
        body {{ background-color: #0d1117; color: #c9d1d9; font-family: sans-serif; padding: 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; background: #161b22; padding: 25px; border-radius: 12px; border: 1px solid #30363d; }}
        h2 {{ color: #58a6ff; border-bottom: 2px solid #21262d; padding-bottom: 10px; }}
        pre {{ background-color: #0d1117; padding: 15px; border-radius: 8px; border: 1px solid #30363d; white-space: pre-wrap; }}
        b {{ color: #79c0ff; }} code {{ color: #7ee787; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>🔍 AraştırX | {q_type.upper()} Sonuçları</h2>
        <pre>{rendered_body}</pre>
    </div>
</body>
</html>"""

# --- MESAJ İŞLEME ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    asyncio.create_task(delete_message_safe(update.message))

    await register_user(update.effective_user, context=context)
    user_id = update.effective_user.id
    text_input = update.message.text.strip()
    u_name = update.effective_user.username
    u_str = f"@{u_name}" if u_name else "<i>Kullanıcı Adı Yok</i>"

    cfg = get_settings()
    if cfg.get("maintenance_mode") and user_id != ADMIN_ID:
        return

    # ADMIN ÖZEL İŞLEMLERİ
    if user_id == ADMIN_ID and context.user_data.get('admin_action'):
        action = context.user_data.get('admin_action')
        context.user_data['admin_action'] = None

        if action == 'add_vip':
            try:
                parts = text_input.split(" ")
                target_uid, days = parts[0], int(parts[1]) if len(parts) > 1 else 30
                users_col.update_one(
                    {"user_id": target_uid},
                    {"$set": {"is_vip": True, "vip_until": (date.today() + timedelta(days=days)).isoformat()}}
                )
                await send_log(context, f"👑 <b>VIP VERİLDİ!</b>\nID: <code>{target_uid}</code> ({days} Gün)")
            except Exception: pass

        elif action == 'del_vip':
            try:
                users_col.update_one({"user_id": text_input}, {"$set": {"is_vip": False, "vip_until": None}})
                await send_log(context, f"❌ <b>VIP KALDIRILDI!</b>\nID: <code>{text_input}</code>")
            except Exception: pass

        elif action == 'add_channel':
            try:
                ch_list = cfg.get("channels", [])
                if text_input not in ch_list:
                    ch_list.append(text_input)
                    update_settings({"channels": ch_list})
            except Exception: pass

        elif action == 'del_channel':
            try:
                ch_list = cfg.get("channels", [])
                if text_input in ch_list:
                    ch_list.remove(text_input)
                    update_settings({"channels": ch_list})
            except Exception: pass

        elif action == 'broadcast':
            try:
                all_users = users_col.find({})
                success, fail = 0, 0
                for u in all_users:
                    try:
                        await context.bot.send_message(chat_id=int(u['user_id']), text=f"📢 <b>DUYURU</b>\n\n{text_input}", parse_mode="HTML")
                        success += 1
                    except Exception: fail += 1
                await send_log(context, f"📢 <b>DUYURU TAMAMLANDI!</b>\n✅ Başarılı: {success}\n❌ Başarısız: {fail}")
            except Exception: pass

        elif action == 'ban_user':
            try:
                u_doc = users_col.find_one({"user_id": text_input})
                if u_doc:
                    new_ban = not u_doc.get("is_banned", False)
                    users_col.update_one({"user_id": text_input}, {"$set": {"is_banned": new_ban}})
                    ban_str = "BANLANDI ⛔" if new_ban else "BANI KALDIRILDI ✅"
                    await send_log(context, f"👤 Kullanıcı ID: <code>{text_input}</code> {ban_str}")
            except Exception: pass

        text, keyboard = build_admin_panel()
        menu_msg_id = context.user_data.get('menu_message_id')
        if menu_msg_id:
            try: await context.bot.edit_message_text(chat_id=user_id, message_id=menu_msg_id, text=text, parse_mode="HTML", reply_markup=keyboard)
            except Exception: pass
        return

    # SORGU İŞLEMLERİ
    if context.user_data.get('waiting_for_query'):
        q_type = context.user_data.get('current_query_type', 'islem')
        menu_msg_id = context.user_data.get('menu_message_id')
        context.user_data['waiting_for_query'] = False

        try: u_data = users_col.find_one({"user_id": str(user_id)}) or {}
        except Exception: u_data = {}
        daily_count = u_data.get("daily_queries", 0)

        if menu_msg_id:
            try: await context.bot.edit_message_text(chat_id=user_id, message_id=menu_msg_id, text="⏳ <b>Sorgulanıyor, lütfen bekleyin...</b>", parse_mode="HTML")
            except Exception: pass

        try: users_col.update_one({"user_id": str(user_id)}, {"$set": {"daily_queries": daily_count + 1}})
        except Exception: pass

        await send_log(context, f"🔍 <b>SORGU:</b> {u_str} | <code>{q_type.upper()}</code> | <code>{html.escape(text_input)}</code>")

        try:
            base_api = "http://arastir.vip/api"
            params = {}
            if q_type == "adsoyad":
                parts = text_input.split(" ", 1)
                params['ad'] = parts[0]
                if len(parts) > 1: params['soyad'] = parts[1]
                endpoint = f"{base_api}/adsoyad.php"
            elif q_type == "gsmtc":
                params['gsm'] = text_input
                endpoint = f"{base_api}/gsmtc.php"
            else:
                params['tc'] = text_input
                endpoint = f"{base_api}/{q_type}.php"
            
            response = requests.get(endpoint, params=params, timeout=15)
            
            if response.status_code == 200:
                res_json = response.json()
                if res_json.get("success"):
                    data = res_json.get("data")
                    count = res_json.get("count", None)
                    raw_formatted = format_data_text(data)
                    
                    sonuc_mesaji = f"✅ <b>Sorgu Başarılı ({q_type.upper()})</b>\n"
                    if count is not None: sonuc_mesaji += f"📊 <b>Bulunan Kayıt:</b> <code>{count}</code>\n"
                    sonuc_mesaji += "━━━━━━━━━━━━━━━━━━\n" + raw_formatted + "━━━━━━━━━━━━━━━━━━"
                    
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Ana Menüye Dön", callback_data="menu_home")]])

                    if len(sonuc_mesaji) > 3500:
                        full_html = generate_html_file(q_type, data)
                        html_bytes = io.BytesIO(full_html.encode('utf-8'))
                        html_bytes.name = f"ArastirX_{q_type}_{text_input}.html"
                        
                        if menu_msg_id:
                            try: await context.bot.delete_message(chat_id=user_id, message_id=menu_msg_id)
                            except Exception: pass

                        await context.bot.send_document(
                            chat_id=user_id,
                            document=html_bytes,
                            caption=f"✅ <b>Sorgu Başarılı ({q_type.upper()})</b>\n📄 <i>Sonuç HTML dosyası olarak hazırlandı.</i>",
                            parse_mode="HTML",
                            reply_markup=keyboard
                        )
                    else:
                        if menu_msg_id:
                            await context.bot.edit_message_text(chat_id=user_id, message_id=menu_msg_id, text=sonuc_mesaji, parse_mode="HTML", reply_markup=keyboard)
                else:
                    err = html.escape(str(res_json.get("error", "Kayıt bulunamadı.")))
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Ana Menü", callback_data="menu_home")]])
                    if menu_msg_id:
                        await context.bot.edit_message_text(chat_id=user_id, message_id=menu_msg_id, text=f"⚠️ <b>Hata:</b> {err}", parse_mode="HTML", reply_markup=keyboard)
            else:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Ana Menü", callback_data="menu_home")]])
                if menu_msg_id:
                    await context.bot.edit_message_text(chat_id=user_id, message_id=menu_msg_id, text=f"❌ API Sunucu Hatası: {response.status_code}", parse_mode="HTML", reply_markup=keyboard)

        except Exception as e:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Ana Menü", callback_data="menu_home")]])
            if menu_msg_id:
                await context.bot.edit_message_text(chat_id=user_id, message_id=menu_msg_id, text=f"❌ Sistem Hatası: {html.escape(str(e))}", parse_mode="HTML", reply_markup=keyboard)

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Botta hata oluştu:", exc_info=context.error)

if __name__ == '__main__':
    keep_alive()
    
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_error_handler(global_error_handler)
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("panel", panel_command))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 Bot Polling Başlatıldı...")
    application.run_polling()
