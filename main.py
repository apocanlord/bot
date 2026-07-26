import os
import json
import threading
from datetime import datetime
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# ==========================================
# 1. RENDER KEEPALIVE (PORT SUNUCUSU)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "AraştırX Bot 7/24 Aktif!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()


# ==========================================
# 2. SABİT AYARLAR & AYAR DOSYASI
# ==========================================
BOT_TOKEN = "8646358320:AAEj6rlEpCxX1aLOXspgbsTNpVaYtvvGrbE"
ADMIN_ID = 6073294253
VERI_DOSYASI = "database.json"


# ==========================================
# 3. VERİTABANI YÖNETİMİ
# ==========================================
def verileri_yukle():
    if not os.path.exists(VERI_DOSYASI):
        default_data = {
            "users": {},
            "banned_users": [],
            "bugun_gelen": 0,
            "son_bugun_tarih": datetime.now().strftime("%Y-%m-%d"),
            "bakim_modu": False,
            "kanal_sarti": True,
            "zorunlu_kanallar": ["@arastirduyuru", "@arastirzorunlu"]
        }
        verileri_kaydet(default_data)
        return default_data
    with open(VERI_DOSYASI, "r", encoding="utf-8") as f:
        data = json.load(f)
        
        # Eksik alan kontrolleri
        if "banned_users" not in data: data["banned_users"] = []
        if "bugun_gelen" not in data: data["bugun_gelen"] = 0
        if "son_bugun_tarih" not in data: data["son_bugun_tarih"] = datetime.now().strftime("%Y-%m-%d")
        if "bakim_modu" not in data: data["bakim_modu"] = False
        if "kanal_sarti" not in data: data["kanal_sarti"] = True
        if "zorunlu_kanallar" not in data: data["zorunlu_kanallar"] = ["@arastirduyuru", "@arastirzorunlu"]
        
        # Günlük sayaç sıfırlama
        today = datetime.now().strftime("%Y-%m-%d")
        if data.get("son_bugun_tarih") != today:
            data["bugun_gelen"] = 0
            data["son_bugun_tarih"] = today
            verileri_kaydet(data)
            
        return data

