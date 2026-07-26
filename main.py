import os
import json
import threading
import html
import aiohttp
from datetime import datetime, timedelta
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
# 2. SABİT AYARLAR & YAPILANDIRMA
# ==========================================
BOT_TOKEN = "8646358320:AAEj6rlEpCxX1aLOXspgbsTNpVaYtvvGrbE"
ADMIN_ID = 6073294253
VERI_DOSYASI = "database.json"
API_BASE_URL = "http://arastir.vip/api"
GUNLUK_UCRETSIZ_LIMIT = 7


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
        if "banned_users" not in data: data["banned_users"] = []
        if "bugun_gelen" not in data: data["bugun_gelen"] = 0
        if "son_bugun_tarih" not in data: data["son_bugun_tarih"] = datetime.now().strftime("%Y-%m-%d")
        if "bakim_modu" not in data: data["bakim_modu"] = False
        if "kanal_sarti" not in data: data["kanal_sarti"] = True
        if "zorunlu_kanallar" not in data: data["zorunlu_kanallar"] = ["@arastirduyuru", "@arastirzorunlu"]
        
        today = datetime.now().strftime("%Y-%m-%d")
        if data.get("son_bugun_tarih") != today:
            data["bugun_gelen"] = 0
            data["son_bugun_tarih"] = today
            # Günlük sorgu haklarını sıfırla
            for u in data.get("users", {}).values():
                u["gunluk_sorgu"] = 0
            verileri_kaydet(data)
            
        return data

