import os
import logging
import requests
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Logging ayarları
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

BASE_URL = "http://arastir.vip/api"

# Ana Menü Butonları
def get_main_menu():
    keyboard = [
        [
            InlineKeyboardButton("👤 TC Sorgu", callback_data="btn_tc"),
            InlineKeyboardButton("🔍 Ad Soyad", callback_data="btn_adsoyad"),
        ],
        [
            InlineKeyboardButton("👨‍👩‍👧‍👦 Aile Sorgu", callback_data="btn_aile"),
            InlineKeyboardButton("🌳 Sülale Sorgu", callback_data="btn_sulale"),
        ],
        [
            InlineKeyboardButton("👶 Çocuklar", callback_data="btn_cocuk"),
            InlineKeyboardButton("🏠 Adres Sorgu", callback_data="btn_adres"),
        ],
        [
            InlineKeyboardButton("📱 GSM ➔ TC", callback_data="btn_gsmtc"),
            InlineKeyboardButton("🆔 TC ➔ GSM", callback_data="btn_tcgsm"),
        ],
        [
            InlineKeyboardButton("💼 İşyeri Sorgu", callback_data="btn_isyeri"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    text = (
        f"Selam {user_name}! 👋\n\n"
        "Araştır API Botuna hoş geldin. Sorgulama yapmak istediğin işlemi aşağıdan seçebilirsin:"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=get_main_menu())
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=get_main_menu())


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "main_menu":
        context.user_data["action"] = None
        await start(update, context)
        return

    actions = {
        "btn_tc": ("tc", "Lütfen sorgulamak istediğiniz **11 haneli TC Kimlik Numarasını** girin:"),
        "btn_adsoyad": ("adsoyad", "Lütfen arama formatını şu şekilde girin:\n`Ad Soyad [İl] [İlçe]`\n\nÖrnek: `AHMET YILMAZ İSTANBUL KADIKÖY`"),
        "btn_aile": ("aile", "Lütfen Aile sorgusu için **TC Kimlik Numarasını** girin:"),
        "btn_sulale": ("sulale", "Lütfen Sülale sorgusu için **TC Kimlik Numarasını** girin:"),
        "btn_cocuk": ("cocuk", "Lütfen Çocuk sorgusu için **TC Kimlik Numarasını** girin:"),
        "btn_adres": ("adres", "Lütfen Adres sorgusu için **TC Kimlik Numarasını** girin:"),
        "btn_gsmtc": ("gsmtc", "Lütfen sorgulanacak **GSM Numarasını** girin (Örn: `05551234567`):"),
        "btn_tcgsm": ("tcgsm", "Lütfen GSM sorgusu için **TC Kimlik Numarasını** girin:"),
        "btn_isyeri": ("isyeri", "Lütfen İşyeri sorgusu için **TC Kimlik Numarasını** girin:"),
    }

    if data in actions:
        action_key, prompt_text = actions[data]
        context.user_data["action"] = action_key
        
        back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="main_menu")]])
        await query.message.edit_text(prompt_text, parse_mode="Markdown", reply_markup=back_btn)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get("action")
    if not action:
        await update.message.reply_text("Lütfen önce menüden yapacağınız işlemi seçin! 👇", reply_markup=get_main_menu())
        return

    input_text = update.message.text.strip()
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="main_menu")]])

    try:
        if action == "tc":
            res = requests.get(f"{BASE_URL}/tc.php", params={"tc": input_text}).json()
            if res.get("success"):
                d = res["data"]
                msg = (
                    f"📄 **TC SORGU SONUCU**\n\n"
                    f"🆔 **TC:** `{d.get('TC')}`\n"
                    f"👤 **Ad Soyad:** {d.get('ADI')} {d.get('SOYADI')}\n"
                    f"📅 **Doğum Tarihi:** {d.get('DOGUMTARIHI')}\n"
                    f"📍 **Nüfus İl/İlçe:** {d.get('NUFUSIL')} / {d.get('NUFUSILCE')}\n"
                    f"👩 **Anne Adı (TC):** {d.get('ANNEADI')} ({d.get('ANNETC')})\n"
                    f"👨 **Baba Adı (TC):** {d.get('BABAADI')} ({d.get('BABATC')})\n"
                    f"🇹🇷 **Uyruk:** {d.get('UYRUK')}"
                )
            else:
                msg = f"❌ **Hata:** {res.get('error', 'Kayıt bulunamadı.')}"

        elif action == "adsoyad":
            parts = input_text.split()
            if len(parts) < 2:
                await update.message.reply_text("⚠️ En az Ad ve Soyad girmelisiniz! Örnek: `AHMET YILMAZ`")
                return
            
            params = {"ad": parts[0], "soyad": parts[1]}
            if len(parts) >= 3: params["il"] = parts[2]
            if len(parts) >= 4: params["ilce"] = parts[3]

            res = requests.get(f"{BASE_URL}/adsoyad.php", params=params).json()
            if res.get("success") and res.get("data"):
                msg = f"🔍 **AD SOYAD SORGU (Toplam: {res.get('count', 0)})**\n\n"
                for item in res["data"][:10]: # İlk 10 sonucu göster
                    msg += f"• `{item.get('TC')}` - {item.get('ADI')} {item.get('SOYADI')} ({item.get('DOGUMTARIHI')})\n"
            else:
                msg = f"❌ **Hata:** {res.get('error', 'Sonuç bulunamadı.')}"

        elif action == "aile":
            res = requests.get(f"{BASE_URL}/aile.php", params={"tc": input_text}).json()
            if res.get("success"):
                d = res["data"]
                msg = "👨‍👩‍👧‍👦 **AİLE BİLGİLERİ**\n\n"
                anne = d.get("anne", {})
                baba = d.get("baba", {})
                msg += f"👩 **Anne:** {anne.get('ADI')} {anne.get('SOYADI')} (`{anne.get('TC')}`)\n"
                msg += f"👨 **Baba:** {baba.get('ADI')} {baba.get('SOYADI')} (`{baba.get('TC')}`)\n\n"
                msg += "👧👦 **Kardeşler:**\n"
                for k in d.get("kardesler", []):
                    msg += f"• `{k.get('TC')}` - {k.get('ADI')} {k.get('SOYADI')}\n"
            else:
                msg = f"❌ **Hata:** {res.get('error', 'Kayıt bulunamadı.')}"

        elif action == "sulale":
            res = requests.get(f"{BASE_URL}/sulale.php", params={"tc": input_text}).json()
            if res.get("success"):
                d = res["data"]
                msg = "🌳 **SÜLALE BİLGİLERİ**\n\n"
                for k, v in d.items():
                    if isinstance(v, dict):
                        msg += f"• **{k.capitalize()}:** {v.get('ADI', '')} (`{v.get('TC', '')}`)\n"
            else:
                msg = f"❌ **Hata:** {res.get('error', 'Kayıt bulunamadı.')}"

        elif action == "cocuk":
            res = requests.get(f"{BASE_URL}/cocuk.php", params={"tc": input_text}).json()
            if res.get("success") and res.get("data"):
                msg = f"👶 **ÇOCUKLARI (Toplam: {res.get('count', 0)})**\n\n"
                for c in res["data"]:
                    msg += f"• `{c.get('TC')}` - {c.get('ADI')} {c.get('SOYADI')} ({c.get('DOGUMTARIHI')})\n"
            else:
                msg = f"❌ **Hata:** {res.get('error', 'Kayıt bulunamadı.')}"

        elif action == "adres":
            res = requests.get(f"{BASE_URL}/adres.php", params={"tc": input_text}).json()
            if res.get("success"):
                d = res["data"]
                msg = (
                    f"🏠 **ADRES BİLGİSİ**\n\n"
                    f"👤 **Ad Soyad:** {d.get('AdSoyad')}\n"
                    f"📍 **Doğum Yeri:** {d.get('DogumYeri')}\n"
                    f"🏢 **Vergi No:** {d.get('VergiNumarasi')}\n"
                    f"🏡 **İkametgah:** {d.get('Ikametgah')}"
                )
            else:
                msg = f"❌ **Hata:** {res.get('error', 'Kayıt bulunamadı.')}"

        elif action == "gsmtc":
            res = requests.get(f"{BASE_URL}/gsmtc.php", params={"gsm": input_text}).json()
            if res.get("success") and res.get("data"):
                msg = "📱 **GSM ➔ TC SONUCU**\n\n"
                for tc in res["data"]:
                    msg += f"• TC: `{tc}`\n"
            else:
                msg = f"❌ **Hata:** {res.get('error', 'Kayıt bulunamadı.')}"

        elif action == "tcgsm":
            res = requests.get(f"{BASE_URL}/tcgsm.php", params={"tc": input_text}).json()
            if res.get("success") and res.get("data"):
                msg = "🆔 **TC ➔ GSM SONUCU**\n\n"
                for gsm in res["data"]:
                    msg += f"• GSM: `{gsm}`\n"
            else:
                msg = f"❌ **Hata:** {res.get('error', 'Kayıt bulunamadı.')}"

        elif action == "isyeri":
            res = requests.get(f"{BASE_URL}/isyeri.php", params={"tc": input_text}).json()
            if res.get("success") and res.get("data"):
                msg = "💼 **İŞYERİ / SGK BİLGİLERİ**\n\n"
                for i in res["data"]:
                    msg += (
                        f"🏢 **İşyeri:** {i.get('isyeriUnvani')}\n"
                        f"👤 **Çalışan:** {i.get('calisanAdSoyad')}\n"
                        f"📅 **Giriş Tarihi:** {i.get('iseGirisTarihi')}\n"
                        f"📊 **Durum:** {i.get('calismaDurumu')}\n"
                        f"🔹 **Sektör:** {i.get('isyeriSektoru')}\n"
                        "-----------------------------------\n"
                    )
            else:
                msg = f"❌ **Hata:** {res.get('error', 'Kayıt bulunamadı.')}"

    except Exception as e:
        msg = f"⚠️ Bir bağlantı hatası oluştu: {str(e)}"

    # İşlem bittikten sonra aksiyonu sıfırla ve cevabı ver
    context.user_data["action"] = None
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=back_btn)


# Render Port Kontrolü
async def handle_ping(request):
    return web.Response(text="Bot is active and running!")


async def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("HATA: BOT_TOKEN bulunamadı!")
        return

    app = ApplicationBuilder().token(token).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Aiohttp Web Server (Render İçin)
    server = web.Application()
    server.router.add_get("/", handle_ping)
    runner = web.AppRunner(server)
    await runner.setup()

    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    import asyncio
    await asyncio.Event().wait()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
