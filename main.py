import os
import json
import html
import io
import asyncio
import threading
from datetime import datetime, date
import requests
from flask import Flask
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

ADMIN_ID = 6073294253
TOKEN = "8646358320:AAEj6rlEpCxX1aLOXspgbsTNpVaYtvvGrbE"

# --- VERİTABANI YÖNETİMİ (KORUMALI JSON) ---
DATA_FILE = "bot_data.json"

DEFAULT_CHANNELS = ["@arastirduyuru", "@arastirzorunlu"]
DEFAULT_USERS = {}

def load_data():
    data = {
        "users": dict(DEFAULT_USERS),
        "channels": list(DEFAULT_CHANNELS),
        "must_join": True
    }
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
                
                if "users" in saved_data:
                    data["users"].update(saved_data["users"])
                
                if "channels" in saved_data:
                    combined_channels = list(set(saved_data["channels"] + DEFAULT_CHANNELS))
                    data["channels"] = combined_channels
                    
                if "must_join" in saved_data: 
                    data["must_join"] = saved_data["must_join"]
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

# --- YARDIMCI FONKSİYONLAR ---
def register_user(user):
    """Kullanıcıyı ve username/tarih bilgilerini eksiksiz kaydeder."""
    if not user:
        return
    
    user_id = user.id
    username = user.username if user.username else None
    uid_str = str(user_id)
    today_str = date.today().isoformat()

    if uid_str not in db["users"]:
        db["users"][uid_str] = {
            "is_banned": False,
            "created_at": today_str,
            "username": username
        }
        save_data(db)
    else:
        updated = False
        if "created_at" not in db["users"][uid_str]:
            db["users"][uid_str]["created_at"] = today_str
            updated = True
        if db["users"][uid_str].get("username") != username:
            db["users"][uid_str]["username"] = username
            updated = True
            
        if updated:
            save_data(db)

async def check_channel_subscription(user_id, context: ContextTypes.DEFAULT_TYPE):
    uid_str = str(user_id)
    user_info = db["users"].get(uid_str, {"is_banned": False})

    # Eğer admin banladıysa engelle
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
            # Bot kanalda admin değilse veya hata olursa kullanıcıyı banlama/engelleme
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
    register_user(update.effective_user)
    user_id = update.effective_user.id

    if db["users"].get(str(user_id), {}).get("is_banned"):
        await update.message.reply_text("⛔ <b>Sistemden Banlandınız!</b>\nBota erişiminiz engellenmiştir.", parse_mode="HTML")
        return

    is_ok, missing = await check_channel_subscription(user_id, context)
    if not is_ok:
        if missing == ["BANNED"]:
            await update.message.reply_text("⛔ <b>Sistemden Banlandınız!</b>", parse_mode="HTML")
            return
        await send_subscription_warning(update.effective_chat.id, user_id, missing, context)
        return

    menu_text, keyboard = build_main_menu()
    await update.message.reply_text(menu_text, parse_mode="HTML", reply_markup=keyboard)

def build_main_menu():
    text = (
        "🔍 <b>AraştırX | Analiz Botu</b> Paneline Hoş Geldiniz!\n\n"
        "İşlem yapmak için aşağıdaki menüden bir kategori seçin:"
    )
    keyboard = [
        [InlineKeyboardButton("🤵 Ad Soyad Sorgula", callback_data="query_adsoyad"), InlineKeyboardButton("🖨️ TC Sorgula", callback_data="query_tc")],
        [InlineKeyboardButton("🏢 İşyeri Sorgula", callback_data="query_isyeri"), InlineKeyboardButton("📍 Adres Sorgula", callback_data="query_adres")],
        [InlineKeyboardButton("👥 Aile Sorgula", callback_data="query_aile"), InlineKeyboardButton("👥 Sülale Sorgula", callback_data="query_sulale")],
        [InlineKeyboardButton("👶 Çocuk Sorgula", callback_data="query_cocuk")],
        [InlineKeyboardButton("📱 TC-GSM Sorgula", callback_data="query_tcgsm"), InlineKeyboardButton("📱 GSM-TC Sorgula", callback_data="query_gsmtc")]
    ]
    return text, InlineKeyboardMarkup(keyboard)

