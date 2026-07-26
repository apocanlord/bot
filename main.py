from flask import Flask
import threading
from telegram import Update
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

# 2. Panel Komutu Fonksiyonu
async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_status = "Çevrimiçi"
    total_users = 0      
    daily_commands = 0   
    daily_new_users = 0  
    required_channel = "Ayarlanmadı"

    panel_text = (
        "⚙️ **@arastirxbot** Yönetim Paneli\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 **Sistem Durumu:** {bot_status}\n"
        f"👥 **Toplam Kullanıcı:** `{total_users}`\n"
        f"📊 **Günlük İstatistik:** `{daily_commands}` Komut / `{daily_new_users}` Yeni\n"
        f"📢 **Zorunlu Kanal:** `{required_channel}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ *Son Güncelleme: Anlık*"
    )

    await update.message.reply_text(panel_text, parse_mode="Markdown")

# 3. Ana Çalıştırma Bloğu
if __name__ == '__main__':
    keep_alive()
    
    # Bot Token'ın buraya eklendi
    TOKEN = "8646358320:AAFuW7CHUPtCgT0wgfP9xZxf6URYTWOoYWE"
    
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("panel", panel_command))
    application.run_polling()
