import os
import io
import logging
import requests
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

BASE_URL = "http://arastir.vip/api"
API_TIMEOUT = 12  # Maksimum 12 saniye bekle, cevap gelmezse patlama!

def generate_html_report(title, total_count, headers, rows):
    headers_html = "".join([f"<th>{h}</th>" for h in headers])
    rows_html = ""
    for row in rows:
        tds = "".join([f"<td>{cell}</td>" for cell in row])
        rows_html += f"<tr>{tds}</tr>"

    html_content = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Rapor</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --accent-color: #38bdf8;
            --text-color: #f8fafc;
            --text-muted: #94a3b8;
            --border-color: #334155;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .header {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            padding: 24px;
            border-radius: 16px;
            border: 1px solid var(--border-color);
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{ margin: 0; font-size: 22px; color: var(--accent-color); }}
        .badge {{
            background: rgba(56, 189, 248, 0.1);
            color: var(--accent-color);
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
            border: 1px solid rgba(56, 189, 248, 0.2);
        }}
        .table-container {{
            background-color: var(--card-bg);
            border-radius: 16px;
            border: 1px solid var(--border-color);
            overflow-x: auto;
        }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }}
        th {{
            background-color: rgba(51, 65, 85, 0.5);
            color: var(--text-muted);
            padding: 14px 18px;
            font-weight: 600;
            font-size: 12px;
            border-bottom: 1px solid var(--border-color);
        }}
        td {{ padding: 14px 18px; border-bottom: 1px solid var(--border-color); }}
        .footer {{ text-align: center; margin-top: 24px; color: var(--text-muted); font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>{title}</h1>
                <p style="margin: 4px 0 0 0; color: var(--text-muted); font-size: 13px;">AraştırX VIP Analiz Sistemi</p>
            </div>
            <div class="badge">Toplam: {total_count} Kayıt</div>
        </div>
        <div class="table-container">
            <table>
                <thead><tr>{headers_html}</tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
        <div class="footer">Generatör: AraştırX Telegram Bot</div>
    </div>
</body>
</html>"""
    return html_content


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
    bot_name = context.bot.first_name
    text = (
        f"Selam {user_name}! 👋\n\n"
        f"**{bot_name}** sistemine hoş geldin. Sorgulama yapmak istediğin işlemi aşağıdan seçebilirsin:"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_main_menu())
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=get_main_menu())


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
    status_msg = await update.message.reply_text("⏳ Sorgulanıyor ve VIP Rapor hazırlanıyor...")

    try:
        if action == "adsoyad":
            parts = input_text.split()
            if len(parts) < 2:
                await status_msg.edit_text("⚠️ En az Ad ve Soyad girmelisiniz! Örnek: `AHMET YILMAZ`", parse_mode="Markdown")
                return

            params = {"ad": parts[0], "soyad": parts[1]}
            if len(parts) >= 3: params["il"] = parts[2]
            if len(parts) >= 4: params["ilce"] = parts[3]

            # Timeout koruması eklendi!
            res = requests.get(f"{BASE_URL}/adsoyad.php", params=params, timeout=API_TIMEOUT).json()
            
            if res.get("success") and res.get("data"):
                data_list = res["data"]
                count = res.get("count", len(data_list))

                if count <= 5:
                    msg = f"🔍 **AD SOYAD SORGU (Toplam: {count})**\n\n"
                    for item in data_list:
                        msg += f"• `{item.get('TC')}` - {item.get('ADI')} {item.get('SOYADI')} ({item.get('DOGUMTARIHI')})\n"
                    await status_msg.edit_text(msg, parse_mode="Markdown", reply_markup=back_btn)
                else:
                    headers = ["TC Kimlik No", "Adı", "Soyadı", "Doğum Tarihi"]
                    # Maksimum 1000 kayıtla sınırlandırıyoruz ki bellek şişmesin
                    rows = [[item.get('TC', ''), item.get('ADI', ''), item.get('SOYADI', ''), item.get('DOGUMTARIHI', '')] for item in data_list[:1000]]
                    
                    html_code = generate_html_report(f"Ad Soyad Sorgu: {input_text.upper()}", count, headers, rows)
                    
                    file_bytes = io.BytesIO(html_code.encode("utf-8"))
                    file_bytes.name = f"Sorgu_{input_text.replace(' ', '_')}.html"

                    await status_msg.delete()
                    await update.message.reply_document(
                        document=InputFile(file_bytes),
                        caption=f"📊 **Sorgu Tamamlandı!**\n\n🔍 **Arama:** `{input_text}`\n📈 **Toplam Sonuç:** `{count}` adet\n\n*Aşağıdaki HTML dosyasını açarak tüm sonuçları inceleyebilirsiniz.*",
                        parse_mode="Markdown",
                        reply_markup=back_btn
                    )
            else:
                await status_msg.edit_text(f"❌ **Hata:** {res.get('error', 'Sonuç bulunamadı.')}", reply_markup=back_btn)

        elif action == "tc":
            res = requests.get(f"{BASE_URL}/tc.php", params={"tc": input_text}, timeout=API_TIMEOUT).json()
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
            await status_msg.edit_text(msg, parse_mode="Markdown", reply_markup=back_btn)

        elif action == "gsmtc":
            res = requests.get(f"{BASE_URL}/gsmtc.php", params={"gsm": input_text}, timeout=API_TIMEOUT).json()
            if res.get("success") and res.get("data"):
                msg = "📱 **GSM ➔ TC SONUCU**\n\n" + "\n".join([f"• TC: `{tc}`" for tc in res["data"]])
            else:
                msg = f"❌ **Hata:** {res.get('error', 'Kayıt bulunamadı.')}"
            await status_msg.edit_text(msg, parse_mode="Markdown", reply_markup=back_btn)

        elif action == "tcgsm":
            res = requests.get(f"{BASE_URL}/tcgsm.php", params={"tc": input_text}, timeout=API_TIMEOUT).json()
            if res.get("success") and res.get("data"):
                msg = "🆔 **TC ➔ GSM SONUCU**\n\n" + "\n".join([f"• GSM: `{gsm}`" for gsm in res["data"]])
            else:
                msg = f"❌ **Hata:** {res.get('error', 'Kayıt bulunamadı.')}"
            await status_msg.edit_text(msg, parse_mode="Markdown", reply_markup=back_btn)

        else:
            endpoint_map = {
                "aile": ("aile.php", "Aile Sorgu"),
                "sulale": ("sulale.php", "Sülale Sorgu"),
                "cocuk": ("cocuk.php", "Çocuk Sorgu"),
                "adres": ("adres.php", "Adres Sorgu"),
                "isyeri": ("isyeri.php", "İşyeri Sorgu"),
            }
            ep, title = endpoint_map[action]
            res = requests.get(f"{BASE_URL}/{ep}", params={"tc": input_text}, timeout=API_TIMEOUT).json()
            
            if res.get("success"):
                import json
                msg = f"📄 **{title} Sonucu:**\n\n```json\n{json.dumps(res['data'], ensure_ascii=False, indent=2)[:3500]}\n```"
            else:
                msg = f"❌ **Hata:** {res.get('error', 'Kayıt bulunamadı.')}"
            await status_msg.edit_text(msg, parse_mode="Markdown", reply_markup=back_btn)

    except requests.exceptions.Timeout:
        await status_msg.edit_text("⚠️ **API Zaman Aşımı:** API sunucusu çok yavaş yanıt veriyor veya erişilemiyor.", reply_markup=back_btn)
    except Exception as e:
        await status_msg.edit_text(f"⚠️ **İşlem Hatası:** {str(e)}", reply_markup=back_btn)

    context.user_data["action"] = None


async def handle_ping(request):
    return web.Response(text="Bot is running!")


async def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("HATA: BOT_TOKEN bulunamadı!")
        return

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

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
