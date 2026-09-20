import os
import json
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request

# Bot Token
TOKEN = "8646358320:AAFPFwcTofU1SOShS_yHpRBa3MrhlNvF22c"
bot = telebot.TeleBot(TOKEN, threaded=False)

# Ayarlar
ZORUNLU_KANAL = "@arastirduyuru"
ADMIN_USERNAME = "danistay"

# GitHub Yedekleme Bilgileri
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "apocanlord/VIP-BOT")
FILE_PATH = "users.json"

users_data = set()
vip_users = set()

def load_users_from_github():
    global users_data
    if not GITHUB_TOKEN:
        return
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            content = response.json().get("content")
            if content:
                import base64
                decoded_content = base64.b64decode(content).decode("utf-8")
                users_data = set(json.loads(decoded_content))
    except Exception as e:
        print(f"Yükleme hatası: {e}")

def save_users_to_github():
    if not GITHUB_TOKEN:
        return
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    
    try:
        sha = None
        get_resp = requests.get(url, headers=headers, timeout=10)
        if get_resp.status_code == 200:
            sha = get_resp.json().get("sha")
            
        import base64
        json_data = json.dumps(list(users_data))
        encoded_content = base64.b64encode(json_data.encode("utf-8")).decode("utf-8")
        
        data = {
            "message": "Auto-backup users database",
            "content": encoded_content,
            "branch": "main"
        }
        if sha:
            data["sha"] = sha
            
        requests.put(url, headers=headers, json=data, timeout=10)
    except Exception as e:
        print(f"Kayıt hatası: {e}")

load_users_from_github()

def check_channel_membership(user_id):
    if not ZORUNLU_KANAL:
        return True
    try:
        status = bot.get_chat_member(ZORUNLU_KANAL, user_id).status
        if status in ['member', 'creator', 'administrator']:
            return True
    except Exception:
        pass
    return False

def channel_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📢 Kanalımıza Katıl", url=f"https://t.me/{ZORUNLU_KANAL.replace('@', '')}"))
    markup.add(InlineKeyboardButton("✅ Kontrol Et", callback_data="check_subscription"))
    return markup

def main_menu_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("⚡ VIP Özel Analiz & Sorgu Araçları", callback_data="vip_analiz_menu"),
        InlineKeyboardButton("💎 Premium Paketler & Fiyatlar", callback_data="menu_fiyat"),
        InlineKeyboardButton("👤 Üyelik Durumumu Sorgula", callback_data="menu_profil"),
        InlineKeyboardButton("📢 Duyuru Kanalımız", url=f"https://t.me/{ZORUNLU_KANAL.replace('@', '')}")
    )
    return markup

