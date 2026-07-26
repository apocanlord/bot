from flask import Flask
import threading
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Senin Telegram ID'n panele erişim için eklendi
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

# 2. Start Komutu (Ana Sorgu Menüsü)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_text = (
        "🔍 **@arastirxbot** Araştırma ve Sorgu Paneline Hoş Geldiniz!\n\n"
        "İşlem yapmak için aşağıdaki menüyü kullanabilirsiniz:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔍 Sorgu Yap", callback_data="make_query")],
        [InlineKeyboardButton("👤 Profilim", callback_data="my_profile")]
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

# 4. Ana Çalıştırma Bloğu
if __name__ == '__main__':
    keep_alive()
    
    TOKEN = "8646358320:AAFuW7CHUPtCgT0wgfP9xZxf6URYTWOoYWE"
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("panel", panel_command))
    
    application.run_polling()