# --- 3. YÖNETİCİ PANELİ ---
def build_admin_panel():
    today_str = date.today().isoformat()
    total_users = len(db["users"])
    banned_users = sum(1 for u in db["users"].values() if u.get("is_banned"))
    today_users = sum(1 for u in db["users"].values() if u.get("created_at") == today_str)

    channels_str = "\n".join([f"• {c}" for c in db["channels"]]) if db["channels"] else "<i>Ekli kanal yok.</i>"
    must_join_status = "🟢 AÇIK" if db["must_join"] else "🔴 KAPALI"

    panel_text = (
        "⚙️ <b>AraştırX | Yönetici Paneli</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Bugün Gelen Kullanıcı:</b> <code>{today_users}</code>\n"
        f"📊 <b>Toplam Kullanıcı:</b> <code>{total_users}</code>\n"
        f"🚫 <b>Banlı Kullanıcı:</b> <code>{banned_users}</code>\n"
        f"📢 <b>Kanal Zorunluluğu:</b> {must_join_status}\n\n"
        f"📌 <b>Ekli Bulunan Kanallar:</b>\n{channels_str}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Aşağıdaki butonları kullanarak tüm yönetici işlemlerini hızlıca yapabilirsiniz:"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"Kanal Zorunluluğu: {must_join_status}", callback_data="toggle_channel_req")],
        [InlineKeyboardButton("➕ Kanal Ekle", callback_data="btn_add_channel"), InlineKeyboardButton("➖ Kanal Sil", callback_data="btn_del_channel")],
        [InlineKeyboardButton("📢 Duyuru Gönder", callback_data="btn_broadcast"), InlineKeyboardButton("🛑 Duyuru İptal", callback_data="btn_cancel_broadcast")],
        [InlineKeyboardButton("👥 Kullanıcı Listesi", callback_data="admin_users"), InlineKeyboardButton("🔓 Ban Kaldır (Unban)", callback_data="btn_unban")],
        [InlineKeyboardButton("🔄 Paneli Yenile", callback_data="admin_refresh")]
    ]
    return panel_text, InlineKeyboardMarkup(keyboard)

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komutu kullanma yetkiniz yok.")
        return

    text, keyboard = build_admin_panel()
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)

