import json
import os

# ==========================================
# 1. DOSYA YÖNETİMİ (JSON ALTYAPISI)
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

# ==========================================
# 2. VIP İŞLEMLERİ (EKLEME & KONTROL)
# ==========================================
def vip_ekle(user_id, bitis_tarihi):
    data = verileri_yukle()
    data[str(user_id)] = {
        "vip": True,
        "bitis_tarihi": bitis_tarihi
    }
    verileri_kaydet(data)
    print(f"{user_id} VIP olarak kaydedildi!")

def vip_mi(user_id):
    data = verileri_yukle()
    user_data = data.get(str(user_id))
    if user_data and user_data.get("vip") == True:
        return True
    return False