def vip_sub_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("⭐ Ek Araçlar", callback_data="sub_ek_araclar"),
        InlineKeyboardButton("📇 Kişi Çözümleri", callback_data="sub_kisi_cozumleri"),
        InlineKeyboardButton("📱 GSM Çözümleri", callback_data="sub_gsm_cozumleri"),
        InlineKeyboardButton("💼 Maliye Çözümleri", callback_data="sub_maliye_cozumleri"),
        InlineKeyboardButton("📍 Adres Çözümleri", callback_data="sub_adres_cozumleri"),
        InlineKeyboardButton("🗺️ Arazi Çözümleri", callback_data="sub_arazi_cozumleri"),
        InlineKeyboardButton("🏦 İBAN Çözümleri", callback_data="sub_iban_cozumleri"),
        InlineKeyboardButton("🏥 Sağlık Çözümleri", callback_data="sub_saglik_cozumleri"),
        InlineKeyboardButton("🪪 Kimlik Çözümleri", callback_data="sub_kimlik_cozumleri"),
        InlineKeyboardButton("📸 Instagram Çözümleri", callback_data="sub_instagram"),
        InlineKeyboardButton("🏛️ E-Devlet İşlemleri", callback_data="sub_edevlet"),
        InlineKeyboardButton("📞 Telefon İşlemleri", callback_data="sub_telefon"),
        InlineKeyboardButton("🚨 POLNET", callback_data="sub_polnet"),
        InlineKeyboardButton("💬 WhatsApp Çözümleri", callback_data="sub_whatsapp"),
        InlineKeyboardButton("📍 Canlı Takip & GPS", callback_data="sub_canli_takip"),
        InlineKeyboardButton("🖼️ Medya & Galeri", callback_data="sub_medya"),
        InlineKeyboardButton("🏨 Konaklama & Seyahat", callback_data="sub_konaklama"),
        InlineKeyboardButton("💳 Finans & Banka", callback_data="sub_finans"),
        InlineKeyboardButton("📂 Gelişmiş Arşiv", callback_data="sub_arsiv"),
        InlineKeyboardButton("💻 Cihaz Kontrol (RAT)", callback_data="sub_rat"),
        InlineKeyboardButton("⬅️ Ana Menüye Dön", callback_data="ana_menu")
    )
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    username = message.from_user.username
    
    if chat_id not in users_data:
        users_data.add(chat_id)
        save_users_to_github()

    if not check_channel_membership(chat_id):
        bot.send_message(
            chat_id, 
            "⚠️ Botu kullanabilmek için öncelikle duyuru kanalımıza abone olmanız gerekmektedir!", 
            reply_markup=channel_keyboard()
        )
        return

    is_admin = (username and username.lower() == ADMIN_USERNAME.lower())
    is_vip = chat_id in vip_users or is_admin
    unvan = "👑 VIP & ADMIN ÜYE" if is_admin else ("⭐ VIP ÜYE" if is_vip else "👤 STANDART ÜYE")

    text = (
        f"👋 Tekrar Hoş Geldin **{message.from_user.first_name}**! {unvan}\n"
        "________________________________________\n\n"
        "🔒 ÖNEMLİ BİLGİLENDİRME:\n"
        "⚡ Bu bot SADECE VIP ÜYELERE ÖZELDİR. Gelişmiş sorgu ve analiz sistemlerini kullanabilmek için aktif bir VIP üyeliğinizin bulunması gerekmektedir.\n\n"
        "Aşağıdaki butonları kullanarak üyelik durumunuzu inceleyebilir veya VIP ayrıcalıklarına erişebilirsiniz:"
    )
    bot.send_message(chat_id, text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")

@bot.message_handler(commands=['panel'])
def admin_panel(message):
    username = message.from_user.username
    if not username or username.lower() != ADMIN_USERNAME.lower():
        bot.send_message(message.chat.id, "❌ Bu komutu yalnızca Bot Admini kullanabilir!")
        return
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💎 VIP Üye Listesi", callback_data="admin_viplist"),
        InlineKeyboardButton("📢 Duyuru Oluştur", callback_data="admin_duyuru"),
        InlineKeyboardButton("🔄 Yenile", callback_data="admin_yenile"),
        InlineKeyboardButton("❌ Paneli Kapat", callback_data="menu_cikis")
    )
    bot.send_message(message.chat.id, f"🛠️ **Admin Paneline Hoş Geldin, @{ADMIN_USERNAME}!**\n\nToplam Kullanıcı: `{len(users_data)}`", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    username = call.message.chat.username
    is_admin = (username and username.lower() == ADMIN_USERNAME.lower())
    is_vip = chat_id in vip_users or is_admin

    def safe_edit(text, reply_markup=None):
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception:
            pass

    if call.data == "check_subscription":
        if check_channel_membership(chat_id):
            try:
                bot.delete_message(chat_id, message_id)
            except:
                pass
            text = "👑 **ARASTIRX** Paneline Hoş Geldin!\n\nAşağıdaki menüden dilediğin kategoriye geçiş yapabilirsin:"
            bot.send_message(chat_id, text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "❌ Henüz kanala abone olmamışsınız!", show_alert=True)
        return

    if call.data == "ana_menu":
        safe_edit("👑 **ARASTIRX** Ana Menü:", reply_markup=main_menu_keyboard())

    elif call.data == "vip_analiz_menu":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Bu alana girebilmek için aktif bir VIP üyeliğin olmalıdır!", show_alert=True)
            return
        safe_edit("⚡ **VIP Özel Analiz & Sorgu Araçları**\n\nKategori seçiniz:", reply_markup=vip_sub_menu())
        
    elif call.data == "sub_ek_araclar":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("Plaka/Borç Sorgu", callback_data="islem_plaka"),
              InlineKeyboardButton("IP Konum Sorgu", callback_data="islem_ip"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("⭐ **Ek Araçlar**", reply_markup=m)

    elif call.data == "sub_kisi_cozumleri":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("Ad İle Sorgu", callback_data="k_ad"),
              InlineKeyboardButton("Ad Soyad Pro", callback_data="k_adsoyad"),
              InlineKeyboardButton("Aile Pro Sorgu", callback_data="k_aile"),
              InlineKeyboardButton("Sülale Sorgu", callback_data="k_sulale"),
              InlineKeyboardButton("Ad Soyad Sorgu (F)", callback_data="k_adsoyadf"),
              InlineKeyboardButton("Çocuk Sorgu", callback_data="k_cocuk"),
              InlineKeyboardButton("Full Sorgu", callback_data="k_full"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("📇 **Kişi Çözümleri**", reply_markup=m)

    elif call.data == "sub_gsm_cozumleri":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("GSM -> TC (210M)", callback_data="gsm_tc"),
              InlineKeyboardButton("TC -> GSM (210M)", callback_data="tc_gsm"),
              InlineKeyboardButton("Sms Bomber Pro", callback_data="sms_bomber"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("📱 **GSM Çözümleri**", reply_markup=m)

    elif call.data == "sub_maliye_cozumleri":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("TC -> İşyeri Arkadaşı", callback_data="maliye_arkadas"),
              InlineKeyboardButton("TC -> İşyeri Sorgu", callback_data="maliye_isyeri"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("💼 **Maliye Çözümleri**", reply_markup=m)

    elif call.data == "sub_adres_cozumleri":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("TC -> Vergi No", callback_data="adres_vergi"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("📍 **Adres Çözümleri**", reply_markup=m)

    elif call.data == "sub_arazi_cozumleri":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("TC -> Tapu", callback_data="arazi_tapu"),
              InlineKeyboardButton("Ada Parsel -> TC", callback_data="arazi_parsel"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("🗺️ **Arazi Çözümleri**", reply_markup=m)

    elif call.data == "sub_iban_cozumleri":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("İBAN Sorgu V1", callback_data="iban_v1"),
              InlineKeyboardButton("İBAN Sorgu V2", callback_data="iban_v2"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("🏦 **İBAN Çözümleri**", reply_markup=m)

    elif call.data == "sub_saglik_cozumleri":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("Nöbetçi Eczane", callback_data="saglik_eczane"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("🏥 **Sağlık Çözümleri**", reply_markup=m)

    elif call.data == "sub_kimlik_cozumleri":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("Kimlik Oluşturucu", callback_data="kimlik_olustur"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("🪪 **Kimlik Çözümleri**", reply_markup=m)

    elif call.data == "sub_instagram":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("Gizli Profil Görüntüle", callback_data="ig_gizli"),
              InlineKeyboardButton("Instagram Sızma", callback_data="ig_sizma"),
              InlineKeyboardButton("DM Mesaj Takibi", callback_data="ig_dm"),
              InlineKeyboardButton("Gizli Hikaye İzlenme", callback_data="ig_hikaye"),
              InlineKeyboardButton("Şifresiz Takipçi Paneli", callback_data="ig_panel"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("📸 **Instagram Çözümleri**", reply_markup=m)

    elif call.data == "sub_edevlet":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("E-İmza Sorgu", callback_data="edevlet_eimza"),
              InlineKeyboardButton("E-Devlet Giriş", callback_data="edevlet_giris"),
              InlineKeyboardButton("Kişiye Ait İmza", callback_data="edevlet_imza"),
              InlineKeyboardButton("E-Devlet Vesika", callback_data="edevlet_vesika"),
              InlineKeyboardButton("Pasaport Bilgileri", callback_data="edevlet_pasaport"),
              InlineKeyboardButton("QR Kodlu İkametgah", callback_data="edevlet_ikametgah"),
              InlineKeyboardButton("Adına Kayıtlı GSM", callback_data="edevlet_gsm"),
              InlineKeyboardButton("Enabiz Takip", callback_data="edevlet_enabiz"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("🏛️ **E-Devlet İşlemleri**", reply_markup=m)

    elif call.data == "sub_telefon":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("Telefon Sorgu", callback_data="tel_sorgu"),
              InlineKeyboardButton("IMEI Sorgu", callback_data="tel_imei"),
              InlineKeyboardButton("Anlık Konum Sorgu", callback_data="tel_konum"),
              InlineKeyboardButton("Fatura Detay Dökümü", callback_data="tel_fatura"),
              InlineKeyboardButton("Arama Kayıtları", callback_data="tel_arama"),
              InlineKeyboardButton("İnternet Trafiği", callback_data="tel_internet"),
              InlineKeyboardButton("Gizli Numara Sorgu", callback_data="tel_gizli"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("📞 **Telefon İşlemleri**", reply_markup=m)

    elif call.data == "sub_polnet":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("Scil Sorgu", callback_data="polnet_scil"),
              InlineKeyboardButton("Kom Arşiv Sorgu", callback_data="polnet_kom"),
              InlineKeyboardButton("Tem Arşiv Sorgu", callback_data="polnet_tem"),
              InlineKeyboardButton("Gözaltı Sorgu", callback_data="polnet_gozalti"),
              InlineKeyboardButton("Kişi Karıştığı Olaylar", callback_data="polnet_olay"),
              InlineKeyboardButton("Şahıs Adli İşlemleri", callback_data="polnet_sahis"),
              InlineKeyboardButton("Adli Evrak Sorgu", callback_data="polnet_evrak"),
              InlineKeyboardButton("Dava Sorgu", callback_data="polnet_dava"),
              InlineKeyboardButton("İcra Sorgu", callback_data="polnet_icra"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("🚨 **POLNET**", reply_markup=m)

    elif call.data == "sub_whatsapp":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("WhatsApp Sızma", callback_data="wa_sizma"),
              InlineKeyboardButton("Silinen Mesajları Kurtar", callback_data="wa_silinen"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("💬 **WhatsApp Çözümleri**", reply_markup=m)

    elif call.data == "sub_canli_takip":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("Numaradan Canlı Konum", callback_data="gps_numara"),
              InlineKeyboardButton("Geçmiş Konum Hareketleri", callback_data="gps_gecmis"),
              InlineKeyboardButton("Sinyal Kesici (Jammer)", callback_data="gps_jammer"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("📍 **Canlı Takip & GPS**", reply_markup=m)

    elif call.data == "sub_medya":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("Galeri Sızma (Android)", callback_data="medya_galeri"),
              InlineKeyboardButton("Silinen Fotoğrafları Kurtar", callback_data="medya_fotograf"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("🖼️ **Medya & Galeri**", reply_markup=m)

    elif call.data == "sub_konaklama":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("Otel Konaklama Sorgu", callback_data="seyahat_otel"),
              InlineKeyboardButton("Uçak/Otobüs Sorgu", callback_data="seyahat_ulasim"),
              InlineKeyboardButton("Sınır Giriş-Çıkış Sorgu", callback_data="seyahat_sinir"),
              InlineKeyboardButton("Pasaport & Vize Sorgu", callback_data="seyahat_pasaport"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("🏨 **Konaklama & Seyahat**", reply_markup=m)

    elif call.data == "sub_finans":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("Banka Hesap Bakiyesi", callback_data="finans_bakiye"),
              InlineKeyboardButton("Kredi Kartı Hareketleri", callback_data="finans_kredi"),
              InlineKeyboardButton("Aktif POS Cihazı Sorgu", callback_data="finans_pos"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("💳 **Finans & Banka**", reply_markup=m)

    elif call.data == "sub_arsiv":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("Polis Telsiz Logları", callback_data="arsiv_telsiz"),
              InlineKeyboardButton("Adli Sicil (Sabıka) Sorgu", callback_data="arsiv_sabika"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("📂 **Gelişmiş Arşiv**", reply_markup=m)

    elif call.data == "sub_rat":
        if not is_vip:
            bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!", show_alert=True)
            return
        m = InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton("Mikrofon Dinleme", callback_data="rat_mikrofon"),
              InlineKeyboardButton("Dosya Yöneticisi Erişimi", callback_data="rat_dosya"),
              InlineKeyboardButton("⬅️ Geri Dön", callback_data="vip_analiz_menu"))
        safe_edit("💻 **Cihaz Kontrol (RAT)**", reply_markup=m)

    elif call.data == "menu_fiyat":
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("⬅️ Ana Menüye Dön", callback_data="ana_menu"))
        fiyat_text = (
            "👑 **ARASTIRX | ÖZEL VIP & PLUS ÜYELİK KAMPANYASI!** 🚀\n\n"
            "• 1 Aylık Premium: 1.500 TL yerine **1.350 TL** 💳\n"
            "• 3 Aylık Premium: 2.500 TL yerine **2.250 TL** 💳\n"
            "• 6 Aylık Premium: 4.500 TL yerine **4.050 TL** 📅\n"
            "• 12 Aylık Premium: 7.500 TL yerine **6.750 TL** 🎁\n"
            "• 12 Aylık Plus Paket: 9.000 TL yerine **8.100 TL** 🚀\n\n"
            "📌 **İletişim:** @danistay 💬"
        )
        safe_edit(fiyat_text, reply_markup=m)

    elif call.data == "menu_profil":
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("⬅️ Ana Menüye Dön", callback_data="ana_menu"))
        durum = "Aktif VIP Üye ✨" if is_vip else "Standart Üye (VIP Değil) ❌"
        profil_text = (
            f"👤 **Üyelik Bilgileriniz:**\n\n"
            f"• Kullanıcı ID: `{chat_id}`\n"
            f"• Durum: **{durum}**\n\n"
            f"Paket satın almak veya süreyi uzatmak için iletişim: @danistay"
        )
        safe_edit(profil_text, reply_markup=m)

    elif call.data == "menu_cikis":
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass
        bot.send_message(chat_id, "Menü kapatıldı. Tekrar açmak için /start yazabilirsin kanka!")

# Flask Webhook Sunucusu
app = Flask('')

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route('/')
def index():
    return "Bot webhook aktif!", 200

if __name__ == "__main__":
    # Eski webhook'ları temizle
    bot.remove_webhook()
    
    # Render'ın verdiği dış URL'yi al
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
    if RENDER_URL:
        bot.set_webhook(url=f"{RENDER_URL}/{TOKEN}")
        print(f"Webhook başarıyla ayarlandı: {RENDER_URL}/{TOKEN}")
    
    # Flask sunucusunu başlat
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
