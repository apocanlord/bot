import os
import html
import threading
import requests
from flask import Flask
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

ADMIN_ID = 6073294253
TOKEN = "8646358320:AAEj6rlEpCxX1aLOXspgbsTNpVaYtvvGrbE"

# 1. Render Port Ayarı İçin Web Sunucusu
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

# 2. Start Komutu ve Menü Yapısı
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_text = (
        "🔍 <b>AraştırX | Analiz Botu</b> Paneline Hoş Geldiniz!\n\n"
        "İşlem yapmak için aşağıdaki menüden bir kategori seçin:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🏠 Anasayfa", callback_data="menu_home")],
        [InlineKeyboardButton("🤵 Ad Soyad Sorgula", callback_data="query_adsoyad")],
        [InlineKeyboardButton("🖨️ TC Sorgula", callback_data="query_tc")],
        [InlineKeyboardButton("🏢 İşyeri Sorgula", callback_data="query_isyeri")],
        [InlineKeyboardButton("📍 Adres Sorgula", callback_data="query_adres")],
        [InlineKeyboardButton("👥 Aile Sorgula", callback_data="query_aile")],
        [InlineKeyboardButton("👥 Sülale Sorgula", callback_data="query_sulale")],
        [InlineKeyboardButton("👶 Çocuk Sorgula", callback_data="query_cocuk")],
        [InlineKeyboardButton("📱 TC-GSM Sorgula", callback_data="query_tcgsm")],
        [InlineKeyboardButton("📱 GSM-TC Sorgula", callback_data="query_gsmtc")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(menu_text, parse_mode="HTML", reply_markup=reply_markup)

# 3. Admin Panel Komutu
async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komutu kullanma yetkiniz yok.")
        return

    panel_text = (
        "⚙️ <b>AraştırX | Analiz Botu Yönetim Paneli</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🟢 Durum: <b>Aktif</b>"
    )
    keyboard = [
        [InlineKeyboardButton("⏸️ Durdur", callback_data="stop_bot")],
        [InlineKeyboardButton("📢 Kanal Zorunluluğu 🟢", callback_data="toggle_channel")]
    ]
    await update.message.reply_text(panel_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# 4. Buton Tıklama Yönetimi
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu_home":
        await query.message.reply_text("🏠 Anasayfadasınız.")
    elif data.startswith("query_"):
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
        
        await query.message.reply_text(
            f"🔍 <b>{q_type.upper()} Sorgulama Ekranı</b>\n\nLütfen aratmak istediğiniz bilgiyi gönderin:\n👉 <i>{s_name}</i>",
            parse_mode="HTML"
        )

# HTML Uyumlu Güvenli Formatlayıcı (Karakter Patlamasını Önler)
def format_data_html(data, indent=0):
    text = ""
    prefix = "  " * indent
    if isinstance(data, dict):
        for k, v in data.items():
            k_safe = html.escape(str(k))
            if isinstance(v, (dict, list)):
                text += f"{prefix}🔹 <b>{k_safe.upper()}:</b>\n" + format_data_html(v, indent + 1)
            else:
                v_safe = html.escape(str(v))
                text += f"{prefix}🔹 <b>{k_safe}:</b> <code>{v_safe}</code>\n"
    elif isinstance(data, list):
        for idx, item in enumerate(data, 1):
            if isinstance(item, (dict, list)):
                text += f"{prefix}📌 <b>Kayıt {idx}:</b>\n" + format_data_html(item, indent + 1)
            else:
                item_safe = html.escape(str(item))
                text += f"{prefix}• <code>{item_safe}</code>\n"
    return text

# 5. Gelen Mesajları ve API İsteklerini İşleme
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_query'):
        query_text = update.message.text.strip()
        q_type = context.user_data.get('current_query_type', 'islem')
        
        context.user_data['waiting_for_query'] = False
        await update.message.reply_text("⏳ Sorgulanıyor, lütfen bekleyin...", parse_mode="HTML")
        
        try:
            base_api = "http://arastir.vip/api"
            params = {}
            
            if q_type == "adsoyad":
                parts = query_text.split(" ", 1)
                params['ad'] = parts[0]
                if len(parts) > 1:
                    params['soyad'] = parts[1]
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
                    
                    sonuc_mesaji = f"✅ <b>Sorgu Başarılı ({q_type.upper()})</b>\n"
                    if count is not None:
                        sonuc_mesaji += f"📊 <b>Bulunan Kayıt:</b> <code>{count}</code>\n"
                    sonuc_mesaji += "━━━━━━━━━━━━━━━━━━\n"
                    
                    sonuc_mesaji += format_data_html(data)
                    sonuc_mesaji += "━━━━━━━━━━━━━━━━━━"
                    
                    # Telegram 4096 karakter sınırına takılmasın
                    if len(sonuc_mesaji) > 4000:
                        sonuc_mesaji = sonuc_mesaji[:3900] + "\n\n⚠️ <i>Sonuç çok uzun olduğu için kısaltıldı.</i>"
                        
                    await update.message.reply_text(sonuc_mesaji, parse_mode="HTML")
                else:
                    err_msg = html.escape(str(res_json.get("error", "Bilinmeyen bir hata oluştu.")))
                    await update.message.reply_text(f"⚠️ <b>Hata:</b> {err_msg}", parse_mode="HTML")
            else:
                await update.message.reply_text(f"❌ API Sunucu Hatası: {response.status_code}")
                
        except Exception as e:
            err_str = html.escape(str(e))
            await update.message.reply_text(f"❌ Sistem hatası oluştu: {err_str}", parse_mode="HTML")
            
    else:
        await update.message.reply_text("Menüyü açmak için /start yazabilirsin.")

if __name__ == '__main__':
    keep_alive()
    
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("panel", panel_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()
