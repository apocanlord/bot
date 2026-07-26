from telegram import Update
from telegram.ext import ContextTypes

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Eğer sayaç veya veritabanı değişkenlerin henüz yoksa 0 olarak tanımlıyoruz
    bot_status = "Çevrimiçi"
    total_users = 0      
    daily_commands = 0   
    daily_new_users = 0  
    required_channel = "Ayarlanmadı"

    panel_text = (
        "⚙️ **@arastirxbot** Yönetim Paneli\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 **Sistem Durumu:** {bot_status}\n"
        f"👥 **Toplam Kullanıcı:** `{total_users}`\n"
        f"📊 **Günlük İstatistik:** `{daily_commands}` Komut / `{daily_new_users}` Yeni\n"
        f"📢 **Zorunlu Kanal:** `{required_channel}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ *Son Güncelleme: Anlık*"
    )

    await update.message.reply_text(panel_text, parse_mode="Markdown")
