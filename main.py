async def api_istek_at(endpoint: str, params: dict):
    url = f"http://arastir.vip/api/{endpoint}"
    
    # Gerçek bir tarayıcı taklidi (Cloudflare / WAF engellerini aşmak için)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive"
    }
    
    try:
        # SSL ve zaman aşımı yapılandırması
        timeout = aiohttp.ClientTimeout(total=20)
        connector = aiohttp.TCPConnector(ssl=False)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return True, data
                else:
                    return False, f"API Hatası (HTTP {response.status})"
    except aiohttp.ClientConnectorError:
        return False, "Sunucuya bağlanılamadı. API IP engeli uyguluyor olabilir."
    except Exception as e:
        return False, f"Sunucu Bağlantı Hatası: {str(e)}"
