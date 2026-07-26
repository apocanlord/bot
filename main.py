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
    ContextTypes
)

# ==========================================
# 1. RENDER KEEPALIVE (PORT SUNUCUSU)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "AraştırX Bot 7/24 Aktif ve Çalışıyor!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()


# ==========================================
# 2. SABİT AYARLAR & BİLGİLERİN
# ==========================================
BOT_TOKEN = "8646358320:AAEj6rlEpCxX1aLOXspgbsTNpVaYtvvGrbE"
ADMIN_ID = 6073294253
LOG_KANAL_ID = -1004400643128
GUNLUK_UCRETSIZ_LIMIT = 3
VERI_DOSYASI = "database.json"


# ==========================================
# 3. VERİTABANI YÖNETİMİ (JSON)
# ==========================================
def verileri_yukle():
    if not os.path.exists(VERI_DOSYASI):
        default_data = {
            "users": {},
            "duyuru_metni": None,
            "duyuru_aktif": False,
            "bakim_modu": False,
            "zorunlu_kanallar": ["@arastirzorunlu", "@arastirduyuru"]
        }
        verileri_kaydet(default_data)
        return default_data
    with open(VERI_DOSYASI, "r", encoding="utf-8") as f:
        data = json.load(f)
        # Eksik anahtarlar varsa varsayılan koy
        if "bakim_modu" not in data:
            data["bakim_modu"] = False
        if "zorunlu_kanallar" not in data:
            data["zorunlu_kanallar"] = ["@arastirzorunlu", "@arastirduyuru"]
        return data

