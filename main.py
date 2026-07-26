from flask import Flask
import threading
import requests
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
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

# 2. Start Komutu ve Menü Yapısı
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_text = (
        "🔍 **AraştırX | Analiz Botu** Paneline Hoş Geldiniz!\n\n"
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
    await update.message.reply_text(menu_text, parse_mode="Markdown", reply_markup=reply_markup)

# 3. Admin Panel Komutu
async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komutu kullanma yetkiniz yok.")
        return

    panel_text = (
        "⚙️ **AraştırX | Analiz Botu Yönetim Paneli**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🟢 Durum: **Aktif**"
    )
    keyboard = [
        [InlineKeyboardButton("⏸️ Durdur", callback_data="stop_bot")],
        [InlineKeyboardButton("📢 Kanal Zorunluluğu 🟢", callback_data="toggle_channel")]
    ]
    await update.message.reply_text(panel_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

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
            f"🔍 **{q_type.upper()} Sorgulama Ekranı**\n\nLütfen aratmak istediğiniz bilgiyi gönderin:\n👉 *{s_name}*",
            parse_mode="Markdown"
        )

# Yardımcı Fonksiyon: JSON Verisini Düzenli Formatlama
def format_data(data, indent=0):
    text = ""
    prefix = "  " * indent
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                text += f"{prefix}🔹 **{k.upper()}:**\n" + format_data(v, indent + 1)
            else:
                text += f"{prefix}🔹 **{k}:** `{v}`\n"
    elif isinstance(data, list):
        for idx, item in enumerate(data, 1):
            if isinstance(item, (dict, list)):
                text += f"{prefix}📌 **Kayıt {idx}:**\n" + format_data(item, indent + 1)
            else:
                text += f"{prefix}• `{item}`\n"
    return text

# 5. Gelen Mesajları ve API İsteklerini İşleme
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_query'):
        query_text = update.message.text.strip()
        q_type = context.user_data.get('current_query_type', 'islem')
        
        context.user_data['waiting_for_query'] = False
        await update.message.reply_text("⏳ Sorgulanıyor, lütfen bekleyin...", parse_mode="Markdown")
        
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
                    
                    sonuc_mesaji = f"✅ **Sorgu Başarılı ({q_type.upper()})**\n"
                    if count is not None:
                        sonuc_mesaji += f"📊 **Bulunan Kayıt:** `{count}`\n"
                    sonuc_mesaji += "━━━━━━━━━━━━━━━━━━\n"
                    
                    sonuc_mesaji += format_data(data)
                    sonuc_mesaji += "━━━━━━━━━━━━━━━━━━"
                    
                    if len(sonuc_mesaji) > 4000:
                        sonuc_mesaji = sonuc_mesaji[:3900] + "\n\n⚠️ *Sonuç çok uzun olduğu için kısaltıldı.*"
                        
                    await update.message.reply_text(sonuc_mesaji, parse_mode="Markdown")
                else:
                    err_msg = res_json.get("error", "Bilinmeyen bir hata oluştu.")
                    await update.message.reply_text(f"⚠️ **Hata:** {err_msg}", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ API Sunucu Hatası: {response.status_code}")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Bağlantı/Sistem hatası oluştu: {str(e)}")
            
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
