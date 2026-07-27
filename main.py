import os
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    await update.message.reply_text(f"Selam {user_first_name}! Bot sorunsuz ve aktif şekilde çalışıyor. 🔥")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong! 🏓 Sunucu bağlantısı canlı.")

# Render'ın kapatmaması için port dinleyen dummy HTTP sunucusu
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("HATA: BOT_TOKEN bulunamadı!")
        return

    # Telegram Bot Kurulumu
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))

    # Aiohttp Web Server (Render Port Kontrolü İçin)
    server = web.Application()
    server.router.add_get("/", handle_ping)
    runner = web.AppRunner(server)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web sunucusu {port} portunda başlatıldı.")

    # Bot Polling Başlatma
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    # Sonsuz döngüde tut
    import asyncio
    await asyncio.Event().wait()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
