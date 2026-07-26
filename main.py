import os
import json
import html
import io
import asyncio
import threading
from datetime import datetime, date, timedelta
import requests
from flask import Flask
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

ADMIN_ID = 6073294253
LOG_CHANNEL_ID = -1004400643128
TOKEN = "8646358320:AAEj6rlEpCxX1aLOXspgbsTNpVaYtvvGrbE"
VIP_CONTACT = "@danistay"

# --- VERİTABANI YÖNETİMİ ---
DATA_FILE = "bot_data.json"
DEFAULT_CHANNELS = ["@arastirduyuru", "@arastirzorunlu"]

def load_data():
    data = {
        "users": {},
        "channels": list(DEFAULT_CHANNELS),
        "must_join": True,
        "maintenance_mode": False
    }
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
                if "users" in saved_data: data["users"].update(saved_data["users"])
                if "channels" in saved_data: data["channels"] = list(set(saved_data["channels"] + DEFAULT_CHANNELS))
                if "must_join" in saved_data: data["must_join"] = saved_data["must_join"]
                if "maintenance_mode" in saved_data: data["maintenance_mode"] = saved_data["maintenance_mode"]
        except Exception:
            pass
    return data

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Veri kaydetme hatası: {e}")

db = load_data()
duyuru_iptal_flag = False

# --- 1. Render Web Sunucusu ---
app = Flask('')

@app.route('/')
def home():
    return "AraştırX | Analiz Botu Aktif ve Çalışıyor!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

# --- YARDIMCI FONKSİYONLAR & LOG ---
async def send_log(context: ContextTypes.DEFAULT_TYPE, log_text: str):
    if LOG_CHANNEL_ID:
        try:
            await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=log_text, parse_mode="HTML")
        except Exception as e:
            print(f"Log gönderme hatası: {e}")

def check_and_reset_daily_limit(user_id_str):
    """Kullanıcının günlük sorgu hakkını gün değiştiyse sıfırlar ve VIP süresini kontrol eder."""
    today_str = date.today().isoformat()
    user = db["users"].get(user_id_str)
    if not user:
        return

    # Günlük Sayaç Sıfırlama
    if user.get("last_query_date") != today_str:
        user["last_query_date"] = today_str
        user["daily_queries"] = 0
        save_data(db)

    # VIP Süre Kontrolü
    if user.get("is_vip") and user.get("vip_until"):
        try:
            vip_date = datetime.strptime(user["vip_until"], "%Y-%m-%d").date()
            if date.today() > vip_date:
                user["is_vip"] = False
                user["vip_until"] = None
                save_data(db)
        except Exception:
            pass

