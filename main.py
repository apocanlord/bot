import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ================= AYARLAR =================
# Buradaki bilgileri kendi botuna göre doldur
BOT_TOKEN = "8646358320:AAEj6rlEpCxX1aLOXspgbsTNpVaYtvvGrbE"
ZORUNLU_KANALLAR = ["@arastirduyuru", "@arastirzorunlu"] 
# ===========================================

async def check_channels(user_id, context):
    """Kullanıcının belirtilen kanallarda olup olmadığını denetler."""
    for kanal in ZORUNLU_KANALLAR:
        try:
            member = await context.bot.get_chat_member(chat_id=kanal, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception as e:
            logging.error(f"Hata ({kanal}): {e} - Bot bu kanalda admin olmayabilir.")
            return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start komutu verildiğinde çalışacak ana fonksiyon."""
    user_id = update.effective_user.id
    is_member = await check_channels(user_id, context)
    
    if not is_member:
        # Kanallardan birine bile üye değilse butonları göster
        keyboard = [
            [InlineKeyboardButton("📢 1. Kanala Katıl", url=f"https://t.me/{ZORUNLU_KANALLAR[0].replace('@', '')}")],
            [InlineKeyboardButton("📢 2. Kanala Katıl", url=f"https://t.me/{ZORUNLU_KANALLAR[1].replace('@', '')}")],
            [InlineKeyboardButton("🔄 Kontrol Et", callback_data="check")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "⚠️ **Erişim Reddedildi!**\n\nSistemi kullanabilmek için aşağıdaki kanallara katılmanız zorunludur.", 
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return

    # Kanallardaysa botun ana mesajını gönder
    await update.message.reply_text("✅ **Doğrulama Başarılı!**\n\nSisteme hoş geldin, artık botu kullanabilirsin.", parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kontrol Et butonunun işlevi."""
    query = update.callback_query
    await query.answer()
    
    is_member = await check_channels(query.from_user.id, context)
    if is_member:
        await query.edit_message_text("✅ **Doğrulama Başarılı!**\n\nSisteme hoş geldin, artık botu kullanabilirsin.", parse_mode="Markdown")
    else:
        await query.answer("Kanallara henüz katılmamışsın!", show_alert=True)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^check$"))
    
    print("Bot başlatıldı. Kapatmak için CTRL+C yapabilirsiniz.")
    app.run_polling()