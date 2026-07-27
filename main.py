from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = "8646358320:AAFPFwcTofU1SOShS_yHpRBa3MrhlNvF22c"

ZORUNLU_KANALLAR = [
    "@arastirduyuru",
    "@arastirzorunlu"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    try:
        for kanal in ZORUNLU_KANALLAR:
            uye = await context.bot.get_chat_member(kanal, user_id)

            if uye.status in ["left", "kicked"]:
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "📢 Araştır Duyuru",
                            url="https://t.me/arastirduyuru"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "📢 Araştır Zorunlu",
                            url="https://t.me/arastirzorunlu"
                        )
                    ]
                ]

                await update.message.reply_text(
                    "⚠️ Botu kullanabilmek için aşağıdaki iki kanala da katılmanız zorunludur.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

    except Exception as e:
        print(e)
        await update.message.reply_text(
            "Kanal kontrolü yapılamadı. Botun her iki kanalda da yönetici olduğundan emin olun."
        )
        return

    await update.message.reply_text(
        "✅ Doğrulama başarılı!\n\nBotu kullanabilirsiniz."
    )


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    print("Bot çalışıyor...")
    app.run_polling()