from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
import feedparser
import csv
from flask import Response, io

#collector.py dosyasından fonksiyonları içe aktar
from collector import analyze_with_llama3_api, save_to_db, DB_FILE

app = Flask(__name__)
CORS(app) #teammatenin hata almaması için

RSS_DB_FILE = "rss_data.json"

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
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data=json.load(f)
            return jsonify(data), 200
        return jsonify([]), 200
    
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
                
    
        
    
    


    