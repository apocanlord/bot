import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Token, Admin ID, Kanal ve API Bilgileri
BOT_TOKEN = "8646358320:AAFuW7CHUPtCgT0wgfP9xZxf6URYTWOoYWE"
ADMIN_ID = 6073294253
CHANNEL = "@arastirduyuru"
BASE_URL = 'http://arastir.vip/api'

# Cloudflare (403) engeline takılmamak için tarayıcı gibi görünme başlığı
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

async def is_member(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception:
        return False

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if await is_member(user_id, context):
        keyboard = [
            [InlineKeyboardButton("🆔 TC Sorgu", callback_data="q_tc"), InlineKeyboardButton("👤 Ad Soyad", callback_data="q_adsoyad")],
            [InlineKeyboardButton("👨‍👩‍👧 Aile", callback_data="q_aile"), InlineKeyboardButton("🌳 Sülale", callback_data="q_sulale")],
            [InlineKeyboardButton("👶 Çocuklar", callback_data="q_cocuk"), InlineKeyboardButton("🏠 Adres", callback_data="q_adres")],
            [InlineKeyboardButton("📱 GSM → TC", callback_data="q_gsmtc"), InlineKeyboardButton("📞 TC → GSM", callback_data="q_tcgsm")],
            [InlineKeyboardButton("🏢 İşyeri", callback_data="q_isyeri")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "✨ **Hoş Geldin! Lütfen yapmak istediğin sorgu türünü seçin veya komut kullanın:**",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"❌ Botu kullanabilmek için önce kanala katılmalısın:\nhttps://t.me/arastirduyuru")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    messages = {
        "q_tc": "🆔 **TC Sorgu** için kullanım: `/tc [TCno]`",
        "q_adsoyad": "👤 **Ad Soyad** için kullanım: `/adsoyad [Ad] [Soyad]`",
        "q_aile": "👨‍👩‍👧 **Aile** için kullanım: `/aile [TCno]`",
        "q_sulale": "🌳 **Sülale** için kullanım: `/sulale [TCno]`",
        "q_cocuk": "👶 **Çocuklar** için kullanım: `/cocuk [TCno]`",
        "q_adres": "🏠 **Adres** için kullanım: `/adres [TCno]`",
        "q_gsmtc": "📱 **GSM → TC** için kullanım: `/gsmtc [GSM]`",
        "q_tcgsm": "📞 **TC → GSM** için kullanım: `/tcgsm [TCno]`",
        "q_isyeri": "🏢 **İşyeri** için kullanım: `/isyeri [TCno]`"
    }
    await query.message.reply_text(messages.get(data, "Geçersiz seçim."), parse_mode="Markdown")

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("⚙️ **Yönetim Paneli**\n\n- Bot: Aktif 🚀\n- Kanal: @arastirduyuru ✅\n- Cloudflare Bypass (User-Agent): Aktif ✅", parse_mode="Markdown")
    else:
        await update.message.reply_text("Bu komutu kullanmaya yetkin yok.")

# --- ENDPOINT KOMUTLARI ---

async def tc_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(update.effective_user.id, context):
        await update.message.reply_text("❌ Önce kanala katılmalısın: https://t.me/arastirduyuru")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Örnek kullanım: `/tc 12345678901`", parse_mode="Markdown")
        return
    
    try:
        res = requests.get(f"{BASE_URL}/tc.php", params={"tc": context.args[0]}, headers=HEADERS).json()
        if res.get("success"):
            d = res.get("data", {})
            text = (
                "🆔 **TC Sorgu Sonucu:**\n\n"
                f"📌 **TC:** {d.get('TC', '-')}\n"
                f"👤 **Ad Soyad:** {d.get('ADI', '-')} {d.get('SOYADI', '-')}\n"
                f"🎂 **Doğum Tarihi:** {d.get('DOGUMTARIHI', '-')}\n"
                f"📍 **Nüfus İl/İlçe:** {d.get('NUFUSIL', '-')}/{d.get('NUFUSILCE', '-')}\n"
                f"👩 **Anne:** {d.get('ANNEADI', '-')} ({d.get('ANNETC', '-')})\n"
                f"👨 **Baba:** {d.get('BABAADI', '-')} ({d.get('BABATC', '-')})"
            )
            await update.message.reply_text(text, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Hata: {res.get('error', 'Kayıт bulunamadı.')}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Bağlantı hatası: {e}")

async def adsoyad_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(update.effective_user.id, context):
        await update.message.reply_text("❌ Önce kanala katılmalısın: https://t.me/arastirduyuru")
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Örnek kullanım: `/adsoyad AHMET YILMAZ`", parse_mode="Markdown")
        return
    
    try:
        res = requests.get(f"{BASE_URL}/adsoyad.php", params={"ad": context.args[0], "soyad": context.args[1]}, headers=HEADERS).json()
        if res.get("success"):
            data_list = res.get("data", [])
            text = f"👤 **Ad Soyad Sonucu** (Toplam: {res.get('count', 0)})\n\n"
            for i, item in enumerate(data_list[:10], 1):
                text += f"{i}. {item.get('ADI')} {item.get('SOYADI')} - TC: {item.get('TC')} - Doğum: {item.get('DOGUMTARIHI')}\n"
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("❌ Kayıt bulunamadı.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Hata: {e}")

async def aile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(update.effective_user.id, context):
        await update.message.reply_text("❌ Önce kanala katılmalısın: https://t.me/arastirduyuru")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Örnek kullanım: `/aile 12345678901`", parse_mode="Markdown")
        return

    try:
        res = requests.get(f"{BASE_URL}/aile.php", params={"tc": context.args[0]}, headers=HEADERS).json()
        if res.get("success"):
            d = res.get("data", {})
            anne = d.get("anne", {})
            baba = d.get("baba", {})
            text = (
                "👨‍👩‍👧 **Aile Bilgileri:**\n\n"
                f"👩 Anne: {anne.get('ADI')} {anne.get('SOYADI')} (TC: {anne.get('TC')})\n"
                f"👨 Baba: {baba.get('ADI')} {baba.get('SOYADI')} (TC: {baba.get('TC')})\n"
            )
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("❌ Kayıt bulunamadı.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Hata: {e}")

async def sulale_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(update.effective_user.id, context):
        await update.message.reply_text("❌ Önce kanala katılmalısın: https://t.me/arastirduyuru")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Örnek kullanım: `/sulale 12345678901`", parse_mode="Markdown")
        return

    try:
        res = requests.get(f"{BASE_URL}/sulale.php", params={"tc": context.args[0]}, headers=HEADERS).json()
        if res.get("success"):
            d = res.get("data", {})
            k = d.get("kendisi", {})
            text = f"🌳 **Sülale Bilgisi:**\nSorgulanan: {k.get('ADI')} {k.get('SOYADI')}"
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("❌ Kayıt bulunamadı.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Hata: {e}")

async def cocuk_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(update.effective_user.id, context):
        await update.message.reply_text("❌ Önce kanala katılmalısın: https://t.me/arastirduyuru")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Örnek kullanım: `/cocuk 12345678901`", parse_mode="Markdown")
        return

    try:
        res = requests.get(f"{BASE_URL}/cocuk.php", params={"tc": context.args[0]}, headers=HEADERS).json()
        if res.get("success"):
            data_list = res.get("data", [])
            text = f"👶 **Çocuklar (Toplam: {res.get('count', 0)}):\n\n"
            for i, c in enumerate(data_list[:10], 1):
                text += f"{i}. {c.get('ADI')} {c.get('SOYADI')} - TC: {c.get('TC')}\n"
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("❌ Çocuk kaydı bulunamadı.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Hata: {e}")

async def adres_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(update.effective_user.id, context):
        await update.message.reply_text("❌ Önce kanala katılmalısın: https://t.me/arastirduyuru")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Örnek kullanım: `/adres 12345678901`", parse_mode="Markdown")
        return

    try:
        res = requests.get(f"{BASE_URL}/adres.php", params={"tc": context.args[0]}, headers=HEADERS).json()
        if res.get("success"):
            d = res.get("data", {})
            text = (
                "🏠 **Adres Bilgisi:**\n\n"
                f"👤 Ad Soyad: {d.get('AdSoyad')}\n"
                f"📍 İkametgah: {d.get('Ikametgah')}"
            )
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("❌ Kayıt bulunamadı.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Hata: {e}")

async def gsmtc_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(update.effective_user.id, context):
        await update.message.reply_text("❌ Önce kanala katılmalısın: https://t.me/arastirduyuru")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Örnek kullanım: `/gsmtc 05551234567`", parse_mode="Markdown")
        return

    try:
        res = requests.get(f"{BASE_URL}/gsmtc.php", params={"gsm": context.args[0]}, headers=HEADERS).json()
        if res.get("success"):
            tcs = res.get("data", [])
            text = f"📱 **GSM -> TC Sonucu:**\n" + "\n".join([f"📌 {tc}" for tc in tcs[:10]])
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("❌ Kayıt bulunamadı.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Hata: {e}")

async def tcgsm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(update.effective_user.id, context):
        await update.message.reply_text("❌ Önce kanala katılmalısın: https://t.me/arastirduyuru")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Örnek kullanım: `/tcgsm 12345678901`", parse_mode="Markdown")
        return

    try:
        res = requests.get(f"{BASE_URL}/tcgsm.php", params={"tc": context.args[0]}, headers=HEADERS).json()
        if res.get("success"):
            gsms = res.get("data", [])
            text = f"📞 **TC -> GSM Sonucu:**\n" + "\n".join([f"📱 {gsm}" for gsm in gsms[:10]])
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("❌ Kayıt bulunamadı.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Hata: {e}")

async def isyeri_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(update.effective_user.id, context):
        await update.message.reply_text("❌ Önce kanala katılmalısın: https://t.me/arastirduyuru")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Örnek kullanım: `/isyeri 12345678901`", parse_mode="Markdown")
        return

    try:
        res = requests.get(f"{BASE_URL}/isyeri.php", params={"tc": context.args[0]}, headers=HEADERS).json()
        if res.get("success"):
            items = res.get("data", [])
            text = f"🏢 **İşyeri Bilgileri:**\n"
            for i, item in enumerate(items[:5], 1):
                text += f"{i}. {item.get('isyeriUnvani')} - Durum: {item.get('calismaDurumu')}\n"
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("❌ Kayıt bulunamadı.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Hata: {e}")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Komut ve Buton Yöneticileri
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("panel", panel_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Endpoint Handler'ları
    application.add_handler(CommandHandler("tc", tc_handler))
    application.add_handler(CommandHandler("adsoyad", adsoyad_handler))
    application.add_handler(CommandHandler("aile", aile_handler))
    application.add_handler(CommandHandler("sulale", sulale_handler))
    application.add_handler(CommandHandler("cocuk", cocuk_handler))
    application.add_handler(CommandHandler("adres", adres_handler))
    application.add_handler(CommandHandler("gsmtc", gsmtc_handler))
    application.add_handler(CommandHandler("tcgsm", tcgsm_handler))
    application.add_handler(CommandHandler("isyeri", isyeri_handler))

    print("Tam donanımlı bot aktif ve çalışıyor...")
    application.run_polling()

if __name__ == '__main__':
    main()
