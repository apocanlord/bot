# Örnek olarak aiogram kütüphanesine göre hazırlanmıştır.
# Kendi veritabanı veya sayaç değişkenlerinizi buradaki fonksiyonlara bağlayabilirsiniz.

@dp.message_handler(commands=["panel"])
async def panel_command(message: types.Message):
    # Yetki kontrolü eklemek istersen buraya koyabilirsin (örn: admin ID kontrolü)
    
    # 📌 Buradaki değerleri kendi veritabanınızdan veya sayaçlarınızdan çekmelisiniz:
    bot_status = "Çevrimiçi"
    total_users = 0      # Veritabanından toplam kullanıcı sayısı
    daily_commands = 0   # Bugün çalıştırılan toplam komut
    daily_new_users = 0  # Bugün katılan yeni kullanıcı
    required_channel = "Ayarlanmadı" # Ayarlı olan zorunlu kanal (@kanaladi)

    panel_text = (
        f"⚙️ **@arastirxbot** Yönetim Paneli\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 **Sistem Durumu:** {bot_status}\n"
        f"👥 **Toplam Kullanıcı:** `{total_users}`\n"
        f"📊 **Günlük İstatistik:** `{daily_commands}` Komut / `{daily_new_users}` Yeni\n"
        f"📢 **Zorunlu Kanal:** `{required_channel}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ *Son Güncelleme: Anlık*"
    )

    # MarkdownV2 veya HTML kullanıyorsanız parse_mode'u buna göre ayarlayabilirsiniz (Buradaki yapı Markdown içindir)
    await message.reply(panel_text, parse_mode="Markdown")
