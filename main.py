import os
import json
import threading
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ==========================================
# 1. RENDER KEEPALIVE (PORT) SUNUCUSU
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "AraştırX Bot 7/24 Aktif!"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()


# ==========================================
# 2. JSON VERİTABANI (TELEFON & SUNUCU UYUMLU)
# ==========================================
VERI_DOSYASI = "kullanicilar.json"

def verileri_yukle():
    if not os.path.exists(VERI_DOSYASI):
        return {}
    with open(VERI_DOSYASI, "r", encoding="utf-8") as f:
        return json.load(f)

def verileri_kaydet(data):
    with open(VERI_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def vip_mi(user_id):
    data = verileri_yukle()
    user_data = data.get(str(user_id))
    if user_data and user_data.get("vip") == True:
        return True
    return False


# ==========================================
# 3. BOT MENÜLERİ VE BUTONLAR (ARAŞTIRX)
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_vip = vip_mi(user_id)
    
    durum_metni = "✨ **VIP Üye**" if is_vip else "👤 **Standart Üye**"
    
    mesaj = (
        f"🔍 **AraştırX | Analiz Botuna Hoş Geldiniz!**\n\n"
        f"Üyelik Durumunuz: {durum_metni}\n\n"
        f"Lütfen yapmak istediğiniz işlemi aşağıdaki menüden seçin:"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 Analiz Başlat", callback_data="analiz_menu")],
        [InlineKeyboardButton("💎 VIP Üyelik & Fırsatlar", callback_data="vip_menu")],
        [InlineKeyboardButton("⚙️ Hesap / Durumum", callback_data="hesap_durum")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(mesaj, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(mesaj, reply_markup=reply_markup, parse_mode="Markdown")

# Buton Tıklamaları Yönetimi
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "analiz_menu":
        if vip_mi(user_id):
            text = "📊 **Analiz Paneli:**\nVIP erişiminiz aktif! Analiz yapmak istediğiniz veriyi veya komutu girin."
        else:
            text = "⚠️ **VIP Gerekli:**\nDetaylı analiz özelliğini kullanabilmek için VIP üye olmalısınız."
        
        keyboard = [[InlineKeyboardButton("◀️ Ana Menüye Dön", callback_data="ana_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif query.data == "vip_menu":
        text = (
            "💎 **AraştırX VIP Üyelik Paketleri**\n\n"
            "• Sınırsız Analiz\n"
            "• Hızlı Sorgulama\n"
            "• 7/24 Kesintisiz Erişim\n\n"
            "VIP satın almak için yetkili ile iletişime geçebilirsiniz."
        )
        keyboard = [[InlineKeyboardButton("◀️ Ana Menüye Dön", callback_data="ana_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif query.data == "hesap_durum":
        durum = "VIP Üye" if vip_mi(user_id) else "Standart Üye"
        text = f"👤 **Kullanıcı ID:** `{user_id}`\n📊 **Üyelik Tipi:** {durum}"
        keyboard = [[InlineKeyboardButton("◀️ Ana Menüye Dön", callback_data="ana_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif query.data == "ana_menu":
        await start(update, context)


# ==========================================
# 4. BOTU BAŞLATMA
# ==========================================
if __name__ == '__main__':
    # 1. Render web portunu aç (Kapanmayı engeller)
    keep_alive()
    
    # 2. Telegram Botu Bağlantısı
    BOT_TOKEN = "8646358320:AAEj6rlEpCxX1aLOXspgbsTNpVaYtvvGrbE"
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers (İşleyiciler)
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(button_handler))

    # Botu Dinlemeye Başla
    print("AraştırX Bot Başarıyla Başlatıldı!")
    bot_app.run_polling()