async def register_user(user, referrer_id=None, context: ContextTypes.DEFAULT_TYPE = None):
    if not user:
        return
    
    user_id = user.id
    username = user.username if user.username else None
    first_name = user.first_name if user.first_name else ""
    uid_str = str(user_id)
    today_str = date.today().isoformat()
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    if uid_str not in db["users"]:
        db["users"][uid_str] = {
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
        save_data(db)

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
        # Bilgileri güncelle
        db["users"][uid_str]["username"] = username
        db["users"][uid_str]["first_name"] = first_name
        save_data(db)

    check_and_reset_daily_limit(uid_str)

async def check_channel_subscription(user_id, context: ContextTypes.DEFAULT_TYPE):
    uid_str = str(user_id)
    user_info = db["users"].get(uid_str, {"is_banned": False})

    if user_info.get("is_banned"):
        return False, ["BANNED"]

    if not db["must_join"] or not db["channels"]:
        return True, []

    missing_channels = []
    for channel in db["channels"]:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                missing_channels.append(channel)
        except Exception:
            pass

    if missing_channels:
        return False, missing_channels

    return True, []

async def send_subscription_warning(chat_id, user_id, missing, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⚠️ <b>ZORUNLU KANAL ÜYELİĞİ EKSİK!</b>\n\n"
        "Bu botu kullanabilmek için aşağıdaki kanallara katılmış olmanız gerekmektedir.\n\n"
        "Lütfen kanallara katıldıktan sonra <b>'✅ Katıldım, Onayla'</b> butonuna basın:"
    )
    
    keyboard = []
    for ch in missing:
        clean_ch = ch.replace("@", "")
        keyboard.append([InlineKeyboardButton(f"📢 Katıl: {ch}", url=f"https://t.me/{clean_ch}")])
    keyboard.append([InlineKeyboardButton("✅ Katıldım, Onayla", callback_data="check_subs")])

    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# --- 2. START KOMUTU & ANA MENÜ ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Referans linki tespiti (örn: /start ref_123456)
    referrer_id = None
    if context.args and context.args[0].startswith("ref_"):
        referrer_id = context.args[0].replace("ref_", "")

    await register_user(update.effective_user, referrer_id, context)
    user_id = update.effective_user.id

    if db.get("maintenance_mode") and user_id != ADMIN_ID:
        await update.message.reply_text("⚙️ <b>SİSTEM BAKIMDA!</b>\n\nBot şu an bakım çalışması nedeniyle hizmet dışıdır.", parse_mode="HTML")
        return

    if db["users"].get(str(user_id), {}).get("is_banned"):
        await update.message.reply_text("⛔ <b>Sistemden Banlandınız!</b>", parse_mode="HTML")
        return

    is_ok, missing = await check_channel_subscription(user_id, context)
    if not is_ok:
        if missing == ["BANNED"]:
            await update.message.reply_text("⛔ <b>Sistemden Banlandınız!</b>", parse_mode="HTML")
            return
        await send_subscription_warning(update.effective_chat.id, user_id, missing, context)
        return

    menu_text, keyboard = build_main_menu(user_id)
    await update.message.reply_text(menu_text, parse_mode="HTML", reply_markup=keyboard)

def build_main_menu(user_id):
    u_data = db["users"].get(str(user_id), {})
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
        [InlineKeyboardButton("👤 Profesyonel Profil Kartı", callback_data="user_profile"), InlineKeyboardButton("🔗 Davet Et / Kazan", callback_data="user_ref")],
        [InlineKeyboardButton("👑 VIP Satın Al / Destek", url=f"https://t.me/{VIP_CONTACT.replace('@','')}")]
    ]
    return text, InlineKeyboardMarkup(keyboard)

# --- 3. PROFİL KARTI VE DAVET SİSTEMİ ---
def build_profile_card(user):
    uid_str = str(user.id)
    u_data = db["users"].get(uid_str, {})
    check_and_reset_daily_limit(uid_str)

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
        f"🌐 <b>Dil:</b> TR\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <b>Rol:</b> {role_str}\n"
        f"🚫 <b>Durum:</b> ✅ Aktif\n"
        f"👑 <b>Bot VIP:</b> {vip_str}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🔔 <b>Davet Sayısı:</b> <code>{invites}</code>\n"
        f"⏰ <b>İlk Giriş:</b> <code>{created}</code>"
    )
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Ana Menü", callback_data="menu_home")]])
    return card_text, keyboard

# --- 4. YÖNETİCİ PANELİ ---
def build_admin_panel():
    today_str = date.today().isoformat()
    total_users = len(db["users"])
    banned_users = sum(1 for u in db["users"].values() if u.get("is_banned"))
    vip_users = sum(1 for u in db["users"].values() if u.get("is_vip"))
    today_users = sum(1 for u in db["users"].values() if u.get("created_at") == today_str)

    channels_str = "\n".join([f"• {c}" for c in db["channels"]]) if db["channels"] else "<i>Ekli kanal yok.</i>"
    must_join_status = "🟢 AÇIK" if db["must_join"] else "🔴 KAPALI"
    maint_status = "🟢 AÇIK" if db.get("maintenance_mode") else "🔴 KAPALI"

    panel_text = (
        "⚙️ <b>AraştırX | Yönetici Paneli</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Bugün Gelen Kullanıcı:</b> <code>{today_users}</code>\n"
        f"📊 <b>Toplam Kullanıcı:</b> <code>{total_users}</code>\n"
        f"👑 <b>VIP Kullanıcı:</b> <code>{vip_users}</code>\n"
        f"🚫 <b>Banlı Kullanıcı:</b> <code>{banned_users}</code>\n"
        f"🛠️ <b>Bakım Modu:</b> {maint_status}\n"
        f"📢 <b>Kanal Zorunluluğu:</b> {must_join_status}\n\n"
        f"📌 <b>Ekli Bulunan Kanallar:</b>\n{channels_str}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Yönetici işlemlerini aşağıdaki butonlardan yapabilirsiniz:"
    )
    
    keyboard = [
        [InlineKeyboardButton("👑 VIP Ver / Süre Tanımla", callback_data="btn_add_vip"), InlineKeyboardButton("❌ VIP Kaldır", callback_data="btn_del_vip")],
        [InlineKeyboardButton(f"Bakım Modu: {maint_status}", callback_data="toggle_maintenance"), InlineKeyboardButton(f"Kanal Zorunluluğu: {must_join_status}", callback_data="toggle_channel_req")],
        [InlineKeyboardButton("➕ Kanal Ekle", callback_data="btn_add_channel"), InlineKeyboardButton("➖ Kanal Sil", callback_data="btn_del_channel")],
        [InlineKeyboardButton("📢 Duyuru Gönder", callback_data="btn_broadcast"), InlineKeyboardButton("🛑 Duyuru İptal", callback_data="btn_cancel_broadcast")],
        [InlineKeyboardButton("👥 Kullanıcı Listesi", callback_data="admin_users"), InlineKeyboardButton("⛔ Banla / Ban Kaldır", callback_data="btn_ban")]
    ]
    return panel_text, InlineKeyboardMarkup(keyboard)

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await register_user(update.effective_user, context=context)
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komutu kullanma yetkiniz yok.")
        return

    text, keyboard = build_admin_panel()
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)

