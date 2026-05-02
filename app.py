from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
import io
import feedparser
import csv
from flask import Response
from datetime import datetime, timezone

#collector.py dosyasından fonksiyonları içe aktar
from collector import analyze_with_llama3_api, save_to_db, DB_FILE

app = Flask(__name__)
CORS(app) #teammatenin hata almaması için

RSS_DB_FILE = "rss_data.json"
RSS_SOURCES_FILE = "rss_sources.json"

#helper fonksiyonlar

def get_rss_list():
    if(os.path.exists(RSS_DB_FILE)):
        with open (RSS_DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
        return[]
    
def save_rss_list(rss_list):
    with open(RSS_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(rss_list, f, ensure_ascii=False, indent=4)
        
        
# endpointler

#kayıtlı haberleri getir.

@app.route('/api/news', methods=['GET'])
def get_news():
    if not os.path.exists(DB_FILE):
        return jsonify([]), 200
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # F9: Anahtar kelime arama (Başlıkta veya özette)
    q = request.args.get('q', '').lower()
    # F8: Olay tipi filtresi
    event = request.args.get('event')
    # F8: Minimum skor filtresi
    min_s = request.args.get('min_score', type=int)

    filtered = [
        item for item in data 
        if (not q or q in item.get('original_title','').lower() or q in item.get('summary_tr','').lower()) and
           (not event or item.get('event_type') == event) and
           (not min_s or item.get('score', 0) >= min_s)
    ]
    # En yüksek skorlu olanı en başta göster
    return jsonify(sorted(filtered, key=lambda x: x.get('score', 0), reverse=True)) # Skora göre sırala




# --- F2: RSS KAYNAĞI SİLME ---
@app.route('/api/rss/<rss_id>', methods=['DELETE'])
def delete_rss_source(rss_id):
    if not os.path.exists(RSS_SOURCES_FILE):
        return jsonify({"error": "Kaynak bulunamadı"}), 404

    with open(RSS_SOURCES_FILE, "r", encoding="utf-8") as f:
        sources = json.load(f)

    new_sources = [s for s in sources if s['id'] != rss_id]
    
    with open(RSS_SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(new_sources, f, ensure_ascii=False, indent=4)

    return jsonify({"message": "Kaynak silindi."}), 200
    
    
    
#kaynakları getir
@app.route('/api/rss', methods=['GET'])
def list_rss():
    return jsonify(get_rss_list()), 200





#yeni kaynak ekle
@app.route('/api/rss', methods=['POST'])
def add_rss():
    data = request.json
    new_url = data.get("url")
    
    if not new_url:
        return jsonify({"error": "URL gönderilmedi!"}), 400
    
    # f3 gereksinimi, geçerlilik kontrolü
    feed = feedparser.parse(new_url)
    if feed.bozo != 0:
        return jsonify({"error": "Geçersiz RSS formatı veya bağlantı hatası!"}), 400
    
    rss_list = get_rss_list()
    #aynı url kontrolü
    if any(r['url'] == new_url for r in rss_list):
        return jsonify({"error": "Bu URL zaten kayıtlı!"}), 400
    
    rss_list.append({"url": new_url, "name": feed.feed.get('title', 'İsimsiz Kaynak')})
    save_rss_list(rss_list)
    
    return jsonify({"message": "RSS başarıyla eklendi", "rss_list": rss_list}), 201






# haberleri yenile/çek
@app.route('/api/refresh', methods=['POST'])
def refresh_news():
    rss_list = get_rss_list()
    if not rss_list:
        return jsonify({"error": "Önce RSS kaynağı eklemelisiniz!"}), 400
    
    #tüm kayıtlı rss'leri çek
    for source in rss_list:
        feed = feedparser.parse(source['url'])
        
        for entry in feed.entries[:2]: # Hackathon hızında test için ilk 2 haber
            ai_json_result = analyze_with_llama3_api(entry.title)
            try:
                parsed_json = json.loads(ai_json_result)
                parsed_json["original_title"] = entry.title
                parsed_json["url"] = entry.link
                parsed_json["published_date"] = entry.get('published', '')
                parsed_json["source_rss"] = source['url']
                
                save_to_db(parsed_json)
            except Exception as e:
                print("JSON ayrıştırma hatası:", e)
                
    return jsonify({"message": "Tüm kaynaklardan veriler çekildi ve AI tarafından işlendi!"}), 200






@app.route('/api/export', methods=['GET'])
def export_csv():
    if not os.path.exists(DB_FILE):
        return "veri yok", 404
    
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # CSV oluştur
    output = io.StringIO()
    writer = csv.writer(output)
    
    #başlıklar
    writer.writerow(["Tarih", "Olay Tipi", "Sirket", "Nereden", "Nereye", "Sektor", "Skor", "Baslik", "Link"])
    
    for row in data:
        writer.writerow([
            row.get("published_date", ""),
            row.get("event_type", ""),
            row.get("company", ""),
            row.get("from_location", ""),
            row.get("to_location", ""),
            row.get("sector", ""),
            row.get("score", 0),
            row.get("original_title", ""),
            row.get("url", "")
        ])
        
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=bios_fit_rapor.csv"}
    )






#F17 endpoint: Şirket bazlı zaman tüneli
@app.route('/api/timeline/<company_name>', methods=['GET'])
def get_company_timeline(company_name):
    if not os.path.exists(DB_FILE):
        return jsonify([]), 200
    
    with open(DB_FILE,"r", encoding="utf-8") as f:
        data = json.load(f)

    # sadece o şirketle ilgili olan haberlerin filtrelenip sıralanması.
    company_news = [item for item in data if item.get('company') and company_name.lower() in item.get('company').lower()]
    
    return jsonify(company_news), 200


@app.route('/api/crm/send', methods=['POST'])
def send_to_crm():
    news_data = request.json

    # Gerçek bir CRM'e (Örn: HubSpot, Salesforce) gider gibi simüle et
    print(f"🔄 CRM ENTEGRASYONU TETİKLENDİ!")
    print(f"📦 Müşteri (Account) Oluşturuluyor: {news_data.get('company')}")
    print(f"🎯 Fırsat (Lead) Açılıyor: {news_data.get('event_type')} - Skor: {news_data.get('score')}")    
    
    # Başarı yanıtı dön
    return jsonify({
        "status": "success",
        "message": "Kayıt başarıyla CRM'e (Lead olarak) aktarıldı!",
        "crm_id": "OPP-98765"
    }), 200




# F18: Harita (Map) İçin "From - To" API'si
@app.route('/api/map-data', methods=['GET'])
def get_map_data():
    if not os.path.exists(DB_FILE):
        return jsonify([]), 200
        
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # Sadece hem nereden hem de nereye lokasyonu dolu olanları gönder
    map_items = [item for item in data if item.get('from_location') and item.get('to_location')]
    
    return jsonify(map_items), 200

    

@app.route('/api/reports/weekly', methods=['GET'])
def get_weekly_report():
    if not os.path.exists(DB_FILE): return jsonify({"error": "Veri yok"}), 404
    
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Sadece yüksek skorlu son 10 haberi al[cite: 4, 6]
    top_news = sorted(data, key=lambda x: x.get('score', 0), reverse=True)[:10]
    titles = [n.get('original_title') for n in top_news]
    
    # LLM'den bu haberleri stratejik bir bültene dönüştürmesini iste
    report_prompt = f"Aşağıdaki endüstriyel haberlerden BIOS yönetimi için stratejik bir haftalık bülten özeti oluştur: {titles}"
    
    # analyze_with_llama3_api fonksiyonunu burada rapor için çağırabilirsin
    report_content = analyze_with_llama3_api(report_prompt) 
    
    return jsonify({"report": report_content, "date": datetime.now().strftime("%Y-%m-%d")}), 200



@app.route('/api/stats', methods=['GET'])
def get_stats():
    if not os.path.exists(DB_FILE): return jsonify({}), 200
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    stats = {
        "by_sector": {},
        "by_country": {},
        "total_opportunity_value": 0 # CAPEX toplamı
    }

    for item in data:
        # Sektör bazlı dağılım
        sector = item.get("industry", {}).get("sector", "Bilinmiyor")
        stats["by_sector"][sector] = stats["by_sector"].get(sector, 0) + 1
        
        # Ülke bazlı dağılım
        for country in item.get("entities", {}).get("countries", []):
            stats["by_country"][country] = stats["by_country"].get(country, 0) + 1
            
        # Toplam Yatırım Hacmi (CAPEX)
        capex = item.get("signals", {}).get("capex_usd", 0)
        if capex: stats["total_opportunity_value"] += capex

    return jsonify(stats)


@app.route('/health', methods=['GET'])
def health_check():
    health_status = {
        "status": "healthy",
        "database": "connected" if os.path.exists(DB_FILE) else "not_found",
        "timestamp": datetime.now().isoformat(),
        "version": "v1.0-MVP" # SOW 1.2 sürüm takibi
    }
    return jsonify(health_status), 200


def is_valid_rss(url):
    """F3: RSS bağlantısının geçerliliğini kontrol eder."""
    try:
        # feedparser ile parse etmeyi dene
        feed = feedparser.parse(url)
        # bozo == 1 ise veya haber listesi boşsa geçersiz kabul et
        if feed.bozo == 1 or len(feed.entries) == 0:
            return False
        return True
    except Exception:
        return False










from apscheduler.schedulers.background import BackgroundScheduler

def auto_fetch_job():
    print("⏰ [Cron Job] Arka planda RSS haberleri otomatik taranıyor...")
    # refresh_news() fonksiyonunun içindeki mantığı buraya çağır
    
scheduler = BackgroundScheduler()
scheduler.add_job(func=auto_fetch_job, trigger="interval", minutes=15)
scheduler.start()



if __name__ == "__main__":
    print("🚀 Backend API Sunucusu Çalışıyor: http://localhost:5500")
    app.run(debug=True, port=5500)
                
    
        
    
    


    