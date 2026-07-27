import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Logging ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    await update.message.reply_text(f"Selam {user_first_name}! Bot sorunsuz ve aktif şekilde çalışıyor. 🔥")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong! 🏓 Sunucu bağlantısı canlı.")

def main():
    token = os.environ.get("BOT_TOKEN")
    
    if not token:
        print("HATA: BOT_TOKEN bulunamadı!")
        return

    # Bot uygulamasını başlat
    app = ApplicationBuilder().token(token).build()

    # Komutlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))

    print("Bot başarıyla başlatıldı ve dinlemeye geçti...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
