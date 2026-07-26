from flask import Flask
import threading
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

ADMIN_ID = 6073294253

# 1. Render Port İsteğini Karşılamak İçin Mini Web Sunucusu
app = Flask('')

@app.route('/')
def home():
    return "Bot Aktif ve Çalışıyor!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

# 2. Start Komutu (Görseldeki Tam Liste Alt Alta Menü)
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

# 3. Panel Komutu (Sadece Admin Erişebilir)
async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komutu kullanma yetkiniz yok.")
        return

    bot_status = "Aktif"
    total_users = 2      
    daily_commands = 4   
    daily_new_users = 2  
    required_channel = "@arastirzorunlu"

    panel_text = (
        "⚙️ **@arastirxbot**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🟢 Durum: **{bot_status}**\n"
        f"👥 Kullanıcılar: **{total_users}**\n"
        f"📊 Bugun Komut: **{daily_commands}**\n"
        f"🆕 Bugun Yeni: **{daily_new_users}**\n"
        f"🟢 Kanal: **{required_channel}**\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    keyboard = [
        [InlineKeyboardButton("⏸️ Durdur", callback_data="stop_bot")],
        [InlineKeyboardButton("📢 Kanal Zorunluluğu 🟢", callback_data="toggle_channel")],
        [InlineKeyboardButton("💬 Hoşgeldin Mesajı", callback_data="welcome_msg")],
        [InlineKeyboardButton("⚙️ Özellik Yönetimi", callback_data="features")],
        [InlineKeyboardButton("👥 Kullanıcıları Gör", callback_data="list_users")],
        [InlineKeyboardButton("⛔ Ban Yönetimi", callback_data="ban_management")],
        [InlineKeyboardButton("🔗 Referans Sistemi", callback_data="ref_system")],
        [InlineKeyboardButton("📢 Duyuru Yap", callback_data="broadcast")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(panel_text, parse_mode="Markdown", reply_markup=reply_markup)

# 4. Buton Tıklama ve Sorgu Kategorisi Seçimi
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "menu_home":
        await query.message.reply_text("🏠 Anasayfadasınız. İşlem için menüyü kullanabilirsiniz.")
    elif data.startswith("query_"):
        q_type = data.split("_")[1]
        context.user_data['waiting_for_query'] = True
        context.user_data['current_query_type'] = q_type
        
        titles = {
            "adsoyad": "Ad Soyad",
            "tc": "TC Kimlik",
            "isyeri": "İşyeri",
            "adres": "Adres",
            "aile": "Aile",
            "sulale": "Sülale",
            "cocuk": "Çocuk",
            "tcgsm": "TC - GSM",
            "gsmtc": "GSM - TC"
        }
        
        s_name = titles.get(q_type, "Sorgu")
        
        await query.message.reply_text(
            f"🔍 **{s_name} Ekranı**\n\n"
            f"Lütfen aratmak istediğiniz {s_name.lower()} bilgisini mesaj olarak gönderin:",
            parse_mode="Markdown"
        )
    
    elif data == "stop_bot":
        await query.message.reply_text("⏸️ Bot durdurma komutu alındı.")
    elif data == "toggle_channel":
        await query.message.reply_text("📢 Kanal zorunluluğu durumu değiştirildi.")
    elif data == "welcome_msg":
        await query.message.reply_text("💬 Hoşgeldin mesajı düzenleme paneli.")
    elif data == "features":
        await query.message.reply_text("⚙️ Özellik yönetimi menüsü.")
    elif data == "list_users":
        await query.message.reply_text("👥 Toplam kullanıcı listesi çıkarılıyor...")
    elif data == "ban_management":
        await query.message.reply_text("⛔ Ban yönetimi menüsü.")
    elif data == "ref_system":
        await query.message.reply_text("🔗 Referans sistemi ayarları.")
    elif data == "broadcast":
        await query.message.reply_text("📢 Duyuru göndermek için metni yazın.")

# 5. Kullanıcının Girdiği Veriyi Anında İşleme ve Sonuç Döndürme
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_query'):
        query_text = update.message.text
        q_type = context.user_data.get('current_query_type', 'islem')
        
        context.user_data['waiting_for_query'] = False
        
        # 📌 Bekletme yapmadan doğrudan sonucu burada gösteriyoruz
        # Kendi API sorgunu veya veri çekme kodunu bu bloğun içine yazabilirsin
        sonuc_metni = (
            f"✅ **Sorgu Başarılı**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 **Tür:** `{q_type.upper()}`\n"
            f"🔎 **Aranan:** `{query_text}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📄 **Sonuç:** (Bulunan veriler buraya gelecektir)"
        )
        
        await update.message.reply_text(sonuc_metni, parse_mode="Markdown")
    else:
        await update.message.reply_text("Menüyü açmak için /start yazabilirsin.")

# 6. Ana Çalıştırma Bloğu
if __name__ == '__main__':
    keep_alive()
    
    TOKEN = "8646358320:AAFuW7CHUPtCgT0wgfP9xZxf6URYTWOoYWE"
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("panel", panel_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()