# --- 5. BUTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await register_user(query.from_user, context=context)
    user_id = query.from_user.id
    data = query.data

    if db.get("maintenance_mode") and user_id != ADMIN_ID:
        await query.answer("⚙️ Sistem bakımdadır! Lütfen daha sonra tekrar deneyiniz.", show_alert=True)
        return

    if data == "check_subs":
        await query.answer()
        is_ok, missing = await check_channel_subscription(user_id, context)
        if is_ok:
            # Referans Ödül Kontrolü (Abonelik onaylandığında verilir)
            u_data = db["users"].get(str(user_id), {})
            ref_id = u_data.get("referred_by")
            if ref_id and ref_id in db["users"] and not u_data.get("ref_rewarded"):
                db["users"][str(user_id)]["ref_rewarded"] = True
                db["users"][ref_id]["invites_count"] = db["users"][ref_id].get("invites_count", 0) + 1
                inv_count = db["users"][ref_id]["invites_count"]
                
                # 10 Kişiye Ulaşınca 3 Gün VIP
                if inv_count >= 10 and not db["users"][ref_id].get("is_vip"):
                    db["users"][ref_id]["is_vip"] = True
                    until_date = (date.today() + timedelta(days=3)).isoformat()
                    db["users"][ref_id]["vip_until"] = until_date
                    
                    try:
                        await context.bot.send_message(
                            chat_id=int(ref_id),
                            text="🎉 <b>TEBRİKLER!</b>\n\n10 Kişiyi başarıyla davet ettiğiniz için <b>3 GÜNLÜK HEDİYE VIP</b> üyeliğiniz aktif edildi! 🚀",
                            parse_mode="HTML"
                        )
                    except Exception: pass

                save_data(db)

            text, keyboard = build_main_menu(user_id)
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await query.answer("⚠️ Hâlâ eksik kanallar var! Lütfen tümüne katılın.", show_alert=True)
        return

    # Kullanıcı Menü İşlemleri
    if data == "user_profile":
        await query.answer()
        text, keyboard = build_profile_card(query.from_user)
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
        return

    elif data == "user_ref":
        await query.answer()
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        u_data = db["users"].get(str(user_id), {})
        inv_count = u_data.get("invites_count", 0)

        ref_text = (
            "🔗 <b>KİŞİSEL DAVET (REFERANS) SİSTEMİ</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Arkadaşlarınızı bota davet ederek hediyeler kazanabilirsiniz!\n\n"
            "🎁 <b>Ödül:</b> 10 Arkadaşını bota davet et, <b>3 GÜN ÜCRETSİZ VIP</b> kazan!\n\n"
            f"📊 <b>Toplam Davet Sayınız:</b> <code>{inv_count} / 10</code>\n\n"
            f"👉 <b>Özel Davet Linkiniz:</b>\n<code>{ref_link}</code>"
        )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Ana Menü", callback_data="menu_home")]])
        await query.edit_message_text(text=ref_text, parse_mode="HTML", reply_markup=keyboard)
        return

    elif data == "menu_home":
        context.user_data['waiting_for_query'] = False
        text, keyboard = build_main_menu(user_id)
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
        return

    # Admin İşlemleri
    if user_id == ADMIN_ID:
        if data == "btn_add_vip":
            await query.answer()
            context.user_data['admin_action'] = 'add_vip'
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal / Geri Dön", callback_data="admin_back")]])
            await query.edit_message_text("👑 <b>VIP Verme Modu</b>\n\nLütfen VIP vermek istediğiniz kullanıcının <b>ID'sini ve gün sayısını</b> aralarında boşluk bırakarak yazın:\n<i>(Örn: 6073294253 30)</i>", parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "btn_del_vip":
            await query.answer()
            context.user_data['admin_action'] = 'del_vip'
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal / Geri Dön", callback_data="admin_back")]])
            await query.edit_message_text("❌ <b>VIP Kaldırma Modu</b>\n\nVIP üyeliğini iptal etmek istediğiniz kullanıcının Telegram ID'sini yazıp gönderin:", parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "toggle_maintenance":
            db["maintenance_mode"] = not db.get("maintenance_mode", False)
            save_data(db)
            text, keyboard = build_admin_panel()
            await query.answer("Bakım modu değiştirildi!")
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "toggle_channel_req":
            db["must_join"] = not db["must_join"]
            save_data(db)
            text, keyboard = build_admin_panel()
            await query.answer("Kanal zorunluluğu değiştirildi!")
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "admin_back":
            context.user_data['admin_action'] = None
            await query.answer()
            text, keyboard = build_admin_panel()
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "admin_users":
            await query.answer()
            u_list = list(db["users"].keys())
            total = len(u_list)
            msg = f"👥 <b>Toplam Kullanıcı Listesi ({total}):</b>\n━━━━━━━━━━━━━━━━━━\n"
            
            for uid in u_list[:80]:
                u_data = db["users"][uid]
                uname = u_data.get("username")
                uname_str = f"| @{uname}" if uname else ""
                is_v = " 👑 VIP" if u_data.get("is_vip") else ""
                msg += f"• <code>{uid}</code> {uname_str}{is_v}\n"
                
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Panele Geri Dön", callback_data="admin_back")]])
            await query.edit_message_text(text=msg, parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "btn_ban":
            await query.answer()
            context.user_data['admin_action'] = 'ban_user'
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal / Geri Dön", callback_data="admin_back")]])
            await query.edit_message_text("⛔ <b>Kullanıcı Banlama/Ban Kaldırma Modu</b>\n\nBanlamak veya banını kaldırmak istediğiniz ID'yi gönderin:", parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "btn_add_channel":
            await query.answer()
            context.user_data['admin_action'] = 'add_channel'
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal / Geri Dön", callback_data="admin_back")]])
            await query.edit_message_text("➕ Kanal kullanıcı adını yazın (Örn: @arastirzorunlu):", parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "btn_del_channel":
            await query.answer()
            context.user_data['admin_action'] = 'del_channel'
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal / Geri Dön", callback_data="admin_back")]])
            await query.edit_message_text("➖ Silinecek kanal adını yazın:", parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "btn_broadcast":
            await query.answer()
            context.user_data['admin_action'] = 'broadcast_msg'
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal / Geri Dön", callback_data="admin_back")]])
            await query.edit_message_text("📢 Duyuru metnini yazıp gönderin:", parse_mode="HTML", reply_markup=keyboard)
            return

    is_ok, missing = await check_channel_subscription(user_id, context)
    if not is_ok:
        await query.answer("⚠️ Zorunlu kanallara katılmalısınız!", show_alert=True)
        await send_subscription_warning(query.message.chat_id, user_id, missing, context)
        return

    await query.answer()
    if data.startswith("query_"):
        q_type = data.split("_")[1]
        
        # SORGULAMA LIMITI KONTROLU
        u_data = db["users"].get(str(user_id), {})
        is_vip = u_data.get("is_vip", False) or (user_id == ADMIN_ID)
        daily_count = u_data.get("daily_queries", 0)

        if not is_vip and daily_count >= 7:
            vip_kb = InlineKeyboardMarkup([[InlineKeyboardButton("👑 VIP Satın Al", url=f"https://t.me/{VIP_CONTACT.replace('@','')}")]])
            await query.edit_message_text(
                f"⚠️ <b>GÜNLÜK SORGU LİMİTİNİZ DOLDU!</b>\n\n"
                f"Normal üyeler günde en fazla <b>7 sorgu</b> yapabilir.\n"
                f"Sınırsız sorgu yapmak ve VIP ayrıcalıklarından yararlanmak için {VIP_CONTACT} hesabı ile iletişime geçebilirsiniz.",
                parse_mode="HTML",
                reply_markup=vip_kb
            )
            return

        context.user_data['waiting_for_query'] = True
        context.user_data['current_query_type'] = q_type
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ İşlemi İptal Et / Ana Menü", callback_data="menu_home")]])
        await query.edit_message_text(
            f"🔍 <b>{q_type.upper()} Sorgulama Ekranı</b>\n\nLütfen aratmak istediğiniz bilgiyi mesaja yazıp gönderin:",
            parse_mode="HTML",
            reply_markup=keyboard
        )

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

def generate_html_file(q_type, data, count):
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

# --- 6. MESAJ İŞLEME ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await register_user(update.effective_user, context=context)
    user_id = update.effective_user.id
    text_input = update.message.text.strip()
    u_name = update.effective_user.username
    u_str = f"@{u_name}" if u_name else "<i>Kullanıcı Adı Yok</i>"

    if db.get("maintenance_mode") and user_id != ADMIN_ID:
        await update.message.reply_text("⚙️ <b>SİSTEM BAKIMDA!</b>\n\nBot şu an bakım çalışması nedeniyle hizmet dışıdır.", parse_mode="HTML")
        return

    if user_id == ADMIN_ID and context.user_data.get('admin_action'):
        action = context.user_data.get('admin_action')
        context.user_data['admin_action'] = None

        if action == 'add_vip':
            try:
                parts = text_input.split(" ")
                target_uid = parts[0]
                days = int(parts[1]) if len(parts) > 1 else 30

                if target_uid in db["users"]:
                    db["users"][target_uid]["is_vip"] = True
                    until_date = (date.today() + timedelta(days=days)).isoformat()
                    db["users"][target_uid]["vip_until"] = until_date
                    save_data(db)
                    await update.message.reply_text(f"👑 <code>{target_uid}</code> ID'li kullanıcıya <b>{days} günlük</b> VIP verildi.", parse_mode="HTML")
                    await send_log(context, f"👑 <b>VIP VERİLDİ!</b>\n<b>Kullanıcı ID:</b> <code>{target_uid}</code>\n<b>Süre:</b> {days} Gün")
                else:
                    await update.message.reply_text("⚠️ Kullanıcı sistemde bulunamadı.")
            except Exception:
                await update.message.reply_text("⚠️ Hatalı format! Örnek: <code>6073294253 30</code>", parse_mode="HTML")
            return

        elif action == 'del_vip':
            if text_input in db["users"]:
                db["users"][text_input]["is_vip"] = False
                db["users"][text_input]["vip_until"] = None
                save_data(db)
                await update.message.reply_text(f"❌ <code>{text_input}</code> ID'li kullanıcının VIP üyeliği kaldırıldı.", parse_mode="HTML")
            return

        elif action == 'ban_user':
            if text_input in db["users"]:
                curr = db["users"][text_input].get("is_banned", False)
                db["users"][text_input]["is_banned"] = not curr
                save_data(db)
                st = "Banlandı" if not curr else "Banı Kaldırıldı"
                await update.message.reply_text(f"⛔ Kullanıcı <b>{st}</b>: <code>{text_input}</code>", parse_mode="HTML")
            return

        elif action == 'add_channel':
            ch_name = text_input if text_input.startswith("@") else "@" + text_input
            if ch_name not in db["channels"]:
                db["channels"].append(ch_name)
                save_data(db)
                await update.message.reply_text(f"✅ <b>{ch_name}</b> eklendi.", parse_mode="HTML")
            return

        elif action == 'del_channel':
            ch_name = text_input if text_input.startswith("@") else "@" + text_input
            if ch_name in db["channels"]:
                db["channels"].remove(ch_name)
                save_data(db)
                await update.message.reply_text(f"🗑️ <b>{ch_name}</b> silindi.", parse_mode="HTML")
            return

        elif action == 'broadcast_msg':
            global duyuru_iptal_flag
            duyuru_iptal_flag = False
            status_msg = await update.message.reply_text("📢 <b>Duyuru Gönderimi Başlatıldı...</b>", parse_mode="HTML")
            success, failed = 0, 0
            user_ids = list(db["users"].keys())
            
            for idx, uid in enumerate(user_ids, 1):
                if duyuru_iptal_flag:
                    await status_msg.edit_text("🛑 Duyuru İptal Edildi!", parse_mode="HTML")
                    return
                try:
                    await context.bot.send_message(chat_id=int(uid), text=f"📢 <b>DUYURU</b>\n━━━━━━━━━━━━━━━━━━\n{text_input}", parse_mode="HTML")
                    success += 1
                except Exception: failed += 1
                await asyncio.sleep(0.05)

            await status_msg.edit_text(f"✅ <b>Duyuru Tamamlandı!</b>\n\n✅ Gönderilen: {success}\n❌ Başarısız: {failed}", parse_mode="HTML")
            return

    is_ok, missing = await check_channel_subscription(user_id, context)
    if not is_ok:
        await send_subscription_warning(update.effective_chat.id, user_id, missing, context)
        return

    if context.user_data.get('waiting_for_query'):
        q_type = context.user_data.get('current_query_type', 'islem')
        
        # SORGULAMA LIMIT KONTROLU
        u_data = db["users"].get(str(user_id), {})
        is_vip = u_data.get("is_vip", False) or (user_id == ADMIN_ID)
        daily_count = u_data.get("daily_queries", 0)

        if not is_vip and daily_count >= 7:
            vip_kb = InlineKeyboardMarkup([[InlineKeyboardButton("👑 VIP Satın Al", url=f"https://t.me/{VIP_CONTACT.replace('@','')}")]])
            await update.message.reply_text(
                f"⚠️ <b>GÜNLÜK SORGU LİMİTİNİZ DOLDU!</b>\n\n"
                f"Normal üyeler günde en fazla <b>7 sorgu</b> yapabilir.\n"
                f"Sınırsız sorgu yapmak ve VIP almak için {VIP_CONTACT} hesabı ile iletişime geçebilirsiniz.",
                parse_mode="HTML",
                reply_markup=vip_kb
            )
            context.user_data['waiting_for_query'] = False
            return

        context.user_data['waiting_for_query'] = False
        wait_msg = await update.message.reply_text("⏳ Sorgulanıyor, lütfen bekleyin...", parse_mode="HTML")

        # Sayaç Artırma
        db["users"][str(user_id)]["daily_queries"] = daily_count + 1
        save_data(db)
        
        # Log Kanalına Gönder
        query_log = (
            "🔍 <b>YENİ SORGU YAPILDI</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"<b>Kullanıcı:</b> {u_str}\n"
            f"<b>ID:</b> <code>{user_id}</code>\n"
            f"<b>Sorgu Türü:</b> <code>{q_type.upper()}</code>\n"
            f"<b>Aratılan:</b> <code>{html.escape(text_input)}</code>"
        )
        await send_log(context, query_log)

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
                    
                    if len(sonuc_mesaji) > 3500:
                        full_html = generate_html_file(q_type, data, count)
                        html_bytes = io.BytesIO(full_html.encode('utf-8'))
                        html_bytes.name = f"ArastirX_{q_type}_{text_input}.html"
                        
                        await wait_msg.delete()
                        await update.message.reply_document(
                            document=html_bytes,
                            caption=f"✅ <b>Sorgu Başarılı ({q_type.upper()})</b>\n📄 <i>Sonucunuz <b>HTML Dosyası</b> formatındadır.</i>",
                            parse_mode="HTML"
                        )
                    else:
                        await wait_msg.edit_text(sonuc_mesaji, parse_mode="HTML")
                else:
                    err_msg = html.escape(str(res_json.get("error", "Bilinmeyen bir hata oluştu.")))
                    await wait_msg.edit_text(f"⚠️ <b>Hata:</b> {err_msg}", parse_mode="HTML")
            else:
                await wait_msg.edit_text(f"❌ API Sunucu Hatası: {response.status_code}")
                
        except Exception as e:
            err_str = html.escape(str(e))
            await wait_msg.edit_text(f"❌ Sistem hatası oluştu: {err_str}", parse_mode="HTML")
    else:
        await update.message.reply_text("Menüyü açmak için /start yazabilirsiniz.")

if __name__ == '__main__':
    keep_alive()
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("panel", panel_command))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()
