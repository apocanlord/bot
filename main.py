from flask import Flask
import threading
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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

# 2. Start Komutu
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Bot aktif! Yönetim paneli için /panel yazabilirsin.")

# 3. Panel Komutu (Görseldeki Tasarım ve Gerçek Butonlar)
async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 📌 Buraya veritabanından çektiğin gerçek verileri bağlayabilirsin
    bot_status = "Aktif"
    total_users = 2      
    daily_commands = 4   
    daily_new_users = 2  
    required_channel = "@arastirzorunlu" # Veya "Yok"

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

    # Ekran görüntündeki interaktif yönetim butonları
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

# 4. Ana Çalıştırma Bloğu
if __name__ == '__main__':
    keep_alive()
    
    TOKEN = "8646358320:AAFuW7CHUPtCgT0wgfP9xZxf6URYTWOoYWE"
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Komutları ekliyoruz
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("panel", panel_command))
    
    application.run_polling()
