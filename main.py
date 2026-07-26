import os
import json
import threading
from flask import Flask
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update

# ==========================================
# 1. RENDER İÇİN KEEPALIVE (PORT) SUNUCUSU
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot 7/24 Aktif ve Çalışıyor!"

def run():
    # Render'ın kapanmaması için beklediği portu dinliyoruz
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()


# ==========================================
# 2. TELEFON / JSON DOSYA YÖNETİMİ (HAFİF DB)
# ==========================================
VERI_DOSYASI = "kullanicilar.json"

def verileri_yukle():
    if not os.path.exists(VERI_DOSYASI):
        return {}
    with open(VERI_DOSYASI, "r", encoding="utf-8") as f:
        return json.load(f)

def verileri_kaydet(data):
    with open(VERI_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def vip_ekle(user_id, bitis_tarihi):
    data = verileri_yukle()
    data[str(user_id)] = {
        "vip": True,
        "bitis_tarihi": bitis_tarihi
    }
    verileri_kaydet(data)

def vip_mi(user_id):
    data = verileri_yukle()
    user_data = data.get(str(user_id))
    if user_data and user_data.get("vip") == True:
        return True
    return False


# ==========================================
# 3. TELEGRAM BOT KOMUTLARI & MANTIĞI
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if vip_mi(user_id):
        await update.message.reply_text("Hoş geldin VIP Üye! Tüm özellikler aktif.")
    else:
        await update.message.reply_text("Selam! Standart kullanıcısın. VIP üyelik için menüyü inceleyebilirsin.")


# ==========================================
# 4. BOTU BAŞLATMA
# ==========================================
if __name__ == '__main__':
    # 1. Render web portunu aç (Render kapanmasın diye)
    keep_alive()
    
    # 2. Telegram Bot Entegrasyonu
    BOT_TOKEN = "8646358320:AAEj6rlEpCxX1aLOXspgbsTNpVaYtvvGrbE"
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Komutları ekle
    bot_app.add_handler(CommandHandler("start", start))

    # Botu dinlemeye başla
    print("Bot başarıyla başlatıldı!")
    bot_app.run_polling()
