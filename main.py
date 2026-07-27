Import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ================= AYARLAR =================
# Buradaki bilgileri kendi botuna göre doldur
BOT_TOKEN = "8646358320:AAFPFwcTofU1SOShS_yHpRBa3MrhlNvF22c"
ZORUNLU_KANALLAR =["@arastirduyuru", "@arastirzorunlu"] # İstersen tek kanal bırak, istersen çoğalt.
# ===========================================

async def check_channels(user_id, context):
    """Kullanıcının belirtilen kanallarda olup olmadığını denetler."""
    for kanal in ZORUNLU_KANALLAR:
        try:
            member = await context.bot.get_chat_member(chat_id=kanal, user_id=user_id)
            # Eğer durumu 'left' (ayrılmış), 'kicked' (atılmış) veya 'restricted' ise False döndür
            if member.status in ['left', 'kicked', 'restricted']:
                return False
        except Exception as e:
            # Bot kullanıcıyı hiç görmediyse (User not found) veya admin değilse buraya düşer
            logging.error(f"Hata ({kanal}): {e} - Kullanıcı bulunamadı veya bot admin değil.")
            return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start komutu verildiğinde çalışacak ana fonksiyon."""
    user_id = update.effective_user.id
    is_member = await check_channels(user_id, context)
    
    if not is_member:
        # OTOMATİK BUTON OLUŞTURUCU: Listede kaç kanal varsa o kadar buton yapar. Çökmeyi engeller!
        keyboard = []
        for kanal in ZORUNLU_KANALLAR:
            kanal_linki = f"https://t.me/{kanal.replace('@', '')}"
            keyboard.append([InlineKeyboardButton(f"📢 {kanal} Kanalına Katıl", url=kanal_linki)])
            
        # En alta kontrol butonunu ekle
        keyboard.append([InlineKeyboardButton("🔄 Katıldım, Kontrol Et", callback_data="check")])
        
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