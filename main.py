import logging
import asyncio
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

async def ana_menu_gonder(update_or_query, context, is_callback=False):
    """Kullanıcı doğrulandığında açılacak olan ANA MENÜ."""
    # Buraya botun asıl açılmasını istediğin ana menü butonlarını veya metnini ekleyebilirsin
    ana_menu_text = "🎛️ **Ana Menü**\n\nSisteme başarıyla giriş yaptın. Aşağıdan işlem seçebilirsin:"
    
    # Örnek ana menü butonları (kendi butonlarına göre düzenleyebilirsin)
    keyboard = [
        [InlineKeyboardButton("🔍 İşlem Yap", callback_data="islem_yap")],
        [InlineKeyboardButton("👤 Profilim", callback_data="profil")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if is_callback:
        # Callback üzerinden geldiyse mevcut mesajı ana menü ile güncelle
        await update_or_query.edit_message_text(text=ana_menu_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        # Komut üzerinden geldiyse yeni mesaj olarak gönder
        await update_or_query.message.reply_text(text=ana_menu_text, reply_markup=reply_markup, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start komutu verildiğinde çalışacak ana fonksiyon."""
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
        
        await update.message.reply_text(
            "⚠️ **Erişim Reddedildi!**\n\nSistemi kullanabilmek için aşağıdaki kanallara katılmanız zorunludur.", 
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return

    # Zaten üyeyse direkt ana menüyü aç
    await ana_menu_gonder(update, context, is_callback=False)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kontrol Et butonunun işlevi."""
    query = update.callback_query
    if not query or not query.from_user:
        return
        
    await query.answer()
    
    user_id = query.from_user.id
    is_member = await check_channels(user_id, context)
    
    if is_member:
        # Kanallardaysa o uyarı mesajını yok et, direkt ana menüyü getir!
        await ana_menu_gonder(query, context, is_callback=True)
    else:
        await query.answer("Kanallara henüz katılmamışsın! Lütfen önce katıl.", show_alert=True)

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^check$"))
    
    print("Bot başlatıldı ve güncellendi.")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    stop_signal = asyncio.Event()
    await stop_signal.wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot durduruldu.")
