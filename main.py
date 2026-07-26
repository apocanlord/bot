import os
import json
import html
import io
import asyncio
import threading
import requests
from flask import Flask
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ChatMemberHandler, filters, ContextTypes
from telegram.error import TelegramError

ADMIN_ID = 6073294253
TOKEN = "8646358320:AAEj6rlEpCxX1aLOXspgbsTNpVaYtvvGrbE"

# --- VERİTABANI YÖNETİMİ (JSON) ---
DATA_FILE = "bot_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "users": {},        # "user_id": {"warnings": 0, "is_banned": False}
        "channels": [],     # ["@kanal1", "@kanal2"]
        "must_join": True   # Kanal zorunluluğu
    }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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
def register_user(user_id):
    uid_str = str(user_id)
    if uid_str not in db["users"]:
        db["users"][uid_str] = {"warnings": 0, "is_banned": False}
        save_data(db)

async def check_channel_subscription(user_id, context: ContextTypes.DEFAULT_TYPE):
    """Kullanıcının zorunlu kanallara üye olup olmadığını kontrol eder."""
    if not db["must_join"] or not db["channels"]:
        return True, []

    missing_channels = []
    uid_str = str(user_id)
    register_user(user_id)
    user_info = db["users"].get(uid_str, {"warnings": 0, "is_banned": False})

    if user_info.get("is_banned"):
        return False, ["BANNED"]

    for channel in db["channels"]:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                missing_channels.append(channel)
        except Exception:
            pass

    if missing_channels:
        current_warns = user_info.get("warnings", 0) + 1
        
        if current_warns >= 3:
            db["users"][uid_str]["is_banned"] = True
            db["users"][uid_str]["warnings"] = 3
            save_data(db)
            return False, ["BANNED"]
        else:
            db["users"][uid_str]["warnings"] = current_warns
            save_data(db)
            return False, missing_channels

    return True, []

async def send_subscription_warning(chat_id, user_id, missing, context: ContextTypes.DEFAULT_TYPE):
    uid_str = str(user_id)
    warn_count = db["users"].get(uid_str, {}).get("warnings", 1)

    text = (
        "⚠️ <b>UYARI: ZORUNLU KANAL ÜYELİĞİ EKSİK!</b>\n\n"
        "Bu botu kullanmaya devam edebilmek için zorunlu kanallara abone olmak zorundasınız.\n\n"
        f"🚨 <b>İhlal / Uyarı Durumu:</b> <code>{warn_count}/3</code>\n"
        "<i>(Kanaldan çıkmaya devam ederseniz 3. uyarıda bota erişiminiz tamamen engellenmiştir!)</i>\n\n"
        "Lütfen aşağıdaki kanallara katılıp <b>'✅ Katıldım, Onayla'</b> butonuna basın:"
    )
    
    keyboard = []
    for ch in missing:
        clean_ch = ch.replace("@", "")
        keyboard.append([InlineKeyboardButton(f"📢 Katıl: {ch}", url=f"https://t.me/{clean_ch}")])
    keyboard.append([InlineKeyboardButton("✅ Katıldım, Onayla", callback_data="check_subs")])

    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# --- 2. START KOMUTU & ANA MENÜ ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)

    if db["users"].get(str(user_id), {}).get("is_banned"):
        await update.message.reply_text("⛔ <b>Sistemden Banlandınız!</b>\nZorunlu kanallardan 3 kez ayrıldığınız için bota erişiminiz tamamen engellenmiştir.", parse_mode="HTML")
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

# --- 3. YÖNETİCİ PANELSİ (İNLINE YENİLEME) ---
def build_admin_panel():
    total_users = len(db["users"])
    banned_users = sum(1 for u in db["users"].values() if u.get("is_banned"))
    channels_str = "\n".join([f"• {c}" for c in db["channels"]]) if db["channels"] else "<i>Ekli kanal yok.</i>"
    must_join_status = "🟢 AÇIK" if db["must_join"] else "🔴 KAPALI"

    panel_text = (
        "⚙️ <b>AraştırX | Yönetici Paneli</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Toplam Kullanıcı:</b> <code>{total_users}</code>\n"
        f"🚫 <b>Banlı Kullanıcı:</b> <code>{banned_users}</code>\n"
        f"📢 <b>Kanal Zorunluluğu:</b> {must_join_status}\n\n"
        f"📌 <b>Ekli Bulunan Kanallar:</b>\n{channels_str}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Aşağıdaki butonları kullanarak hızlı işlem yapabilirsiniz:"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"Kanal Zorunluluğu ({must_join_status})", callback_data="toggle_channel_req")],
        [InlineKeyboardButton("👥 Kullanıcı Listesi", callback_data="admin_users"), InlineKeyboardButton("🔄 Paneli Yenile", callback_data="admin_refresh")],
        [InlineKeyboardButton("❓ Komut Kullanım Rehberi", callback_data="admin_guide")]
    ]
    return panel_text, InlineKeyboardMarkup(keyboard)

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komutu kullanma yetkiniz yok.")
        return

    text, keyboard = build_admin_panel()
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)