def verileri_kaydet(data):
    with open(VERI_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def kullanici_kaydet_ve_guncelle(user):
    db = verileri_yukle()
    s_id = str(user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    username = f"@{user.username}" if user.username else "Yok"
    
    if s_id not in db["users"]:
        db["users"][s_id] = {
            "name": user.first_name or "Kullanıcı",
            "username": username,
            "vip": False,
            "katilma_tarihi": today
        }
        db["bugun_gelen"] = db.get("bugun_gelen", 0) + 1
    else:
        db["users"][s_id]["name"] = user.first_name or "Kullanıcı"
        db["users"][s_id]["username"] = username
        
    verileri_kaydet(db)
    return db["users"][s_id]


# ==========================================
# 4. KANAL KATILIM KONTROLÜ
# ==========================================
async def kanallara_katildi_mi(bot, user_id):
    db = verileri_yukle()
    if not db.get("kanal_sarti", True) or user_id == ADMIN_ID:
        return True, []

    eksik_kanallar = []
    for kanal in db.get("zorunlu_kanallar", []):
        try:
            member = await bot.get_chat_member(chat_id=kanal, user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                eksik_kanallar.append(kanal)
        except Exception:
            continue
            
    return len(eksik_kanallar) == 0, eksik_kanallar


# ==========================================
# 5. KULLANICI ANA MENÜSÜ (/start)
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = verileri_yukle()
    s_id = str(user.id)
    
    # Ban Kontrolü
    if s_id in db.get("banned_users", []):
        msg = "❌ **Bot kullanımınız engellenmiştir (Banlandınız).**"
        if update.message: await update.message.reply_text(msg)
        return

    # Bakım Modu Kontrolü
    if db.get("bakim_modu") and user.id != ADMIN_ID:
        msg = "⚙️ **Bot şu an bakım modundadır. Lütfen daha sonra tekrar deneyiniz.**"
        if update.message: await update.message.reply_text(msg)
        return

    u_info = kullanici_kaydet_ve_guncelle(user)

    # Kanal Şartı Kontrolü
    katildi, eksikler = await kanallara_katildi_mi(context.bot, user.id)
    if not katildi:
        keyboard = []
        for k in eksikler:
            clean_k = k.replace('@', '')
            keyboard.append([InlineKeyboardButton(f"📢 {k} Kanalına Katıl", url=f"https://t.me/{clean_k}")])
        keyboard.append([InlineKeyboardButton("✅ Katıldım, Kontrol Et", callback_data="kanal_kontrol")])
        
        msg = "⚠️ **Botu kullanabilmek için lütfen aşağıdaki zorunlu kanallara katılın:**"
        if update.message:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Kullanıcı Arayüzü (Resim 2 Birebir Uyumlu)
    hak_text = "Sınırsız  ∞" if (u_info.get("vip") or user.id == ADMIN_ID) else "3 / 3"
    
    mesaj = (
        f"🔍 **AraştırX | Analiz Botu** Paneline Hoş Geldiniz!\n\n"
        f"📊 **Kalan Günlük Sorgu Hakkınız:**\n"
        f"{hak_text}\n\n"
        f"İşlem yapmak için aşağıdaki menüden bir kategori seçin:"
    )

    keyboard = [
        [InlineKeyboardButton("👤 Ad Soyad Sorgula", callback_data="sorgu_adsoyad"), InlineKeyboardButton("🖨 TC Sorgula", callback_data="sorgu_tc")],
        [InlineKeyboardButton("🏢 İşyeri Sorgula", callback_data="sorgu_isyeri"), InlineKeyboardButton("📍 Adres Sorgula", callback_data="sorgu_adres")],
        [InlineKeyboardButton("👥 Aile Sorgula", callback_data="sorgu_aile"), InlineKeyboardButton("👥 Sülale Sorgula", callback_data="sorgu_sulale")],
        [InlineKeyboardButton("👶 Çocuk Sorgula", callback_data="sorgu_cocuk")],
        [InlineKeyboardButton("📱 TC-GSM Sorgula", callback_data="sorgu_tcgsm"), InlineKeyboardButton("📱 GSM-TC Sorgula", callback_data="sorgu_gsmtc")],
        [InlineKeyboardButton("👤 Profil Kartım", callback_data="profil_im"), InlineKeyboardButton("🔗 Davet Et / VIP K...", callback_data="davet_et")],
        [InlineKeyboardButton("👑 VIP Satın Al / Fiyatlar", callback_data="vip_fiyatlar")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(mesaj, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(mesaj, reply_markup=reply_markup, parse_mode="Markdown")


# ==========================================
# 6. YÖNETİCİ PANELİ (/panel) (Resim 1 Uyumlu)
# ==========================================
async def panel_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komutu sadece bot sahibi kullanabilir.")
        return
    await admin_panel_goster(update, context)

async def admin_panel_goster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = verileri_yukle()
    
    bugun_gelen = db.get("bugun_gelen", 0)
    toplam_user = len(db.get("users", {}))
    vip_user = sum(1 for u in db.get("users", {}).values() if u.get("vip"))
    banli_user = len(db.get("banned_users", []))
    
    bakim_str = "🔴 KAPALI" if not db.get("bakim_modu") else "🟢 AÇIK"
    sart_str = "🟢 AÇIK" if db.get("kanal_sarti") else "🔴 KAPALI"
    
    kanallar_listesi = "\n".join([f"• {k}" for k in db.get("zorunlu_kanallar", [])]) or "• Yok"

    mesaj = (
        f"⚙️ **AraştırX | Yönetici Paneli**\n"
        f"────────────────────────\n"
        f"📆 **Bugün Gelen:** {bugun_gelen} | 📊 **Toplam:** {toplam_user}\n"
        f"👑 **VIP:** {vip_user} | 🚫 **Banlı:** {banli_user}\n"
        f"🛠 **Bakım Modu:** {bakim_str} | 📢 **Kanal Şartı:** {sart_str}\n\n"
        f"📌 **Kanallar:**\n"
        f"{kanallar_listesi}\n"
        f"────────────────────────"
    )

    bakim_btn = f"Bakım: {bakim_str}"
    sart_btn = f"Şart: {sart_str}"

    keyboard = [
        [InlineKeyboardButton("👑 VIP Ver", callback_data="adm_vip_ver"), InlineKeyboardButton("❌ VIP Kaldır", callback_data="adm_vip_kaldir")],
        [InlineKeyboardButton(bakim_btn, callback_data="adm_toggle_bakim"), InlineKeyboardButton(sart_btn, callback_data="adm_toggle_sart")],
        [InlineKeyboardButton("➕ Kanal Ekle", callback_data="adm_kanal_ekle"), InlineKeyboardButton("➖ Kanal Sil", callback_data="adm_kanal_sil")],
        [InlineKeyboardButton("📢 Duyuru Gönder", callback_data="adm_duyuru_gonder"), InlineKeyboardButton("👥 Kullanıcı Listesi", callback_data="adm_user_list")],
        [InlineKeyboardButton("⛔️ Banla / Ban Kaldır", callback_data="adm_ban_yonet")],
        [InlineKeyboardButton("🔄 Paneli Yenile", callback_data="adm_panel_refresh")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(mesaj, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(mesaj, reply_markup=reply_markup, parse_mode="Markdown")


# ==========================================
# 7. PANEL BUTON İŞLEYİCİLERİ
# ==========================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    db = verileri_yukle()

    if data == "kanal_kontrol":
        await start(update, context)
        return

    # --- ADMIN BUTONLARI ---
    if user_id == ADMIN_ID:
        if data == "adm_panel_refresh":
            await admin_panel_goster(update, context)
            return

        elif data == "adm_toggle_bakim":
            db["bakim_modu"] = not db.get("bakim_modu", False)
            verileri_kaydet(db)
            await admin_panel_goster(update, context)
            return

        elif data == "adm_toggle_sart":
            db["kanal_sarti"] = not db.get("kanal_sarti", True)
            verileri_kaydet(db)
            await admin_panel_goster(update, context)
            return

        elif data == "adm_vip_ver":
            context.user_data["beklenen_islem"] = "vip_ver"
            await query.message.edit_text("👑 **VIP Verilecek Kullanıcının Telegram ID'sini Yazın:**", parse_mode="Markdown")
            return

        elif data == "adm_vip_kaldir":
            context.user_data["beklenen_islem"] = "vip_kaldir"
            await query.message.edit_text("❌ **VIP'si Kaldırılacak Kullanıcının Telegram ID'sini Yazın:**", parse_mode="Markdown")
            return

        elif data == "adm_kanal_ekle":
            context.user_data["beklenen_islem"] = "kanal_ekle"
            await query.message.edit_text("➕ **Eklenecek Kanal Kullanıcı Adını Yazın (Örn: `@arastirduyuru`):**", parse_mode="Markdown")
            return

        elif data == "adm_kanal_sil":
            context.user_data["beklenen_islem"] = "kanal_sil"
            await query.message.edit_text("➖ **Silinecek Kanal Kullanıcı Adını Yazın (Örn: `@arastirduyuru`):**", parse_mode="Markdown")
            return

        elif data == "adm_ban_yonet":
            context.user_data["beklenen_islem"] = "ban_yonet"
            await query.message.edit_text("⛔️ **Banlayacağınız veya Banını Kaldıracağınız Kullanıcı ID'sini Yazın:**", parse_mode="Markdown")
            return

        elif data == "adm_duyuru_gonder":
            context.user_data["beklenen_islem"] = "duyuru_gonder"
            await query.message.edit_text("📢 **Tüm Kullanıcılara Gönderilecek Duyuru Metnini Yazın:**", parse_mode="Markdown")
            return

        elif data == "adm_user_list":
            users = db.get("users", {})
            metin = f"👥 **Kullanıcı Listesi ({len(users)} Kişi):**\n\n"
            count = 0
            for uid, uinfo in users.items():
                count += 1
                v_tag = " [VIP]" if uinfo.get("vip") else ""
                metin += f"{count}. {uinfo.get('name')} ({uinfo.get('username')}) - `{uid}`{v_tag}\n"
                if count >= 30:
                    metin += "\n*(Son 30 kullanıcı listelendi)*"
                    break
            
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Panele Dön", callback_data="adm_panel_refresh")]])
            await query.message.edit_text(metin, reply_markup=kb, parse_mode="Markdown")
            return

    # --- KULLANICI SORGU BUTONLARI BILDIRIMI ---
    if data.startswith("sorgu_"):
        sorgu_adi = data.replace("sorgu_", "").upper()
        await query.message.reply_text(f"🔍 **{sorgu_adi} Sorgulamak için arama verisini mesaj olarak iletin.**", parse_mode="Markdown")
    elif data == "profil_im":
        u_info = db.get("users", {}).get(str(user_id), {})
        vip_st = "Evet 💎" if u_info.get("vip") else "Hayır"
        await query.message.reply_text(f"👤 **Profil Bilgileriniz:**\n\n• **Ad:** {u_info.get('name')}\n• **Kullanıcı Adı:** {u_info.get('username')}\n• **ID:** `{user_id}`\n• **VIP:** {vip_st}", parse_mode="Markdown")
    elif data == "vip_fiyatlar":
        await query.message.reply_text("💎 **VIP Üyelik Fiyatları:**\n\n• 1 Aylık VIP: 1250₺\n\nSatın almak için yönetici ile iletişime geçiniz.", parse_mode="Markdown")


# ==========================================
# 8. METİN GİRDİLERİ (ADMIN İŞLEMLERİ)
# ==========================================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    db = verileri_yukle()
    
    # Beklenen Admin İşlemi Var mı?
    if user_id == ADMIN_ID and "beklenen_islem" in context.user_data:
        islem = context.user_data.pop("beklenen_islem")

        if islem == "vip_ver":
            if text in db["users"]:
                db["users"][text]["vip"] = True
                verileri_kaydet(db)
                await update.message.reply_text(f"✅ `{text}` ID'li kullanıcı **VIP** yapıldı!", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ Bu kullanıcı veritabanında bulunamadı.")

        elif islem == "vip_kaldir":
            if text in db["users"]:
                db["users"][text]["vip"] = False
                verileri_kaydet(db)
                await update.message.reply_text(f"✅ `{text}` ID'li kullanıcının VIP üyeliği kaldırıldı.", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ Bu kullanıcı veritabanında bulunamadı.")

        elif islem == "kanal_ekle":
            if not text.startswith("@"): text = "@" + text
            if text not in db["zorunlu_kanallar"]:
                db["zorunlu_kanallar"].append(text)
                verileri_kaydet(db)
                await update.message.reply_text(f"✅ `{text}` zorunlu kanallara eklendi!", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Bu kanal zaten listede var.")

        elif islem == "kanal_sil":
            if not text.startswith("@"): text = "@" + text
            if text in db["zorunlu_kanallar"]:
                db["zorunlu_kanallar"].remove(text)
                verileri_kaydet(db)
                await update.message.reply_text(f"✅ `{text}` zorunlu kanallardan silindi!", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ Bu kanal listede bulunamadı.")

        elif islem == "ban_yonet":
            if text in db["banned_users"]:
                db["banned_users"].remove(text)
                verileri_kaydet(db)
                await update.message.reply_text(f"🟢 `{text}` ID'li kullanıcının banı kaldırıldı.", parse_mode="Markdown")
            else:
                db["banned_users"].append(text)
                verileri_kaydet(db)
                await update.message.reply_text(f"⛔️ `{text}` ID'li kullanıcı engellendi (Banlandı).", parse_mode="Markdown")

        elif islem == "duyuru_gonder":
            basarili = 0
            for uid in db.get("users", {}):
                try:
                    await context.bot.send_message(chat_id=int(uid), text=f"📢 **DUYURU:**\n\n{text}", parse_mode="Markdown")
                    basarili += 1
                except Exception:
                    continue
            await update.message.reply_text(f"✅ Duyuru `{basarili}` kullanıcıya iletildi!", parse_mode="Markdown")

        return


# ==========================================
# 9. BOTU BAŞLAT
# ==========================================
if __name__ == '__main__':
    keep_alive()
    
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("panel", panel_komutu))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))

    print("AraştırX Panel Botu Aktif!")
    bot_app.run_polling()
