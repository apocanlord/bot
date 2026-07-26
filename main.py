        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*'
            }
            
            # Eğer API bir anahtar (Token) gerektiriyorsa buraya eklenmeli:
            # headers['Authorization'] = 'Bearer SENIN_API_KEYIN'

            if q_type == "adsoyad":
                parts = query_text.split(" ", 1)
                ad = parts[0]
                soyad = parts[1] if len(parts) > 1 else ""
                api_url = f"https://arastir.vip/adsoyad.php?ad={requests.utils.quote(ad)}&soyad={requests.utils.quote(soyad)}"
            elif q_type in ["tc", "tcgsm", "cocuk", "aile", "sulale", "isyeri", "adres"]:
                api_url = f"https://arastir.vip/{q_type}.php?tc={requests.utils.quote(query_text)}"
            elif q_type == "gsmtc":
                api_url = f"https://arastir.vip/gsmtc.php?gsm={requests.utils.quote(query_text)}"
            else:
                api_url = f"https://arastir.vip/{q_type}.php?q={requests.utils.quote(query_text)}"
            
            response = requests.get(api_url, headers=headers, timeout=15)
            
            # 403 veya başka bir hata durumunda sunucunun döndürdüğü HTML/Metin içeriğini görelim
            if response.status_code == 200:
                res_data = response.json()
                
                if isinstance(res_data, list) and len(res_data) > 0:
                    res_data = res_data[0]
                    
                if isinstance(res_data, dict) and len(res_data) > 0:
                    sonuc_mesaji = f"✅ **Sorgu Başarılı ({q_type.upper()})**\n━━━━━━━━━━━━━━━━━━\n"
                    for key, val in res_data.items():
                        sonuc_mesaji += f"🔹 **{key.capitalize()}:** `{val}`\n"
                    sonuc_mesaji += "━━━━━━━━━━━━━━━━━━"
                else:
                    sonuc_mesaji = f"⚠️ Aranan kriterlere uygun veri bulunamadı."
                
                await update.message.reply_text(sonuc_mesaji, parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ API Sunucu Hatası: {response.status_code}\nDetay: {response.text[:200]}")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Bağlantı hatası oluştu: {str(e)}")