# --- 4. KOMUTLAR ---
async def add_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("Kullanım: <code>/kanal_ekle @kanaladi</code>", parse_mode="HTML")
        return
    
    ch_name = context.args[0]
    if not ch_name.startswith("@"): ch_name = "@" + ch_name
        
    if ch_name not in db["channels"]:
        db["channels"].append(ch_name)
        save_data(db)
        await update.message.reply_text(f"✅ <b>{ch_name}</b> eklendi.", parse_mode="HTML")
    else:
        await update.message.reply_text("⚠️ Bu kanal zaten ekli.")

async def del_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("Kullanım: <code>/kanal_sil @kanaladi</code>", parse_mode="HTML")
        return
        
    ch_name = context.args[0]
    if not ch_name.startswith("@"): ch_name = "@" + ch_name

    if ch_name in db["channels"]:
        db["channels"].remove(ch_name)
        save_data(db)
        await update.message.reply_text(f"🗑️ <b>{ch_name}</b> çıkarıldı.", parse_mode="HTML")
    else:
        await update.message.reply_text("⚠️ Kanal bulunamadı.")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("Kullanım: <code>/unban KULLANICI_ID</code>", parse_mode="HTML")
        return
    
    uid = context.args[0]
    if uid in db["users"]:
        db["users"][uid]["is_banned"] = False
        db["users"][uid]["warnings"] = 0
        save_data(db)
        await update.message.reply_text(f"✅ <code>{uid}</code> banı kaldırıldı.", parse_mode="HTML")
    else:
        await update.message.reply_text("Kullanıcı bulunamadı.")

# --- 5. DUYURU SİSTEMİ ---
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global duyuru_iptal_flag
    if update.effective_user.id != ADMIN_ID: return
    
    duyuru_msg = " ".join(context.args)
    if not duyuru_msg:
        await update.message.reply_text("⚠️ Lütfen duyuru metnini girin.", parse_mode="HTML")
        return
        
    duyuru_iptal_flag = False
    status_msg = await update.message.reply_text("📢 <b>Duyuru Başlatıldı...</b>", parse_mode="HTML")
    
    success = 0
    failed = 0
    user_ids = list(db["users"].keys())
    total = len(user_ids)

    for idx, uid in enumerate(user_ids, 1):
        if duyuru_iptal_flag:
            await status_msg.edit_text(f"🛑 <b>Duyuru İptal Edildi!</b>\n\nGönderilen: {success}\nBaşarısız: {failed}", parse_mode="HTML")
            return

        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 <b>DUYURU</b>\n━━━━━━━━━━━━━━━━━━\n{duyuru_msg}", parse_mode="HTML")
            success += 1
        except Exception:
            failed += 1
            
        if idx % 10 == 0 or idx == total:
            try:
                await status_msg.edit_text(f"⏳ <b>Duyuru Gönderiliyor...</b> ({idx}/{total})\n\n✅ Başarılı: {success}\n❌ Başarısız: {failed}", parse_mode="HTML")
            except Exception: pass
            
        await asyncio.sleep(0.05)

    await status_msg.edit_text(f"✅ <b>Duyuru Tamamlandı!</b>\n\n📊 Toplam: {total}\n✅ Gönderilen: {success}\n❌ Ulaşılamayan: {failed}", parse_mode="HTML")

async def cancel_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global duyuru_iptal_flag
    if update.effective_user.id != ADMIN_ID: return
    duyuru_iptal_flag = True
    await update.message.reply_text("🛑 <b>Duyuru iptal ediliyor...</b>", parse_mode="HTML")