def verileri_kaydet(data):
    with open(VERI_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def kullanici_kontrol_ve_guncelle(user):
    data = verileri_yukle()
    s_id = str(user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    username = f"@{user.username}" if user.username else "Yok"
    
    if s_id not in data["users"]:
        data["users"][s_id] = {
            "name": user.first_name or "Kullanıcı",
            "username": username,
            "vip": False,
            "hak": GUNLUK_UCRETSIZ_LIMIT,
            "son_tarih": today
        }
    else:
        # Kullanıcı adı veya isim değiştiyse güncelle
        data["users"][s_id]["name"] = user.first_name or "Kullanıcı"
        data["users"][s_id]["username"] = username
        
        # Gün değiştiyse ücretsiz hakları yenile
        if data["users"][s_id]["son_tarih"] != today:
            data["users"][s_id]["hak"] = GUNLUK_UCRETSIZ_LIMIT
            data["users"][s_id]["son_tarih"] = today
            
    verileri_kaydet(data)
    return data["users"][s_id]


# ==========================================
# 4. LOG KANALINA BİLDİRİM GÖNDERİCİ
# ==========================================
async def log_gonder(bot, mesaj):
    try:
        await bot.send_message(chat_id=LOG_KANAL_ID, text=mesaj, parse_mode="Markdown")
    except Exception as e:
        print(f"Log Gönderim Hatası: {e}")


# ==========================================
# 5. ZORUNLU KANAL KONTROLÜ (ÇOKLU KANAL)
# ==========================================
async def katilinmayan_kanallari_getir(bot, user_id):
    db = verileri_yukle()
    kanallar = db.get("zorunlu_kanallar", [])
    katilinmayanlar = []
    
    for kanal in kanallar:
        try:
            member = await bot.get_chat_member(chat_id=kanal, user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                katilinmayanlar.append(kanal)
        except Exception as e:
            print(f"Kanal kontrol hatası ({kanal}): {e}")
            # Kanal bulunamazsa veya yetki yoksa es geç
            continue
            
    return katilinmayanlar


# ==========================================
# 6. MENÜLER VE ANA KOMUTLAR
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = verileri_yukle()
    user_data = kullanici_kontrol_ve_guncelle(user)
    
    # Bakım Modu Kontrolü
    if db.get("bakim_modu") and user.id != ADMIN_ID:
        msg = "🛠 **BOT BAKIMDADIR!**\n\nBot şu anda bakımdadır. Lütfen daha sonra tekrar deneyiniz."
        if update.message:
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.callback_query.message.edit_text(msg, parse_mode="Markdown")
        return

    # Yeni Başlatanı Logla
    if update.message:
        username_str = f" (@{user.username})" if user.username else ""
        await log_gonder(context.bot, f"👤 **Yeni Başlatma:**\n• Kullanıcı: {user.first_name}{username_str}\n• ID: `{user.id}`")

    # Zorunlu Kanal Kontrolü
    katilinmayanlar = await katilinmayan_kanallari_getir(context.bot, user.id)
    if katilinmayanlar and user.id != ADMIN_ID:
        keyboard = []
        for k in katilinmayanlar:
            clean_k = k.replace('@', '')
            keyboard.append([InlineKeyboardButton(f"📢 {k} Kanalına Katıl", url=f"https://t.me/{clean_k}")])
        keyboard.append([InlineKeyboardButton("✅ Katıldım, Kontrol Et", callback_data="kanal_kontrol")])
        
        msg = (
            f"⚠️ **AraştırX | Analiz Botunu Kullanabilmek İçin Aşağıdaki Kanallara Katılmalısınız!**\n\n"
            f"Lütfen tüm kanallara katıldıktan sonra **Katıldım, Kontrol Et** butonuna basınız."
        )
        if update.message:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await update.callback_query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    duyuru_ek = ""
    if db.get("duyuru_aktif") and db.get("duyuru_metni"):
        duyuru_ek = f"\n📢 **DUYURU:** {db['duyuru_metni']}\n\n"

    durum_metni = "✨ **VIP Üye** (Sınırsız)" if user_data["vip"] else f"👤 **Standart Üye** (Kalan Hak: {user_data['hak']})"
    
    mesaj = (
        f"🔍 **AraştırX | Analiz Botuna Hoş Geldiniz!**\n"
        f"{duyuru_ek}"
        f"Üyelik Durumunuz: {durum_metni}\n\n"
        f"Lütfen yapmak istediğiniz sorgu/analiz türünü seçin:"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 Genel Analiz & Sorgu", callback_data="sorgu_genel"), InlineKeyboardButton("🔍 Hızlı Profil Sorgu", callback_data="sorgu_profil")],
        [InlineKeyboardButton("💎 VIP Üyelik Satın Al", callback_data="vip_bilgi")],
        [InlineKeyboardButton("⚙️ Hesabım & Kalan Haklarım", callback_data="hesap_durum")]
    ]
    
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 Yönetici Paneli", callback_data="admin_panel")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(mesaj, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(mesaj, reply_markup=reply_markup, parse_mode="Markdown")


# ==========================================
# 7. YÖNETİCİ PANELİ (/panel)
# ==========================================
async def panel_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komutu sadece bot yöneticisi kullanabilir.")
        return
    await admin_panel_goster(update, context)

async def admin_panel_goster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = verileri_yukle()
    toplam_kullanici = len(db["users"])
    vip_sayisi = sum(1 for u in db["users"].values() if u.get("vip"))
    duyuru_durum = "🟢 Aktif" if db.get("duyuru_aktif") else "🔴 Pasif"
    bakim_durum = "🔴 AKTİF (Bakımda)" if db.get("bakim_modu") else "🟢 PASİF (Açık)"
    kanallar_str = ", ".join(db.get("zorunlu_kanallar", [])) or "Yok"
    
    mesaj = (
        f"👑 **YÖNETİCİ PANELİ**\n\n"
        f"👥 **Toplam Kullanıcı:** `{toplam_kullanici}`\n"
        f"💎 **VIP Kullanıcı:** `{vip_sayisi}`\n"
        f"🛠 **Bakım Modu:** {bakim_durum}\n"
        f"📢 **Duyuru Durumu:** {duyuru_durum}\n"
        f"📢 **Zorunlu Kanallar:** {kanallar_str}\n\n"
        f"Yapmak istediğiniz işlemi seçin:"
    )
    
    bakim_btn_text = "🟢 Bakım Modunu Kapat" if db.get("bakim_modu") else "🛠 Bakım Modunu Aç"
    
    keyboard = [
        [InlineKeyboardButton("👥 Tüm Kullanıcılar (ID/Username)", callback_data="adm_kullanicilar")],
        [InlineKeyboardButton(bakim_btn_text, callback_data="adm_bakim_toggle"), InlineKeyboardButton("🔄 Paneli Yenile", callback_data="admin_panel")],
        [InlineKeyboardButton("➕ VIP Ekle/Çıkar", callback_data="adm_vip_yonet"), InlineKeyboardButton("📢 Kanal Ekle/Çıkar", callback_data="adm_kanal_yonet")],
        [InlineKeyboardButton("📢 Duyuru Yap", callback_data="adm_duyuru_yap"), InlineKeyboardButton("🚫 Duyuru İptal", callback_data="adm_duyuru_iptal")],
        [InlineKeyboardButton("◀️ Ana Menüye Dön", callback_data="ana_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(mesaj, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(mesaj, reply_markup=reply_markup, parse_mode="Markdown")


# ==========================================
# 8. BUTON VE ETKİLEŞİM İŞLEYİCİSİ
# ==========================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    db = verileri_yukle()
    user_data = kullanici_kontrol_ve_guncelle(query.from_user)
    
    if data == "kanal_kontrol" or data == "ana_menu":
        await start(update, context)
        return

    # Bakım Engeli (Admin Hariç)
    if db.get("bakim_modu") and user_id != ADMIN_ID:
        await query.message.edit_text("🛠 **BOT BAKIMDADIR!**\n\nBot şu anda bakımdadır. Lütfen daha sonra tekrar deneyiniz.", parse_mode="Markdown")
        return

    # --- SORGU BUTONLARI ---
    if data in ["sorgu_genel", "sorgu_profil"]:
        if not user_data["vip"] and user_data["hak"] <= 0:
            text = (
                "❌ **Ücretsiz Günlük Limitiniz Doldu!**\n\n"
                "Bugünkü sorgu haklarınızı tükettiniz. Gece 00:00'da haklarınız yenilenecektir.\n"
                "Sınırsız kullanım için VIP üyelik alabilirsiniz."
            )
            keyboard = [[InlineKeyboardButton("💎 VIP Al", callback_data="vip_bilgi"), InlineKeyboardButton("◀️ Menü", callback_data="ana_menu")]]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
            
        if not user_data["vip"]:
            db["users"][str(user_id)]["hak"] -= 1
            verileri_kaydet(db)
            
        kalan_hak = "Sınırsız (VIP)" if user_data["vip"] else f"{db['users'][str(user_id)]['hak']} Hak Kaldı"
        sorgu_turu = "Genel Analiz" if data == "sorgu_genel" else "Hızlı Profil Sorgu"
        
        # Log Gönder
        username_str = f" (@{query.from_user.username})" if query.from_user.username else ""
        await log_gonder(context.bot, f"🔎 **Sorgu Tıklandı:**\n• Kullanıcı: {query.from_user.first_name}{username_str}\n• ID: `{user_id}`\n• Tür: {sorgu_turu}")

        text = (
            f"✅ **{sorgu_turu} Başlatıldı!**\n\n"
            f"🔍 Sorgulamak istediğiniz veriyi veya kullanıcı adını mesaja yazıp gönderin.\n\n"
            f"📊 **Kalan Hak:** `{kalan_hak}`"
        )
        keyboard = [[InlineKeyboardButton("◀️ Ana Menüye Dön", callback_data="ana_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # --- HESAP DURUMU ---
    elif data == "hesap_durum":
        durum = "✨ VIP Üye (Sınırsız)" if user_data["vip"] else f"👤 Standart Üye ({user_data['hak']}/{GUNLUK_UCRETSIZ_LIMIT} Hak)"
        username_str = f"@{query.from_user.username}" if query.from_user.username else "Yok"
        text = (
            f"👤 **Kullanıcı:** {query.from_user.first_name}\n"
            f"🏷 **Kullanıcı Adı:** {username_str}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"📊 **Üyelik Tipi:** {durum}\n"
            f"📅 **Son Yenilenme:** {user_data['son_tarih']}"
        )
        keyboard = [[InlineKeyboardButton("◀️ Ana Menüye Dön", callback_data="ana_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # --- VIP BİLGİ ---
    elif data == "vip_bilgi":
        text = (
            "💎 **AraştırX VIP Üyelik Ayrıcalıkları**\n\n"
            "• Sınırsız Sorgu ve Analiz Hakkı\n"
            "• Günlük Limit Engeline Takılmama\n"
            "• 7/24 Öncelikli Yüksek Hızlı Sunucu\n\n"
            "VIP üyelik satın almak için yönetici ile iletişime geçin."
        )
        keyboard = [[InlineKeyboardButton("◀️ Ana Menüye Dön", callback_data="ana_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # --- ADMIN İŞLEMLERİ ---
    elif data == "admin_panel" and user_id == ADMIN_ID:
        await admin_panel_goster(update, context)

    elif data == "adm_bakim_toggle" and user_id == ADMIN_ID:
        db["bakim_modu"] = not db.get("bakim_modu", False)
        verileri_kaydet(db)
        durum = "AÇILDI (Bakımdadır)" if db["bakim_modu"] else "KAPATILDI (Kullanıma Açık)"
        await log_gonder(context.bot, f"🛠 **Bakım Modu {durum}!**")
        await admin_panel_goster(update, context)

    elif data == "adm_kullanicilar" and user_id == ADMIN_ID:
        kullanicilar = db["users"]
        liste_metni = f"👥 **TÜM KULLANICILAR LİSTESİ ({len(kullanicilar)} Kişi)**\n\n"
        
        count = 0
        for uid, uinfo in kullanicilar.items():
            count += 1
            v_durum = "💎 VIP" if uinfo.get("vip") else "👤 Standart"
            uname = uinfo.get('username', 'Yok')
            name = uinfo.get('name', 'Kullanıcı')
            liste_metni += f"{count}. {name} | {uname}\n   └ ID: `{uid}` - Status: {v_durum}\n"
            if count >= 30: # Mesaj boyut sınırı için
                liste_metni += "\n*(Sadece son 30 kullanıcı listelendi)*"
                break
        
        keyboard = [[InlineKeyboardButton("🔄 Yenile", callback_data="adm_kullanicilar"), InlineKeyboardButton("◀️ Panele Dön", callback_data="admin_panel")]]
        await query.message.edit_text(liste_metni, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "adm_vip_yonet" and user_id == ADMIN_ID:
        text = (
            "➕/➖ **VIP EKLE / ÇIKAR**\n\n"
            "Kullanıcıya VIP vermek veya VIP'sini almak için sohbet alanına şu komutları yazabilirsiniz:\n\n"
            "👉 VIP Ekleme: `/vipekle ID`\n"
            "👉 VIP Çıkarma: `/vipsil ID`"
        )
        keyboard = [[InlineKeyboardButton("◀️ Panele Dön", callback_data="admin_panel")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "adm_kanal_yonet" and user_id == ADMIN_ID:
        kanallar = ", ".join(db.get("zorunlu_kanallar", [])) or "Yok"
        text = (
            f"📢 **ZORUNLU KANAL YÖNETİMİ**\n\n"
            f"Mevcut Kanallar: {kanallar}\n\n"
            f"Kanal eklemek veya çıkarmak için şu komutları kullanabilirsiniz:\n\n"
            f"👉 Kanal Ekle: `/kanalekle @kanaladi`\n"
            f"👉 Kanal Çıkar: `/kanalsil @kanaladi`"
        )
        keyboard = [[InlineKeyboardButton("◀️ Panele Dön", callback_data="admin_panel")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "adm_duyuru_yap" and user_id == ADMIN_ID:
        text = (
            "📢 **DUYURU YAYINLAMA**\n\n"
            "Tüm kullanıcılara gösterilecek duyuru metnini ayarlamak için şu komutu yazın:\n\n"
            "👉 `/duyuru Buraya duyuru metnini yazın`"
        )
        keyboard = [[InlineKeyboardButton("◀️ Panele Dön", callback_data="admin_panel")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "adm_duyuru_iptal" and user_id == ADMIN_ID:
        db["duyuru_aktif"] = False
        db["duyuru_metni"] = None
        verileri_kaydet(db)
        await log_gonder(context.bot, "🚫 **Yönetici Duyuruyu İptal Etti.**")
        text = "✅ **Duyuru başarıyla kaldırıldı ve pasife alındı.**"
        keyboard = [[InlineKeyboardButton("◀️ Panele Dön", callback_data="admin_panel")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


# ==========================================
# 9. ADMIN KOMUTLARI
# ==========================================
async def vip_ekle_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        hedef_id = str(context.args[0])
        db = verileri_yukle()
        if hedef_id in db["users"]:
            db["users"][hedef_id]["vip"] = True
            verileri_kaydet(db)
            await log_gonder(context.bot, f"✨ **VIP Eklendi:**\n• Kullanıcı ID: `{hedef_id}`")
            await update.message.reply_text(f"✅ `{hedef_id}` ID'li kullanıcı başarıyla **VIP** yapıldı!", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Bu kullanıcı veritabanında bulunamadı.")
    except IndexError:
        await update.message.reply_text("⚠️ Kullanım: `/vipekle KULLANICI_ID`", parse_mode="Markdown")

async def vip_sil_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        hedef_id = str(context.args[0])
        db = verileri_yukle()
        if hedef_id in db["users"]:
            db["users"][hedef_id]["vip"] = False
            verileri_kaydet(db)
            await log_gonder(context.bot, f"🔻 **VIP Kaldırıldı:**\n• Kullanıcı ID: `{hedef_id}`")
            await update.message.reply_text(f"✅ `{hedef_id}` ID'li kullanıcının VIP üyeliği kaldırıldı.", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Bu kullanıcı veritabanında bulunamadı.")
    except IndexError:
        await update.message.reply_text("⚠️ Kullanım: `/vipsil KULLANICI_ID`", parse_mode="Markdown")

async def kanal_ekle_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        kanal = context.args[0]
        if not kanal.startswith("@"):
            kanal = "@" + kanal
        db = verileri_yukle()
        if kanal not in db["zorunlu_kanallar"]:
            db["zorunlu_kanallar"].append(kanal)
            verileri_kaydet(db)
            await log_gonder(context.bot, f"📢 **Yeni Zorunlu Kanal Eklendi:** {kanal}")
            await update.message.reply_text(f"✅ `{kanal}` zorunlu kanallara eklendi!", parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ Bu kanal zaten listede var.")
    except IndexError:
        await update.message.reply_text("⚠️ Kullanım: `/kanalekle @kanaladi`", parse_mode="Markdown")

async def kanal_sil_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        kanal = context.args[0]
        if not kanal.startswith("@"):
            kanal = "@" + kanal
        db = verileri_yukle()
        if kanal in db["zorunlu_kanallar"]:
            db["zorunlu_kanallar"].remove(kanal)
            verileri_kaydet(db)
            await log_gonder(context.bot, f"🚫 **Zorunlu Kanal Kaldırıldı:** {kanal}")
            await update.message.reply_text(f"✅ `{kanal}` zorunlu kanallardan çıkarıldı!", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Bu kanal listede bulunamadı.")
    except IndexError:
        await update.message.reply_text("⚠️ Kullanım: `/kanalsil @kanaladi`", parse_mode="Markdown")

async def duyuru_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    metin = " ".join(context.args)
    if not metin:
        await update.message.reply_text("⚠️ Kullanım: `/duyuru Mesajınız...`", parse_mode="Markdown")
        return
    db = verileri_yukle()
    db["duyuru_metni"] = metin
    db["duyuru_aktif"] = True
    verileri_kaydet(db)
    await log_gonder(context.bot, f"📢 **Yeni Duyuru Yayınlandı:**\n{metin}")
    await update.message.reply_text(f"📢 **Duyuru Yayınlandı:**\n\n{metin}", parse_mode="Markdown")


# ==========================================
# 10. BOTU BAŞLATMA
# ==========================================
if __name__ == '__main__':
    # Render web portunu aç (Render kapanmama garantisi)
    keep_alive()
    
    # Telegram Bot Kurulumu
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("panel", panel_komutu))
    bot_app.add_handler(CommandHandler("vipekle", vip_ekle_komut))
    bot_app.add_handler(CommandHandler("vipsil", vip_sil_komut))
    bot_app.add_handler(CommandHandler("kanalekle", kanal_ekle_komut))
    bot_app.add_handler(CommandHandler("kanalsil", kanal_sil_komut))
    bot_app.add_handler(CommandHandler("duyuru", duyuru_komut))
    bot_app.add_handler(CallbackQueryHandler(button_handler))

    print("AraştırX Bot Tam Sürüm Başarıyla Çalıştırıldı!")
    bot_app.run_polling()
