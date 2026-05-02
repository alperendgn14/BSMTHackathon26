import feedparser
import os
import json
from groq import Groq
from dotenv import load_dotenv
import requests
from datetime import datetime, timezone
import urllib.robotparser

load_dotenv()

# Groq API Anahtarını buraya yapıştır
api_key = os.getenv("GROQ_API_KEY")

if api_key is None:
    raise ValueError("Hata: .env dosyasında GROQ_API_KEY bulunamadı!")

client = Groq()
feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Verilerin kaydedileceği MVP veritabanı dosyamız
DB_FILE = "database.json"

def analyze_with_llama3_api(text):
    # JSON anahtarlarını İngilizce olarak sabitlediğimiz katı prompt
    prompt = f"""Sen bir endüstriyel haber analistsin. Aşağıdaki haber metninden bilgileri çıkar. 
    SADECE aşağıdaki JSON formatında çıktı ver, anahtarları (keys) ASLA Türkçeye çevirme:
    {{
        "event_type": "relocation | closure | expansion | new_plant | tender | other",
        "summary_tr": "Türkçe 2-4 cümlelik özet",
        "company": "Şirket adı veya null",
        "from_location": "Çıkış lokasyonu veya null",
        "to_location": "Hedef lokasyon veya null",
        "sector": "Sektör veya null",
    }}
    METİN: {text}"""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a data extraction assistant that strictly outputs in the requested JSON format."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}, 
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f'{{"error": "API bağlantı hatası: {str(e)}"}}'




def save_to_db(new_data):
    # Mevcut verileri oku veya yeni dosya oluştur
    data = []
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                pass
    
    # Yeni haberi ekle ve kaydet
    data.append(new_data)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"💾 Veri {DB_FILE} dosyasına eklendi!")

# F13: Yüksek Skorlu Fırsatlar İçin Bildirim
def send_webhook_alert(news_data):
    # Bir Discord sunucusu açıp kanal ayarlarından saniyeler içinde Webhook URL alabilirsin.
    WEBHOOK_URL = "BURAYA_DISCORD_VEYA_SLACK_WEBHOOK_URL_GELECEK"
    
    if news_data.get("score", 0) >= 80:
        mesaj = {
            "content": f"🚨 **YENİ YÜKSEK FIRSAT YAKALANDI! (Skor: {news_data['score']})**\n"
                       f"🏢 **Şirket:** {news_data['company']}\n"
                       f"📍 **Rota:** {news_data['from_location']} ➡️ {news_data['to_location']}\n"
                       f"📝 **Özet:** {news_data['summary_tr']}\n"
                       f"🔗 [Kaynağa Git]({news_data['url']})"
        }
        try:
            requests.post(WEBHOOK_URL, json=mesaj)
            print("🔔 Discord/Slack bildirimi gönderildi!")
        except Exception as e:
            print("Bildirim hatası:", e)

def check_robots_txt(url):
    try:
        # Domain'in ana robots.txt dosyasını bul (Örn: https://www.reuters.com/robots.txt)
        parsed_uri = urllib.parse.urlparse(url)
        base_url = '{uri.scheme}://{uri.netloc}'.format(uri=parsed_uri)
        
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(base_url + "/robots.txt")
        rp.read()
        
        # Sitemizin botu (USER_AGENT) buraya girebilir mi?
        return rp.can_fetch(feedparser.USER_AGENT, url)
    except:
        return True # Hata varsa (dosya yoksa vb.) varsayılan olarak izin ver



def fetch_rss_news(rss_url):
    print(f"[{rss_url}] adresinden haberler çekiliyor...\n")
    
    # İŞTE EKSİK OLAN/BULUNAMAYAN SATIR BURASI:
    feed = feedparser.parse(rss_url)

    # Hackathon F3 Zorunluluğu: Bağlantı kontrolü
    if feed.bozo != 0:
        print("RSS okuma hatası! Geçerli bir bağlantı olduğundan emin ol.")
        return

    # İşlemi hızlandırmak için ilk 3 haberi test edelim
    for i, entry in enumerate(feed.entries[:3]):
        
        # F5 Zorunluluğu: Kopya Haber Kontrolü (Dedup)
        if is_duplicate(entry.link):
            print(f"⏭️ Zaten eklenmiş, atlanıyor: {entry.title}")
            continue

        print(f"--- İşlenen Haber {i+1} ---")
        
        # Llama 3 API'sine gönder
        ai_json_result = analyze_with_llama3_api(entry.title)
        
        try:
            parsed_json = json.loads(ai_json_result)
            
            # Veritabanına (JSON'a) kaydetmeden önce arayüz için gerekli ekstra verileri ekle
            parsed_json["original_title"] = entry.title
            parsed_json["url"] = entry.link
            parsed_json["published_date"] = entry.get('published', '')
            
            # Deterministik BIOS-Fit Skorunu hesapla ve AI'ın uydurduğu skorun üzerine yaz (F7b)
            parsed_json["score"] = calculate_bios_fit_score(parsed_json, entry.link)
            
            print(json.dumps(parsed_json, indent=4, ensure_ascii=False))
            save_to_db(parsed_json)
            
        except Exception as e:
            print("❌ JSON ayrıştırma hatası:", e)
            
        print("-" * 30)

def calculate_bios_fit_score(parsed_json, source_url):
    # event type - ağırlık : 0.30
    e_map ={"relocation": 1.0, 
           "new_plant": 0.90,
           "expansion": 0.75,
           "tender": 0.55,
           "closure": 0.45,
           "other": 0.10}
    e_val = e_map.get(parsed_json.get("event_type", "other"), 0.10)
    
    #a, aktör netliği. - ağırlık 0.25
    a_val = 0.0
    if parsed_json.get("company"): a_val += 0.40
    if parsed_json.get("from_location"): a_val +=0.25
    if parsed_json.get("to_location"): a_val +=0.25
    if parsed_json.get("sector"): a_val +=0.10
    
    # g, coğrafya. - ağırlık 0.20 (MVP için Avrupa ülkeleri basit metin kontrolü)
    loc_text = str(parsed_json.get("from_location")) + str(parsed_json.get("to_location"))
    if any(country in loc_text for country in ["Germany", "Almanya", "France", "Poland", "Turkey", "Türkiye", "Europe"]):
        g_val = 1.0
    else:
        g_val = 0.50
        
        
    # t, zaman ve c, kaynak güveni. 
    t_val = 0.70 # ortalama zaman penceresi 
    c_val = 0.85 if "reuters" in source_url or "bloomberg" in source_url else 0.55
    
    # dökümandaki formül
    raw_score = 100* ((0.30 * e_val)+ (0.25 * a_val) + (0.20 * g_val) + (0.15 * t_val) + (0.10 * c_val))
    return round(raw_score)
    
    
#kopya haber engelleyici
def is_duplicate(url):
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return any(item.get("url") == url for item in data)
            except:
                return False
    return False

    


if __name__ == "__main__":
    test_rss_url = "https://news.google.com/rss/search?q=factory+relocation+europe&hl=en-US&gl=US&ceid=US:en" 
    fetch_rss_news(test_rss_url)