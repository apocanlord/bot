from flask import Flask
import threading

# 1. Mini Web Sunucusu (Render'ın port isteğini karşılamak için)
app = Flask('')

@app.route('/')
def home():
    return "Bot Aktif ve Çalışıyor!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

# Botu başlatmadan önce web sunucusunu tetikliyoruz
if __name__ == '__main__':
    keep_alive()
    # Buradan sonra mevcut bot çalıştırma kodun (örn: application.run_polling() vb.) devam edebilir.