# --- 6. BUTON TIKLAMA (INLINE EDITING - GÖRÜNTÜ KİRLİLİĞİ YOK) ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    # A) Kullanıcı Onay Butonu
    if data == "check_subs":
        await query.answer()
        is_ok, missing = await check_channel_subscription(user_id, context)
        if is_ok:
            text, keyboard = build_main_menu()
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await send_subscription_warning(query.message.chat_id, user_id, missing, context)
        return

    # B) Admin Paneli İç Buton İşlemleri (Tümü aynı mesajda güncellenir)
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

        elif data == "admin_users":
            await query.answer()
            u_list = list(db["users"].keys())
            total = len(u_list)
            msg = f"👥 <b>Toplam Kullanıcı Listesi ({total}):</b>\n━━━━━━━━━━━━━━━━━━\n"
            for uid in u_list[:80]:
                is_b = " ⛔ (BANLI)" if db["users"][uid].get("is_banned") else ""
                msg += f"• <code>{uid}</code>{is_b}\n"
            if total > 80: msg += f"\n<i>...ve {total - 80} kişi daha.</i>"
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Panele Geri Dön", callback_data="admin_back")]])
            await query.edit_message_text(text=msg, parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "admin_guide":
            await query.answer()
            guide_text = (
                "📖 <b>Yönetici Komut Rehberi</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "👉 <code>/kanal_ekle @kanaladi</code> : Yeni zorunlu kanal ekler.\n"
                "👉 <code>/kanal_sil @kanaladi</code> : Kanalı zorunlu listeden çıkarır.\n"
                "👉 <code>/duyuru Mesajınız</code> : Tüm üyelere toplu duyuru atar.\n"
                "👉 <code>/duyuru_iptal</code> : Süren duyuruyu anında durdurur.\n"
                "👉 <code>/unban KULLANICI_ID</code> : Banlı kullanıcının engelini kaldırır."
            )
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Panele Geri Dön", callback_data="admin_back")]])
            await query.edit_message_text(text=guide_text, parse_mode="HTML", reply_markup=keyboard)
            return

        elif data == "admin_back":
            await query.answer()
            text, keyboard = build_admin_panel()
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
            return

    # C) Kullanıcı Kanal Kontrolü
    is_ok, missing = await check_channel_subscription(user_id, context)
    if not is_ok:
        await query.answer("⚠️ Zorunlu kanallara katılmalısınız!", show_alert=True)
        if missing == ["BANNED"]:
            await query.edit_message_text("⛔ <b>Banlandınız!</b>\nBota erişiminiz engellenmiştir.", parse_mode="HTML")
        else:
            await send_subscription_warning(query.message.chat_id, user_id, missing, context)
        return

    # D) Kullanıcı Sorgu Menü Butonları
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
        
        # Kullanıcı buton seçince ekran o anki mesaj üstünde güncellenir
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

# HTML Biçimlendirme
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

# --- 7. MESAJ İŞLEME VE API SORGUSU ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)

    is_ok, missing = await check_channel_subscription(user_id, context)
    if not is_ok:
        if missing == ["BANNED"]:
            await update.message.reply_text("⛔ <b>Banlandınız!</b>", parse_mode="HTML")
        else:
            await send_subscription_warning(update.effective_chat.id, user_id, missing, context)
        return

    if context.user_data.get('waiting_for_query'):
        query_text = update.message.text.strip()
        q_type = context.user_data.get('current_query_type', 'islem')
        
        context.user_data['waiting_for_query'] = False
        wait_msg = await update.message.reply_text("⏳ Sorgulanıyor, lütfen bekleyin...", parse_mode="HTML")
        
        try:
            base_api = "http://arastir.vip/api"
            params = {}
            if q_type == "adsoyad":
                parts = query_text.split(" ", 1)
                params['ad'] = parts[0]
                if len(parts) > 1: params['soyad'] = parts[1]
                endpoint = f"{base_api}/adsoyad.php"
            elif q_type == "gsmtc":
                params['gsm'] = query_text
                endpoint = f"{base_api}/gsmtc.php"
            else:
                params['tc'] = query_text
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
                        html_bytes.name = f"ArastirX_{q_type}_{query_text}.html"
                        
                        await wait_msg.delete()
                        await update.message.reply_document(
                            document=html_bytes,
                            caption=f"✅ <b>Sorgu Başarılı ({q_type.upper()})</b>\n📄 <i>Sonuçlar kesintisiz <b>HTML Dosyası</b> formatında iletildi.</i>",
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
        await update.message.reply_text("Menüyü açmak için /start yazabilirsin.")

if __name__ == '__main__':
    keep_alive()
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("panel", panel_command))
    application.add_handler(CommandHandler("kanal_ekle", add_channel_command))
    application.add_handler(CommandHandler("kanal_sil", del_channel_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("duyuru", broadcast_command))
    application.add_handler(CommandHandler("duyuru_iptal", cancel_broadcast_command))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()