def verileri_kaydet(data):
    with open(VERI_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def kullanici_kaydet_ve_guncelle(user, referrer_id=None):
    db = verileri_yukle()
    s_id = str(user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    username = f"@{user.username}" if user.username else "Yok"
    yeni_kayit = False
    
    if s_id not in db["users"]:
        yeni_kayit = True
        db["users"][s_id] = {
            "name": user.first_name or "Kullanıcı",
            "username": username,
            "vip": False,
            "vip_bitis": None,
            "katilma_tarihi": today,
            "gunluk_sorgu": 0,
            "davet_sayisi": 0,
            "invited_by": str(referrer_id) if referrer_id and str(referrer_id) != s_id else None
        }
        db["bugun_gelen"] = db.get("bugun_gelen", 0) + 1

        # Referans/Davet Kontrolü
        if referrer_id and str(referrer_id) in db["users"] and str(referrer_id) != s_id:
            ref_user = db["users"][str(referrer_id)]
            ref_user["davet_sayisi"] = ref_user.get("davet_sayisi", 0) + 1
            
            # 10 Davete 3 Gün VIP Ödülü
            if ref_user["davet_sayisi"] % 10 == 0:
                ref_user["vip"] = True
                suan = datetime.now()
                if ref_user.get("vip_bitis"):
                    try:
                        mevcut_bitis = datetime.strptime(ref_user["vip_bitis"], "%Y-%m-%d %H:%M")
                        if mevcut_bitis > suan:
                            suan = mevcut_bitis
                    except Exception:
                        pass
                yeni_bitis = suan + timedelta(days=3)
                ref_user["vip_bitis"] = yeni_bitis.strftime("%Y-%m-%d %H:%M")
    else:
        db["users"][s_id]["name"] = user.first_name or "Kullanıcı"
        db["users"][s_id]["username"] = username
        if "gunluk_sorgu" not in db["users"][s_id]: db["users"][s_id]["gunluk_sorgu"] = 0
        if "davet_sayisi" not in db["users"][s_id]: db["users"][s_id]["davet_sayisi"] = 0

    # Süreli VIP Kontrolü
    u = db["users"][s_id]
    if u.get("vip") and u.get("vip_bitis"):
        try:
            bitis = datetime.strptime(u["vip_bitis"], "%Y-%m-%d %H:%M")
            if datetime.now() > bitis:
                u["vip"] = False
                u["vip_bitis"] = None
        except Exception:
            pass

    verileri_kaydet(db)
    return db["users"][s_id], yeni_kayit


# ==========================================
# 4. UZUN MESAJ BÖLÜCÜ & API SÜRÜCÜSÜ
# ==========================================
async def guvenli_html_mesaj_gonder(update_or_msg, text: str):
    """HTML içeriklerini Telegram'ın 4096 karakter sınırına takılmadan parçalayarak gönderir."""
    MAX_LEN = 3800
    if len(text) <= MAX_LEN:
        if hasattr(update_or_msg, 'reply_text'):
            await update_or_msg.reply_text(text, parse_mode="HTML")
        else:
            await update_or_msg.send_message(text, parse_mode="HTML")
        return

    parcalar = [text[i:i+MAX_LEN] for i in range(0, len(text), MAX_LEN)]
    for p in parcalar:
        if hasattr(update_or_msg, 'reply_text'):
            await update_or_msg.reply_text(p, parse_mode="HTML")
        else:
            await update_or_msg.send_message(p, parse_mode="HTML")

async def api_istek_at(endpoint: str, params: dict):
    url = f"{API_BASE_URL}/{endpoint}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=12) as response:
                if response.status == 200:
                    data = await response.json()
                    return True, data
                else:
                    return False, f"API Hatası (HTTP {response.status})"
    except Exception as e:
        return False, f"Sunucu Bağlantı Hatası: {str(e)}"

def format_api_response_html(sorgu_turu: str, res: dict) -> str:
    if not res.get("success"):
        err = html.escape(str(res.get('error', 'Sonuç bulunamadı veya işlem başarısız.')))
        return f"❌ <b>Hata:</b> {err}"

    data = res.get("data")
    if not data:
        return "❌ <b>Kayıt bulunamadı.</b>"

    # 1. TC SORGU
    if sorgu_turu == "sorgu_tc":
        return (
            f"🖨 <b>TC Kimlik Sorgu Sonucu</b>\n\n"
            f"• <b>TC:</b> <code>{html.escape(str(data.get('TC', '-')))}</code>\n"
            f"• <b>Ad Soyad:</b> {html.escape(str(data.get('ADI', '-')))} {html.escape(str(data.get('SOYADI', '-')))}\n"
            f"• <b>Doğum Tarihi:</b> {html.escape(str(data.get('DOGUMTARIHI', '-')))}\n"
            f"• <b>Nüfus İl / İlçe:</b> {html.escape(str(data.get('NUFUSIL', '-')))} / {html.escape(str(data.get('NUFUSILCE', '-')))}\n"
            f"• <b>Anne Adı / TC:</b> {html.escape(str(data.get('ANNEADI', '-')))} (<code>{html.escape(str(data.get('ANNETC', '-')))}</code>)\n"
            f"• <b>Baba Adı / TC:</b> {html.escape(str(data.get('BABAADI', '-')))} (<code>{html.escape(str(data.get('BABATC', '-')))}</code>)\n"
            f"• <b>Uyruk:</b> {html.escape(str(data.get('UYRUK', '-')))}"
        )

    # 2. AD SOYAD SORGU
    elif sorgu_turu == "sorgu_adsoyad":
        count = res.get("count", len(data))
        out = f"👤 <b>Ad Soyad Sorgu Sonuçları</b> ({count} Kayıt):\n\n"
        for idx, item in enumerate(data, 1):
            out += f"<b>{idx}.</b> <code>{html.escape(str(item.get('TC')))}</code> | {html.escape(str(item.get('ADI')))} {html.escape(str(item.get('SOYADI')))} | DT: {html.escape(str(item.get('DOGUMTARIHI')))}\n"
        return out

    # 3. AİLE SORGU
    elif sorgu_turu == "sorgu_aile":
        anne = data.get("anne", {})
        baba = data.get("baba", {})
        kardesler = data.get("kardesler", [])
        
        out = f"👥 <b>Aile Sorgu Sonucu</b>\n\n"
        out += f"👩 <b>Anne:</b> {html.escape(str(anne.get('ADI', '-')))} {html.escape(str(anne.get('SOYADI', '')))} (<code>{html.escape(str(anne.get('TC', '-')))}</code>)\n"
        out += f"👨 <b>Baba:</b> {html.escape(str(baba.get('ADI', '-')))} {html.escape(str(baba.get('SOYADI', '')))} (<code>{html.escape(str(baba.get('TC', '-')))}</code>)\n\n"
        out += f"👶 <b>Kardeşler ({len(kardesler)}):</b>\n"
        for k in kardesler:
            out += f"• <code>{html.escape(str(k.get('TC')))}</code> - {html.escape(str(k.get('ADI')))} {html.escape(str(k.get('SOYADI')))}\n"
        return out

    # 4. SÜLALE SORGU
    elif sorgu_turu == "sorgu_sulale":
        kendisi = data.get("kendisi", {})
        anne = data.get("anne", {})
        baba = data.get("baba", {})
        anneanne = data.get("anneanne", {})
        dede_a = data.get("dede_anne_tarafi", {})
        babaanne = data.get("babaanne", {})
        dede_b = data.get("dede_baba_tarafi", {})
        
        return (
            f"👥 <b>Sülale Sorgu Sonucu</b>\n\n"
            f"👤 <b>Kendisi:</b> {html.escape(str(kendisi.get('ADI', '-')))} (<code>{html.escape(str(kendisi.get('TC', '-')))}</code>)\n"
            f"👩 <b>Anne:</b> {html.escape(str(anne.get('ADI', '-')))} (<code>{html.escape(str(anne.get('TC', '-')))}</code>)\n"
            f"👨 <b>Baba:</b> {html.escape(str(baba.get('ADI', '-')))} (<code>{html.escape(str(baba.get('TC', '-')))}</code>)\n"
            f"👵 <b>Anneanne:</b> {html.escape(str(anneanne.get('ADI', '-')))} (<code>{html.escape(str(anneanne.get('TC', '-')))}</code>)\n"
            f"👴 <b>Dede (Anne T.):</b> {html.escape(str(dede_a.get('ADI', '-')))} (<code>{html.escape(str(dede_a.get('TC', '-')))}</code>)\n"
            f"👵 <b>Babaanne:</b> {html.escape(str(babaanne.get('ADI', '-')))} (<code>{html.escape(str(babaanne.get('TC', '-')))}</code>)\n"
            f"👴 <b>Dede (Baba T.):</b> {html.escape(str(dede_b.get('ADI', '-')))} (<code>{html.escape(str(dede_b.get('TC', '-')))}</code>)"
        )

    # 5. ÇOCUK SORGU
    elif sorgu_turu == "sorgu_cocuk":
        count = res.get("count", len(data))
        out = f"👶 <b>Çocuk Sorgu Sonuçları</b> ({count} Kayıt):\n\n"
        for item in data:
            out += f"• <code>{html.escape(str(item.get('TC')))}</code> | {html.escape(str(item.get('ADI')))} {html.escape(str(item.get('SOYADI')))} | DT: {html.escape(str(item.get('DOGUMTARIHI')))}\n"
        return out

    # 6. ADRES SORGU
    elif sorgu_turu == "sorgu_adres":
        return (
            f"📍 <b>Adres & İkametgah Bilgisi</b>\n\n"
            f"• <b>TC:</b> <code>{html.escape(str(data.get('KimlikNo', '-')))}</code>\n"
            f"• <b>Ad Soyad:</b> {html.escape(str(data.get('AdSoyad', '-')))}\n"
            f"• <b>Doğum Yeri:</b> {html.escape(str(data.get('DogumYeri', '-')))}\n"
            f"• <b>Vergi No:</b> {html.escape(str(data.get('VergiNumarasi', '-')))}\n"
            f"• <b>İkametgah:</b> {html.escape(str(data.get('Ikametgah', '-')))}"
        )

    # 7. GSM -> TC
    elif sorgu_turu == "sorgu_gsmtc":
        tcleri = "\n".join([f"• <code>{html.escape(str(tc))}</code>" for tc in data])
        return f"📱 <b>GSM → TC Sorgu Sonucu</b>\n\n{tcleri}"

    # 8. TC -> GSM
    elif sorgu_turu == "sorgu_tcgsm":
        gsmleri = "\n".join([f"• <code>{html.escape(str(gsm))}</code>" for gsm in data])
        return f"📱 <b>TC → GSM Sorgu Sonucu</b>\n\n{gsmleri}"

    # 9. İŞYERİ SORGU
    elif sorgu_turu == "sorgu_isyeri":
        out = f"🏢 <b>İşyeri & SGK Bilgileri</b> ({res.get('count', len(data))} Kayıt):\n\n"
        for item in data:
            out += (
                f"• <b>Çalışan:</b> {html.escape(str(item.get('calisanAdSoyad')))}\n"
                f"• <b>İşyeri Ünvanı:</b> {html.escape(str(item.get('isyeriUnvani')))}\n"
                f"• <b>SGK Sicil No:</b> <code>{html.escape(str(item.get('isyeriSgkSicilNo')))}</code>\n"
                f"• <b>İşe Giriş Tarihi:</b> {html.escape(str(item.get('iseGirisTarihi')))}\n"
                f"• <b>Sektör:</b> {html.escape(str(item.get('isyeriSektoru')))}\n"
                f"• <b>Durum:</b> {html.escape(str(item.get('calismaDurumu')))}\n"
                f"────────────────────────\n"
            )
        return out

    return "⚠️ Bilinmeyen sorgu formatı."


# ==========================================
# 5. KANAL KATILIM KONTROLÜ
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
# 6. KULLANICI ANA MENÜSÜ (/start)
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = verileri_yukle()
    s_id = str(user.id)
    
    # Referans (Davet) Parametresi Yakalama
    ref_id = None
    if context.args and len(context.args) > 0:
        ref_id = context.args[0]

    if s_id in db.get("banned_users", []):
        msg = "❌ <b>Bot kullanımınız engellenmiştir (Banlandınız).</b>"
        if update.message: await update.message.reply_text(msg, parse_mode="HTML")
        return

    if db.get("bakim_modu") and user.id != ADMIN_ID:
        msg = "⚙️ <b>Bot şu an bakım modundadır. Lütfen daha sonra tekrar deneyiniz.</b>"
        if update.message: await update.message.reply_text(msg, parse_mode="HTML")
        return

    u_info, _ = kullanici_kaydet_ve_guncelle(user, ref_id)

    katildi, eksikler = await kanallara_katildi_mi(context.bot, user.id)
    if not katildi:
        keyboard = []
        for k in eksikler:
            clean_k = k.replace('@', '')
            keyboard.append([InlineKeyboardButton(f"📢 {k} Kanalına Katıl", url=f"https://t.me/{clean_k}")])
        keyboard.append([InlineKeyboardButton("✅ Katıldım, Kontrol Et", callback_data="kanal_kontrol")])
        
        msg = "⚠️ <b>Botu kullanabilmek için lütfen aşağıdaki zorunlu kanallara katılın:</b>"
        if update.message:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        else:
            await update.callback_query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    # Hak Hesabı
    if u_info.get("vip") or user.id == ADMIN_ID:
        hak_text = "Sınırsız ∞ (VIP)"
    else:
        kullanilan = u_info.get("gunluk_sorgu", 0)
        kalan = max(0, GUNLUK_UCRETSIZ_LIMIT - kullanilan)
        hak_text = f"{kalan} / {GUNLUK_UCRETSIZ_LIMIT}"

    mesaj = (
        f"🔍 <b>AraştırX | Analiz Botu</b> Paneline Hoş Geldiniz!\n\n"
        f"📊 <b>Günlük Kalan Sorgu Hakkınız:</b> {hak_text}\n"
        f"👑 <b>Yönetici İletişim:</b> @danistay\n\n"
        f"İşlem yapmak için aşağıdaki menüden bir kategori seçin:"
    )

    keyboard = [
        [InlineKeyboardButton("👤 Ad Soyad Sorgula", callback_data="sorgu_adsoyad"), InlineKeyboardButton("🖨 TC Sorgula", callback_data="sorgu_tc")],
        [InlineKeyboardButton("🏢 İşyeri Sorgula", callback_data="sorgu_isyeri"), InlineKeyboardButton("📍 Adres Sorgula", callback_data="sorgu_adres")],
        [InlineKeyboardButton("👥 Aile Sorgula", callback_data="sorgu_aile"), InlineKeyboardButton("👥 Sülale Sorgula", callback_data="sorgu_sulale")],
        [InlineKeyboardButton("👶 Çocuk Sorgula", callback_data="sorgu_cocuk")],
        [InlineKeyboardButton("📱 TC-GSM Sorgula", callback_data="sorgu_tcgsm"), InlineKeyboardButton("📱 GSM-TC Sorgula", callback_data="sorgu_gsmtc")],
        [InlineKeyboardButton("👤 Profilim", callback_data="profil_im"), InlineKeyboardButton("🎁 Davet Et & VIP Kazan", callback_data="davet_et")],
        [InlineKeyboardButton("👑 VIP Satın Al / Fiyatlar", callback_data="vip_fiyatlar")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(mesaj, reply_markup=reply_markup, parse_mode="HTML")
    elif update.callback_query:
        await update.callback_query.message.edit_text(mesaj, reply_markup=reply_markup, parse_mode="HTML")


# ==========================================
# 7. YÖNETİCİ PANELİ (/panel)
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
        f"⚙️ <b>AraştırX | Yönetici Paneli</b>\n"
        f"────────────────────────\n"
        f"📆 <b>Bugün Gelen:</b> {bugun_gelen} | 📊 <b>Toplam:</b> {toplam_user}\n"
        f"👑 <b>VIP:</b> {vip_user} | 🚫 <b>Banlı:</b> {banli_user}\n"
        f"🛠 <b>Bakım Modu:</b> {bakim_str} | 📢 <b>Kanal Şartı:</b> {sart_str}\n\n"
        f"📌 <b>Kanallar:</b>\n"
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
        await update.message.reply_text(mesaj, reply_markup=reply_markup, parse_mode="HTML")
    elif update.callback_query:
        await update.callback_query.message.edit_text(mesaj, reply_markup=reply_markup, parse_mode="HTML")


# ==========================================
# 8. BUTON İŞLEYİCİSİ
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

    # ADMIN BUTONLARI
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
            await query.message.edit_text("👑 <b>VIP Verilecek Kullanıcının Telegram ID'sini Yazın:</b>", parse_mode="HTML")
            return

        elif data == "adm_vip_kaldir":
            context.user_data["beklenen_islem"] = "vip_kaldir"
            await query.message.edit_text("❌ <b>VIP'si Kaldırılacak Kullanıcının Telegram ID'sini Yazın:</b>", parse_mode="HTML")
            return

        elif data == "adm_kanal_ekle":
            context.user_data["beklenen_islem"] = "kanal_ekle"
            await query.message.edit_text("➕ <b>Eklenecek Kanal Kullanıcı Adını Yazın (Örn: <code>@arastirduyuru</code>):</b>", parse_mode="HTML")
            return

        elif data == "adm_kanal_sil":
            context.user_data["beklenen_islem"] = "kanal_sil"
            await query.message.edit_text("➖ <b>Silinecek Kanal Kullanıcı Adını Yazın (Örn: <code>@arastirduyuru</code>):</b>", parse_mode="HTML")
            return

        elif data == "adm_ban_yonet":
            context.user_data["beklenen_islem"] = "ban_yonet"
            await query.message.edit_text("⛔️ <b>Banlayacağınız veya Banını Kaldıracağınız Kullanıcı ID'sini Yazın:</b>", parse_mode="HTML")
            return

        elif data == "adm_duyuru_gonder":
            context.user_data["beklenen_islem"] = "duyuru_gonder"
            await query.message.edit_text("📢 <b>Tüm Kullanıcılara Gönderilecek Duyuru Metnini Yazın:</b>", parse_mode="HTML")
            return

        elif data == "adm_user_list":
            users = db.get("users", {})
            metin = f"👥 <b>Kullanıcı Listesi ({len(users)} Kişi):</b>\n\n"
            count = 0
            for uid, uinfo in users.items():
                count += 1
                v_tag = " [VIP]" if uinfo.get("vip") else ""
                metin += f"{count}. {html.escape(uinfo.get('name'))} ({uinfo.get('username')}) - <code>{uid}</code>{v_tag}\n"
                if count >= 30:
                    metin += "\n<i>(İlk 30 kullanıcı listelendi)</i>"
                    break
            
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Panele Dön", callback_data="adm_panel_refresh")]])
            await query.message.edit_text(metin, reply_markup=kb, parse_mode="HTML")
            return

    # SORGU BUTONLARI YÖNLENDİRMESİ
    if data.startswith("sorgu_"):
        u_info = db.get("users", {}).get(str(user_id), {})
        if not (u_info.get("vip") or user_id == ADMIN_ID):
            kullanilan = u_info.get("gunluk_sorgu", 0)
            if kullanilan >= GUNLUK_UCRETSIZ_LIMIT:
                msg = (
                    f"⚠️ <b>Günlük Ücretsiz Sorgu Sınırına Ulaştınız!</b>\n\n"
                    f"Günlük ücretsiz sorgu limitiniz (<b>{GUNLUK_UCRETSIZ_LIMIT}</b>) dolmıştır.\n"
                    f"Sınırsız ve kesintisiz sorgu yapmak için VIP üyelik satın alabilir veya arkadaşlarınızı davet ederek VIP kazanabilirsiniz."
                )
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("👑 VIP Satın Al / Fiyatlar", callback_data="vip_fiyatlar")]])
                await query.message.reply_text(msg, reply_markup=kb, parse_mode="HTML")
                return

        context.user_data["aktif_sorgu"] = data
        
        rehber = {
            "sorgu_tc": "Lütfen sorgulanacak <b>11 haneli TC Kimlik Numarasını</b> girin:",
            "sorgu_adsoyad": "Lütfen Ad ve Soyad girin. Ek parametreler için virgül kullanabilirsiniz:\n\n<b>Örnekler:</b>\n• <code>AHMET YILMAZ</code>\n• <code>AHMET, YILMAZ, İSTANBUL</code>",
            "sorgu_aile": "Lütfen Aile sorgusu için <b>TC Kimlik Numarasını</b> girin:",
            "sorgu_sulale": "Lütfen Sülale sorgusu için <b>TC Kimlik Numarasını</b> girin:",
            "sorgu_cocuk": "Lütfen Çocuk sorgusu için <b>TC Kimlik Numarasını</b> girin:",
            "sorgu_adres": "Lütfen Adres/İkametgah sorgusu için <b>TC Kimlik Numarasını</b> girin:",
            "sorgu_gsmtc": "Lütfen <b>GSM Numarasını</b> girin (Örn: <code>05551234567</code>):",
            "sorgu_tcgsm": "Lütfen GSM Numaralarını öğrenmek istediğiniz <b>TC Kimlik Numarasını</b> girin:",
            "sorgu_isyeri": "Lütfen İşyeri/SGK sorgusu için <b>TC Kimlik Numarasını</b> girin:"
        }
        
        msg = rehber.get(data, "Lütfen sorgulamak istediğiniz veriyi yazın:")
        await query.message.reply_text(f"🔍 {msg}", parse_mode="HTML")

    elif data == "profil_im":
        u_info = db.get("users", {}).get(str(user_id), {})
        vip_st = "Evet 💎" if u_info.get("vip") else "Hayır"
        
        if u_info.get("vip") or user_id == ADMIN_ID:
            kalan_hak = "Sınırsız ∞"
        else:
            kalan_hak = f"{max(0, GUNLUK_UCRETSIZ_LIMIT - u_info.get('gunluk_sorgu', 0))} / {GUNLUK_UCRETSIZ_LIMIT}"

        await query.message.reply_text(
            f"👤 <b>Profil Bilgileriniz:</b>\n\n"
            f"• <b>Ad:</b> {html.escape(u_info.get('name', '-'))}\n"
            f"• <b>Kullanıcı Adı:</b> {u_info.get('username', '-')}\n"
            f"• <b>ID:</b> <code>{user_id}</code>\n"
            f"• <b>VIP Üyelik:</b> {vip_st}\n"
            f"• <b>Günlük Kalan Sorgu:</b> {kalan_hak}\n"
            f"• <b>Topladığınız Davet:</b> {u_info.get('davet_sayisi', 0)} Kişi",
            parse_mode="HTML"
        )
    
    elif data == "davet_et":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        u_info = db.get("users", {}).get(str(user_id), {})
        davet_sayisi = u_info.get("davet_sayisi", 0)
        
        msg = (
            f"🎁 <b>ÜCRETSİZ VIP KAZANMA FIRSATI!</b>\n\n"
            f"Aşağıdaki özel davet linkinizi arkadaşlarınıza gönderin. Her <b>10 başarılı davette</b> sistem otomatik olarak hesabınıza <b>3 Günlük VIP</b> tanımlar!\n\n"
            f"📊 <b>Mevcut Davet Sayınız:</b> {davet_sayisi} Kişi\n\n"
            f"🔗 <b>Özel Davet Linkiniz:</b>\n<code>{ref_link}</code>"
        )
        await query.message.reply_text(msg, parse_mode="HTML")

    elif data == "vip_fiyatlar":
        fiyat_text = (
            "Sınırsız sorgu, sıfır bekleme süresi ve kesintisiz VIP ayrıcalıklarına erişmek için büyük indirim başladı!\n\n"
            "👑 <b>1 AYLIK PREMIUM:</b> 2.500 ₺ ➡️ <b>1.250 ₺</b>\n"
            "🔥 <b>3 AYLIK VIP PLUS:</b> 5.000 ₺ ➡️ <b>2.500 ₺</b> <i>(Günün Fırsat Paketi!)</i>\n"
            "💎 <b>6 AYLIK VIP PRO:</b> <b>4.500 ₺</b>\n"
            "🎖️ <b>12 AYLIK YILLIK VIP:</b> <b>7.500 ₺</b>\n"
            "♾️ <b>SINIRSIZ / ÖMÜR BOYU VIP:</b> <b>12.500 ₺</b>\n\n"
            "🎁 <b>ÜCRETSİZ VIP FIRSATI:</b>\n"
            "10 Arkadaşını bota davet et, sistem anında hesabına 3 Günlük VIP tanımlasın!\n\n"
            "📲 <b>Satın Alım & İletişim:</b> @danistay"
        )
        await query.message.reply_text(fiyat_text, parse_mode="HTML")


# ==========================================
# 9. METİN VE API İSTEK İŞLEYİCİSİ
# ==========================================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    db = verileri_yukle()

    # 1. ADMIN BEKLEYEN İŞLEMLERİ
    if user_id == ADMIN_ID and "beklenen_islem" in context.user_data:
        islem = context.user_data.pop("beklenen_islem")

        if islem == "vip_ver":
            if text in db["users"]:
                db["users"][text]["vip"] = True
                verileri_kaydet(db)
                await update.message.reply_text(f"✅ <code>{text}</code> ID'li kullanıcı <b>VIP</b> yapıldı!", parse_mode="HTML")
            else:
                await update.message.reply_text("❌ Bu kullanıcı veritabanında bulunamadı.")

        elif islem == "vip_kaldir":
            if text in db["users"]:
                db["users"][text]["vip"] = False
                db["users"][text]["vip_bitis"] = None
                verileri_kaydet(db)
                await update.message.reply_text(f"✅ <code>{text}</code> ID'li kullanıcının VIP üyeliği kaldırıldı.", parse_mode="HTML")
            else:
                await update.message.reply_text("❌ Bu kullanıcı veritabanında bulunamadı.")

        elif islem == "kanal_ekle":
            if not text.startswith("@"): text = "@" + text
            if text not in db["zorunlu_kanallar"]:
                db["zorunlu_kanallar"].append(text)
                verileri_kaydet(db)
                await update.message.reply_text(f"✅ <code>{text}</code> zorunlu kanallara eklendi!", parse_mode="HTML")
            else:
                await update.message.reply_text("⚠️ Bu kanal zaten listede var.")

        elif islem == "kanal_sil":
            if not text.startswith("@"): text = "@" + text
            if text in db["zorunlu_kanallar"]:
                db["zorunlu_kanallar"].remove(text)
                verileri_kaydet(db)
                await update.message.reply_text(f"✅ <code>{text}</code> zorunlu kanallardan silindi!", parse_mode="HTML")
            else:
                await update.message.reply_text("❌ Bu kanal listede bulunamadı.")

        elif islem == "ban_yonet":
            if text in db["banned_users"]:
                db["banned_users"].remove(text)
                verileri_kaydet(db)
                await update.message.reply_text(f"🟢 <code>{text}</code> ID'li kullanıcının banı kaldırıldı.", parse_mode="HTML")
            else:
                db["banned_users"].append(text)
                verileri_kaydet(db)
                await update.message.reply_text(f"⛔️ <code>{text}</code> ID'li kullanıcı engellendi (Banlandı).", parse_mode="HTML")

        elif islem == "duyuru_gonder":
            basarili = 0
            for uid in db.get("users", {}):
                try:
                    await context.bot.send_message(chat_id=int(uid), text=f"📢 <b>DUYURU:</b>\n\n{text}", parse_mode="HTML")
                    basarili += 1
                except Exception:
                    continue
            await update.message.reply_text(f"✅ Duyuru <code>{basarili}</code> kullanıcıya iletildi!", parse_mode="HTML")

        return

    # 2. CANLI API SORGU İŞLEMLERİ
    if "aktif_sorgu" in context.user_data:
        sorgu_turu = context.user_data.pop("aktif_sorgu")

        # Sorgu Anı Hak Kontrolü
        u_info = db.get("users", {}).get(str(user_id), {})
        if not (u_info.get("vip") or user_id == ADMIN_ID):
            kullanilan = u_info.get("gunluk_sorgu", 0)
            if kullanilan >= GUNLUK_UCRETSIZ_LIMIT:
                await update.message.reply_text(f"⚠️ <b>Günlük 7 ücretsiz sorgu limitiniz dolmuştur.</b>\nVIP satın almak için @danistay ile iletişime geçebilirsiniz.", parse_mode="HTML")
                return

        bekleme_msg = await update.message.reply_text("⏳ <b>Sorgunuz API üzerinden işleniyor, lütfen bekleyin...</b>", parse_mode="HTML")
        
        endpoint = ""
        params = {}

        if sorgu_turu == "sorgu_tc":
            endpoint = "tc.php"
            params = {"tc": text}

        elif sorgu_turu == "sorgu_adsoyad":
            endpoint = "adsoyad.php"
            if "," in text:
                parcalar = [p.strip() for p in text.split(",")]
                params["ad"] = parcalar[0]
                if len(parcalar) > 1: params["soyad"] = parcalar[1]
                if len(parcalar) > 2: params["il"] = parcalar[2]
                if len(parcalar) > 3: params["ilce"] = parcalar[3]
            else:
                # Virgül kullanılmadıysa boşluğa göre ad ve soyadı ayır
                parcalar = text.split()
                if len(parcalar) >= 2:
                    params["soyad"] = parcalar[-1]  # Son kelime soyad
                    params["ad"] = " ".join(parcalar[:-1])  # Geri kalanı ad (örn: Ahmet Can)
                else:
                    params["ad"] = text
                    params["soyad"] = ""

        elif sorgu_turu == "sorgu_aile":
            endpoint = "aile.php"
            params = {"tc": text}

        elif sorgu_turu == "sorgu_sulale":
            endpoint = "sulale.php"
            params = {"tc": text}

        elif sorgu_turu == "sorgu_cocuk":
            endpoint = "cocuk.php"
            params = {"tc": text}

        elif sorgu_turu == "sorgu_adres":
            endpoint = "adres.php"
            params = {"tc": text}

        elif sorgu_turu == "sorgu_gsmtc":
            endpoint = "gsmtc.php"
            params = {"gsm": text}

        elif sorgu_turu == "sorgu_tcgsm":
            endpoint = "tcgsm.php"
            params = {"tc": text}

        elif sorgu_turu == "sorgu_isyeri":
            endpoint = "isyeri.php"
            params = {"tc": text}

        # API İSTEĞİ AT
        ok, res = await api_istek_at(endpoint, params)
        
        await bekleme_msg.delete()

        if ok:
            # Sorgu Başarılı Olduğunda Hakkı Düş (VIP/Admin Değilse)
            if not (u_info.get("vip") or user_id == ADMIN_ID):
                db["users"][str(user_id)]["gunluk_sorgu"] = u_info.get("gunluk_sorgu", 0) + 1
                verileri_kaydet(db)

            cevap = format_api_response_html(sorgu_turu, res)
            await guvenli_html_mesaj_gonder(update.message, cevap)
        else:
            await update.message.reply_text(f"❌ <b>API Bağlantı Hatası:</b> {html.escape(str(res))}", parse_mode="HTML")


# ==========================================
# 10. BOTU BAŞLAT
# ==========================================
if __name__ == '__main__':
    keep_alive()
    
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("panel", panel_komutu))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))

    print("AraştırX Canlı API Bağlantılı Bot Aktif!")
    bot_app.run_polling()
