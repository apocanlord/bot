import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ================= AYARLAR =================
BOT_TOKEN = "8646358320:AAFPFwcTofU1SOShS_yHpRBa3MrhlNvF22c"
ZORUNLU_KANALLAR = ["@arastirduyuru", "@arastirzorunlu"] 
# ===========================================

async def check_channels(user_id, context):
    """Kullanıcının belirtilen kanallarda olup olmadığını denetler."""
    for kanal in ZORUNLU_KANALLAR:
        try:
            member = await context.bot.get_chat_member(chat_id=kanal, user_id=user_id)
            if member.status in ['left', 'kicked', 'restricted']:
                return False
        except Exception as e:
            logging.error(f"Hata ({kanal}): {e} - Kullanıcı bulunamadı veya bot admin değil.")
            return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start komutu verildiğinde çalışacak ana fonksiyon."""
    # Güvenlik önlemi: update.message veya effective_user boş olmasın
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    is_member = await check_channels(user_id, context)
    
    if not is_member:
        keyboard = []
        for kanal in ZORUNLU_KANALLAR:
            kanal_linki = f"https://t.me/{kanal.replace('@', '')}"
            keyboard.append([InlineKeyboardButton(f"📢 {kanal} Kanalına Katıl", url=kanal_linki)])
            
        keyboard.append([InlineKeyboardButton("🔄 Katıldım, Kontrol Et", callback_data="check")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Yeni kullanıcıda ekranın kesin çıkması için reply_text kullanıyoruz
        await update.message.reply_text(
            "⚠️ **Erişim Reddedildi!**\n\nSistemi kullanabilmek için aşağıdaki kanallara katılmanız zorunludur.", 
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text("✅ **Doğrulama Başarılı!**\n\nSisteme hoş geldin, artık botu kullanabilirsin.", parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kontrol Et butonunun işlevi."""
    query = update.callback_query
    if not query or not query.from_user:
        return
        
    await query.answer()
    
    user_id = query.from_user.id
    is_member = await check_channels(user_id, context)
    
    if is_member:
        try:
            await query.edit_message_text("✅ **Doğrulama Başarılı!**\n\nSisteme hoş geldin, artık botu kullanabilirsin.", parse_mode="Markdown")
        except Exception:
            await context.bot.send_message(chat_id=user_id, text="✅ **Doğrulama Başarılı!**\n\nSisteme hoş geldin, artık botu kullanabilirsin.", parse_mode="Markdown")
    else:
        await query.answer("Kanallara henüz katılmamışsın! Lütfen önce katıl.", show_alert=True)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^check$"))
    
    print("Bot başlatıldı ve güncellendi.")
    app.run_polling()
