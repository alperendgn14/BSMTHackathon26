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
    prompt = f"""Sen BIOS için fırsat çıkaran bir endüstriyel relokasyon analistsin.
GÖREV: Metinden şirket, lokasyon, sektör, hat tipi, zaman çizelgesi ve CAPEX bilgilerini çıkar.
KURALLAR: Sadece JSON döndür. Bulamadığın alanları null bırak. Çıktı dili Türkçe olsun.

İSTENEN JSON YAPISI:
{{
  "article": {{
    "text_summary_tr": "2-4 cümlelik özet",
    "event_type": "relocation | closure | downsizing | expansion | new_plant | tender | capex_fdi | other",
    "confidence": 0.0-1.0 arası sayı
  }},
  "entities": {{
    "company": {{"name": "string", "ticker": "null"}},
    "countries": ["list"],
    "from_location": "string",
    "to_location": "string"
  }},
  "industry": {{
    "sector": "string",
    "line_type": "string",
    "equipment_keywords": ["list"]
  }},
  "signals": {{
    "capex_usd": number,
    "jobs_impact": integer,
    "timeline": "string"
  }},
  "bios_fit": {{
    "rationale_tr": "Skor gerekçesi",
    "recommended_action": "monitor | reach_out | tender_watch"
  }}
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
        new_data["audit"] = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), # İzlenebilirlik
        "gdpr_compliant": True, # Kişisel veri işlenmedi onayı
        "source_publisher": "Google News RSS Agent" # Kaynak odaklı yaklaşım
}
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
    # Döküman 2 (SOW) 2.5 maddesindeki iç içe yapıya göre verileri çekiyoruz
    source_data = parsed_json.get("source", {})
    article_data = parsed_json.get("article", {})
    entities_data = parsed_json.get("entities", {})
    industry_data = parsed_json.get("industry", {})
    signals_data = parsed_json.get("signals", {})
    
    # 1. R: Relokasyon Doğrudanlığı (Relocation Directness) - Ağırlık: 0.18
    # Relocation/Line Transfer ise tam puan; yatırım ise orta puan
    event_type = article_data.get("event_type", "other")
    r_map = {"relocation": 1.0, "new_plant": 0.8, "expansion": 0.7, "tender": 0.5, "closure": 0.4, "other": 0.1}
    r_val = r_map.get(event_type, 0.1)

    # 2. G: Coğrafi Uygunluk (Geographical Suitability) - Ağırlık: 0.15
    # Avrupa ülkeleri ve Türkiye öncelikli
    loc_text = f"{entities_data.get('from_location', '')} {entities_data.get('to_location', '')}".lower()
    europe_keywords = ["germany", "france", "poland", "turkey", "türkiye", "romania", "hungary", "europe"]
    g_val = 1.0 if any(k in loc_text for k in europe_keywords) else 0.5

    # 3. S: Sektör Önceliği (Industry Priority) - Ağırlık: 0.12
    # Otomotiv, enerji, batarya, kimya öncelikli
    sector_text = str(industry_data.get("sector", "")).lower()
    priority_sectors = ["otomotiv", "automotive", "energy", "enerji", "battery", "batarya", "chemical", "kimya"]
    s_val = 1.0 if any(s in sector_text for s in priority_sectors) else 0.4

    # 4. T: Teknik Karmaşıklık (Technical Complexity) - Ağırlık: 0.22
    # Hat tipi veya ekipman anahtar kelimeleri varsa yüksek puan
    t_val = 1.0 if industry_data.get("line_type") or industry_data.get("equipment_keywords") else 0.5

    # 5. U: Zaman Penceresi (Time Window) - Ağırlık: 0.12
    # Timeline bilgisi varsa sinyal kalitesi yüksektir
    u_val = 1.0 if signals_data.get("timeline") else 0.4

    # 6. C: Kaynak Güveni (Source Trust) - Ağırlık: 0.11
    # IR/Press Release tam puan; saygın medya orta puan
    source_url = source_url.lower()
    if "press" in source_url or "ir" in source_url:
        c_val = 1.0
    elif any(s in source_url for s in ["reuters", "bloomberg", "wsj", "ft.com"]):
        c_val = 0.8
    else:
        c_val = 0.5

    # 7. V: Proje Hacmi (Project Volume) - Ağırlık: 0.10
    # CAPEX veya istihdam verisi varsa hacim belirlidir
    v_val = 1.0 if signals_data.get("capex_usd") or signals_data.get("jobs_impact") else 0.3

    # Döküman 2 - Madde 3.2: Resmi Ağırlıklı Skor Formülü
    score = 100 * (0.22*t_val + 0.18*r_val + 0.15*g_val + 0.12*s_val + 0.12*u_val + 0.11*c_val + 0.10*v_val)

    # Döküman 2 - Madde 3.2: ScoreConfidence ve DataCompleteness Hesaplama
    # Kritik alanlar: company, event_type, country, (from/to), sector
    critical_fields = [
        entities_data.get("company", {}).get("name"),
        article_data.get("event_type"),
        entities_data.get("countries"),
        entities_data.get("from_location") or entities_data.get("to_location"),
        industry_data.get("sector")
    ]
    data_completeness = sum(1 for field in critical_fields if field) / len(critical_fields)
    score_confidence = min(1.0, 0.6 * c_val + 0.4 * data_completeness)

    # Eğer güven puanı çok düşükse skoru cezalandır (Doküman 4'teki ek kural)
    if score_confidence < 0.40:
        score = score * 0.5

    return round(score), round(score_confidence, 2)
    
    
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