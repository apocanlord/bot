from flask import Flask
import threading
from curl_cffi import requests  # <-- Standart requests yerine bunu kullanıyoruz (TLS taklidi için)
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

ADMIN_ID = 6073294253

app = Flask('')

@app.route('/')
def home():
    return "Bot Aktif ve Çalışıyor!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_text = (
        "🔍 **@arastirxbot** Araştırma ve Sorgu Paneline Hoş Geldiniz!\n\n"
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

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komutu kullanma yetkiniz yok.")
        return

    panel_text = "⚙️ **@arastirxbot Yönetim Paneli**\n━━━━━━━━━━━━━━━━━━\n🟢 Durum: **Aktif**"
    keyboard = [
        [InlineKeyboardButton("⏸️ Durdur", callback_data="stop_bot")],
        [InlineKeyboardButton("📢 Kanal Zorunluluğu 🟢", callback_data="toggle_channel")]
    ]
    await update.message.reply_text(panel_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

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
            "adsoyad": "Ad Soyad", "tc": "TC Kimlik", "isyeri": "İşyeri",
            "adres": "Adres", "aile": "Aile", "sulale": "Sülale",
            "cocuk": "Çocuk", "tcgsm": "TC - GSM", "gsmtc": "GSM - TC"
        }
        s_name = titles.get(q_type, "Sorgu")
        
        await query.message.reply_text(
            f"🔍 **{s_name} Ekranı**\n\nLütfen aratmak istediğiniz bilgiyi mesaj olarak gönderin:",
            parse_mode="Markdown"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_query'):
        query_text = update.message.text.strip()
        q_type = context.user_data.get('current_query_type', 'islem')
        
        context.user_data['waiting_for_query'] = False
        await update.message.reply_text("⏳ Sorgulanıyor, lütfen bekleyin...", parse_mode="Markdown")
        
        try:
            if q_type == "adsoyad":
                parts = query_text.split(" ", 1)
                ad = parts[0]
                soyad = parts[1] if len(parts) > 1 else ""
                api_url = f"https://arastir.vip/adsoyad.php?ad={requests.utils.quote(ad)}&soyad={requests.utils.quote(soyad)}"
            elif q_type in ["tc", "tcgsm", "cocuk", "aile", "sulale", "isyeri", "adres"]:
                api_url = f"https://arastir.vip/{q_type}.php?tc={requests.utils.quote(query_text)}"
            elif q_type == "gsmtc":
                api_url = f"https://arastir.vip/gsmtc.php?gsm={requests.utils.quote(query_text)}"
            else:
                api_url = f"https://arastir.vip/{q_type}.php?q={requests.utils.quote(query_text)}"
            
            # curl_cffi kullanarak doğrudan Chrome tarayıcı imzasıyla istek atıyoruz (Cloudflare'i takmaz)
            response = requests.get(api_url, impersonate="chrome", timeout=15)
            
            if response.status_code == 200:
                try:
                    res_data = response.json()
                except:
                    await update.message.reply_text(f"❌ API HTML döndürdü (Engel aşılamadı): {response.text[:150]}")
                    return
                
                if isinstance(res_data, list) and len(res_data) > 0:
                    res_data = res_data[0]
                    
                if isinstance(res_data, dict) and len(res_data) > 0:
                    sonuc_mesaji = f"✅ **Sorgu Başarılı ({q_type.upper()})**\n━━━━━━━━━━━━━━━━━━\n"
                    for key, val in res_data.items():
                        sonuc_mesaji += f"🔹 **{key.capitalize()}:** `{val}`\n"
                    sonuc_mesaji += "━━━━━━━━━━━━━━━━━━"
                else:
                    sonuc_mesaji = f"⚠️ Aranan kriterlere uygun veri bulunamadı."
                
                await update.message.reply_text(sonuc_mesaji, parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ API Sunucu Hatası: {response.status_code}")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Bağlantı hatası oluştu: {str(e)}")
            
    else:
        await update.message.reply_text("Menüyü açmak için /start yazabilirsin.")

if __name__ == '__main__':
    keep_alive()
    TOKEN = "8646358320:AAFuW7CHUPtCgT0wgfP9xZxf6URYTWOoYWE"
    
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("panel", panel_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()