# --- 4. BUTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    register_user(query.from_user)
    user_id = query.from_user.id
    data = query.data

    if data == "check_subs":
        await query.answer()
        is_ok, missing = await check_channel_subscription(user_id, context)
        if is_ok:
            text, keyboard = build_main_menu()
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await query.answer("⚠️ Hâlâ eksik kanallar var! Lütfen tümüne katılın.", show_alert=True)
        return

    if user_id == ADMIN_ID:
        if data == "toggle_channel_req":
            db["must_join"] = not db["must_join"]
            save_data(db)
            text, keyboard = build_admin_panel()
            await query.answer("Kanal zorunluluğu değiştirildi!")
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "admin_refresh":
            text, keyboard = build_admin_panel()
            await query.answer("Panel Yenilendi!")
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
                created = u_data.get("created_at", "Bilinmiyor")
                uname = u_data.get("username")
                uname_str = f"| @{uname}" if uname else "| <i>(Kullanıcı Adı Yok)</i>"
                is_b = " ⛔ (BANLI)" if u_data.get("is_banned") else ""
                
                msg += f"• <code>{uid}</code> {uname_str} | 📅 {created}{is_b}\n"
                
            if total > 80: msg += f"\n<i>...ve {total - 80} kişi daha.</i>"
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Panele Geri Dön", callback_data="admin_back")]])
            await query.edit_message_text(text=msg, parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "btn_add_channel":
            await query.answer()
            context.user_data['admin_action'] = 'add_channel'
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal / Geri Dön", callback_data="admin_back")]])
            await query.edit_message_text("➕ <b>Kanal Ekleme Modu</b>\n\nEklemek istediğiniz kanal kullanıcı adını yazıp gönderin:\n<i>(Örn: @arastirzorunlu)</i>", parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "btn_del_channel":
            await query.answer()
            context.user_data['admin_action'] = 'del_channel'
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal / Geri Dön", callback_data="admin_back")]])
            await query.edit_message_text("➖ <b>Kanal Silme Modu</b>\n\nSilmek istediğiniz kanal kullanıcı adını yazıp gönderin:\n<i>(Örn: @arastirzorunlu)</i>", parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "btn_unban":
            await query.answer()
            context.user_data['admin_action'] = 'unban_user'
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal / Geri Dön", callback_data="admin_back")]])
            await query.edit_message_text("🔓 <b>Ban Kaldırma Modu</b>\n\nBanını açmak istediğiniz kullanıcının Telegram ID'sini yazıp gönderin:", parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "btn_broadcast":
            await query.answer()
            context.user_data['admin_action'] = 'broadcast_msg'
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ İptal / Geri Dön", callback_data="admin_back")]])
            await query.edit_message_text("📢 <b>Duyuru Modu</b>\n\nTüm üyelere iletmek istediğiniz duyuru metnini yazıp gönderin:", parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "btn_cancel_broadcast":
            global duyuru_iptal_flag
            duyuru_iptal_flag = True
            await query.answer("Duyuru iptal talebi iletildi!", show_alert=True)
            return

    is_ok, missing = await check_channel_subscription(user_id, context)
    if not is_ok:
        if missing == ["BANNED"]:
            await query.edit_message_text("⛔ <b>Banlandınız!</b>\nBota erişiminiz engellenmiştir.", parse_mode="HTML")
        else:
            await query.answer("⚠️ Zorunlu kanallara katılmalısınız!", show_alert=True)
            await send_subscription_warning(query.message.chat_id, user_id, missing, context)
        return

    await query.answer()
    if data.startswith("query_"):
        q_type = data.split("_")[1]
        context.user_data['waiting_for_query'] = True
        context.user_data['current_query_type'] = q_type
        
        titles = {
            "adsoyad": "Ad Soyad (Örn: AHMET YILMAZ)",
            "tc": "TC Kimlik (11 Haneli)",
            "isyeri": "İşyeri (TC Kimlik)",
            "adres": "Adres (TC Kimlik)",
            "aile": "Aile (TC Kimlik)",
            "sulale": "Sülale (TC Kimlik)",
            "cocuk": "Çocuk (TC Kimlik)",
            "tcgsm": "TC - GSM (TC Kimlik)",
            "gsmtc": "GSM - TC (Örn: 05551234567)"
        }
        s_name = titles.get(q_type, "Sorgu Bilgisi")
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ İşlemi İptal Et / Ana Menü", callback_data="menu_home")]])
        await query.edit_message_text(
            f"🔍 <b>{q_type.upper()} Sorgulama Ekranı</b>\n\nLütfen aratmak istediğiniz bilgiyi mesaja yazıp gönderin:\n👉 <i>{s_name}</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    elif data == "menu_home":
        context.user_data['waiting_for_query'] = False
        text, keyboard = build_main_menu()
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)

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

# --- 5. MESAJ İŞLEME VE INTERAKTİF ADMIN İŞLEMLERİ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    user_id = update.effective_user.id
    text_input = update.message.text.strip()

    if user_id == ADMIN_ID and context.user_data.get('admin_action'):
        action = context.user_data.get('admin_action')
        context.user_data['admin_action'] = None

        if action == 'add_channel':
            ch_name = text_input if text_input.startswith("@") else "@" + text_input
            if ch_name not in db["channels"]:
                db["channels"].append(ch_name)
                save_data(db)
                await update.message.reply_text(f"✅ <b>{ch_name}</b> zorunlu kanallara eklendi.", parse_mode="HTML")
            else:
                await update.message.reply_text("⚠️ Bu kanal zaten listede ekli.")
            return

        elif action == 'del_channel':
            ch_name = text_input if text_input.startswith("@") else "@" + text_input
            if ch_name in db["channels"]:
                db["channels"].remove(ch_name)
                save_data(db)
                await update.message.reply_text(f"🗑️ <b>{ch_name}</b> listeden çıkarıldı.", parse_mode="HTML")
            else:
                await update.message.reply_text("⚠️ Kanal listede bulunamadı.")
            return

        elif action == 'unban_user':
            if text_input in db["users"]:
                db["users"][text_input]["is_banned"] = False
                save_data(db)
                await update.message.reply_text(f"✅ <code>{text_input}</code> ID'li kullanıcının banı kaldırıldı.", parse_mode="HTML")
            else:
                await update.message.reply_text("⚠️ Kullanıcı veritabanında bulunamadı.")
            return

        elif action == 'broadcast_msg':
            global duyuru_iptal_flag
            duyuru_iptal_flag = False
            status_msg = await update.message.reply_text("📢 <b>Duyuru Gönderimi Başlatıldı...</b>", parse_mode="HTML")
            
            success, failed = 0, 0
            user_ids = list(db["users"].keys())
            total = len(user_ids)

            for idx, uid in enumerate(user_ids, 1):
                if duyuru_iptal_flag:
                    await status_msg.edit_text(f"🛑 <b>Duyuru İptal Edildi!</b>\n\nGönderilen: {success}\nBaşarısız: {failed}", parse_mode="HTML")
                    return

                try:
                    await context.bot.send_message(chat_id=int(uid), text=f"📢 <b>DUYURU</b>\n━━━━━━━━━━━━━━━━━━\n{text_input}", parse_mode="HTML")
                    success += 1
                except Exception:
                    failed += 1
                    
                if idx % 10 == 0 or idx == total:
                    try:
                        await status_msg.edit_text(f"⏳ <b>Duyuru Gönderiliyor...</b> ({idx}/{total})\n\n✅ Başarılı: {success}\n❌ Başarısız: {failed}", parse_mode="HTML")
                    except Exception: pass
                await asyncio.sleep(0.05)

            await status_msg.edit_text(f"✅ <b>Duyuru Tamamlandı!</b>\n\n📊 Toplam: {total}\n✅ Gönderilen: {success}\n❌ Ulaşılamayan: {failed}", parse_mode="HTML")
            return

    is_ok, missing = await check_channel_subscription(user_id, context)
    if not is_ok:
        if missing == ["BANNED"]:
            await update.message.reply_text("⛔ <b>Banlandınız!</b>", parse_mode="HTML")
        else:
            await send_subscription_warning(update.effective_chat.id, user_id, missing, context)
        return

    if context.user_data.get('waiting_for_query'):
        q_type = context.user_data.get('current_query_type', 'islem')
        context.user_data['waiting_for_query'] = False
        wait_msg = await update.message.reply_text("⏳ Sorgulanıyor, lütfen bekleyin...", parse_mode="HTML")
        
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
                            caption=f"✅ <b>Sorgu Başarılı ({q_type.upper()})</b>\n📄 <i>Sonucunuz <b>HTML Dosyası</b> formatında iletildi.</i>",
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
