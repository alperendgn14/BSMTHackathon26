import subprocess
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json
import os
import io
import feedparser
import csv
from flask import Response
from datetime import datetime, timezone
import uuid
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
#collector.py dosyasından fonksiyonları içe aktar
from collector import analyze_with_llama3_api, save_to_db, DB_FILE

app = Flask(__name__)
CORS(app) #teammatenin hata almaması için


@app.route('/')
def index():
    # index.html dosyan app.py ile aynı klasördeyse '.' kullanılır
    return send_from_directory('.', 'index.html')


RSS_DB_FILE = "rss_data.json"
RSS_SOURCES_FILE = "rss_sources.json"

#helper fonksiyonlar

@app.route('/api/start-collector', methods=['POST'])
def start_collector():
    try:
        # Popen kullanarak collector'ı arka planda başlatıyoruz.
        # Bu sayede site donmaz, collector işini yaparken site çalışmaya devam eder.
        subprocess.Popen(["python", "collector.py"])
        
        return jsonify({
            "status": "success", 
            "message": "Haber toplama işlemi arka planda başlatıldı. Birazdan liste güncellenecek."
        }), 202
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500




def get_rss_list():
    try:
        # F11: Dosya kontrolü ve kalıcılık
        if not os.path.exists('rss_sources.json'):
            return []
        
        with open('rss_sources.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Veri None ise veya liste değilse boş liste dön
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, Exception):
        return []
    
def save_rss_list(rss_list):
    with open(RSS_SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(rss_list, f, ensure_ascii=False, indent=4)
        
        
# endpointler

#kayıtlı haberleri getir.

@app.route('/api/news', methods=['GET'])
@app.route('/api/news', methods=['GET'])
def get_news():
    try:
        # rss_data.json dosyasını oku
        if not os.path.exists(RSS_DB_FILE):
            return jsonify([])

        with open(RSS_DB_FILE, 'r', encoding='utf-8') as f:
            all_news = json.load(f)

        # Haberleri en yeniden en eskiye sırala (isteğe bağlı)
        all_news.reverse() 

        return jsonify(all_news)
    except Exception as e:
        return jsonify({"error": str(e)}), 500




# --- F2: RSS KAYNAĞI SİLME ---
@app.route('/api/rss/<id>', methods=['DELETE'])
def delete_rss(id):
    try:
        if not os.path.exists(RSS_SOURCES_FILE):
            return jsonify({"error": "Dosya bulunamadı"}), 404

        with open(RSS_SOURCES_FILE, 'r', encoding='utf-8') as f:
            sources = json.load(f)

        # ID'si eşleşmeyenleri tut, eşleşeni listeden çıkar
        new_sources = [s for s in sources if s.get('id') != id]

        with open(RSS_SOURCES_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_sources, f, indent=4, ensure_ascii=False)

        return jsonify({"message": "Kaynak başarıyla silindi", "sources": new_sources}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
    
#kaynakları getir
@app.route('/api/rss', methods=['GET'])
def list_rss():
    return jsonify(get_rss_list()), 200





#yeni kaynak ekle
@app.route('/api/rss', methods=['POST'])
def add_rss():
    data = request.get_json()
    # Kayıtları MUTLAKA rss_sources.json dosyasına yönlendiriyoruz
    try:
        sources = []
        if os.path.exists("rss_sources.json") and os.stat("rss_sources.json").st_size > 0:
            with open("rss_sources.json", 'r', encoding='utf-8') as f:
                sources = json.load(f)

        sources.append({
            "id": str(uuid.uuid4())[:8],
            "url": data['url'],
            "name": data.get('name', 'Yeni Kaynak')
        })

        with open("rss_sources.json", 'w', encoding='utf-8') as f:
            json.dump(sources, f, indent=4, ensure_ascii=False)

        return jsonify(sources), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500






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


@app.route('/api/rss', methods=['GET', 'POST'])
def handle_rss():
    if request.method == 'POST':
        print("--- POST ISTEGI GELDI ---") # Terminalde takip için
        data = request.get_json()
        new_url = data.get("url")
        
        # Daha önce yazdığımız ekleme mantığı buraya:
        rss_list = get_rss_list()
        # ... (Geçerlilik ve kopya kontrolü) ...
        
        new_entry = {"id": str(uuid.uuid4())[:8], "url": new_url, "name": "Yeni Kaynak"}
        rss_list.append(new_entry)
        save_rss_list(rss_list)
        
        return jsonify({"message": "Eklendi", "rss_list": rss_list}), 201
    
    else:
        # GET isteği gelirse listeyi döndür
        return jsonify(get_rss_list())


@app.route('/api/chat', methods=['POST'])
def chat_with_agent():
    try:
        data = request.json
        context_text = data.get('context', '')
        user_question = data.get('question', '')

        prompt = f"""Sen endüstriyel yatırımları analiz eden profesyonel bir yapay zeka ajanısın. 
Aşağıdaki 'HABER METNİ'ni referans alarak kullanıcının 'SORU'suna kısa, net ve profesyonel bir Türkçe ile cevap ver. 
Eğer sorunun cevabı metinde yoksa "Bu bilgi haber kaynağında bulunmuyor" şeklinde belirt. Asla metin dışı uydurma yapma.

HABER METNİ: {context_text}
SORU: {user_question}"""

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a precise, context-aware Q&A assistant."},
                {"role": "user", "content": prompt}
            ],
            model="gemma2-9b-it", # Hızlı ve token dostu model
        )
        answer = chat_completion.choices[0].message.content
        return jsonify({"answer": answer}), 200
    except Exception as e:
        print(f"Chat Hatası: {e}")
        return jsonify({"error": "Sistem geçici olarak yanıt veremiyor."}), 500





@app.route('/api/generate-email', methods=['POST'])
def generate_email():
    """Seçilen haber için Llama 3.3 70B'den B2B Satış/Temas maili taslağı oluşturur."""
    data = request.json
    context = data.get("context", "")
    
    prompt = f"""Sen üst düzey bir kurumsal satış ve iş geliştirme yöneticisisin. 
Aşağıdaki yatırım haberini okuyan bir Türk firması (BIOS) adına, yatırımı yapacak olan firmanın üst yönetimine (C-Level) profesyonel bir B2B (İşletmeden İşletmeye) temas e-postası yazacaksın.

Amacın: Onların yeni lokasyonlarındaki tedarik zinciri, otomasyon, taşıma veya güvenlik süreçlerinde güçlü bir yerel partner olabileceğimizi vurgulamak.

KURALLAR:
1. Konu başlığı çarpıcı ve profesyonel olmalı (Örn: "KONU: [Şirket] - [Lokasyon] Yatırımınız ve Stratejik Partnerlik").
2. Hitap profesyonel olmalı (Örn: "Sayın [Şirket] Yönetim Kurulu,").
3. E-posta nazik, değer odaklı ve doğrudan hedefe yönelik olmalı. Çok uzun olmamalı.
4. E-postanın sonuna "Saygılarımla, [Adınız/Unvanınız]" gibi bir imza alanı bırak.
5. ASLA JSON formatı kullanma, sadece e-postanın metnini Markdown formatında dön.

YATIRIM BAĞLAMI:
{context}
"""
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Sen usta bir B2B satış yöneticisisin. Sadece mail taslağı metni üretirsin."},
                {"role": "user", "content": prompt}
            ],
            model="gemma2-9b-it", # Güçlü model
        )
        return jsonify({"email_draft": chat_completion.choices[0].message.content})
    except Exception as e:
        print(f"Mail API Hatası: {e}")
        return jsonify({"error": "Mail oluşturulamadı."}), 500



@app.route('/api/news', methods=['DELETE', 'OPTIONS'])
@app.route('/api/news', methods=['DELETE'])
def delete_news():
    data = request.json
    news_id = data.get("id")
    
    try:
        if os.path.exists('rss_data.json'):
            with open('rss_data.json', 'r', encoding='utf-8') as f:
                news_list = json.load(f)
        else:
            return jsonify({"error": "Veritabanı bulunamadı."}), 404

        # Haberi tam başlık veya URL üzerinden %100 isabetle filtrele
        filtered_news = [
            n for n in news_list 
            if n.get('article', {}).get('title') != news_id 
            and n.get('source', {}).get('url') != news_id
        ]
        
        # Temizlenmiş listeyi kaydet
        with open('rss_data.json', 'w', encoding='utf-8') as f:
            json.dump(filtered_news, f, ensure_ascii=False, indent=2)
            
        return jsonify({"status": "success", "message": "Haber veritabanından kalıcı olarak yok edildi."})
    except Exception as e:
        print(f"Silme Hatası: {e}")
        return jsonify({"error": "Silme işlemi başarısız oldu."}), 500




@app.route('/api/news/comment', methods=['POST', 'OPTIONS'])
def add_comment():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    data = request.json
    news_id = str(data.get("id", "")).strip()
    comment_text = data.get("comment", "").strip()
    # Yeni dinamik alanlar
    first_name = data.get("first_name", "Anonim").strip()
    last_name = data.get("last_name", "").strip()
    email = data.get("email", "").strip()

    if not news_id or not comment_text:
        return jsonify({"error": "Eksik veri"}), 400

    try:
        news_list = []
        if os.path.exists('rss_data.json'):
            try:
                with open('rss_data.json', 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        news_list = json.loads(content)
            except json.JSONDecodeError:
                pass

        # Dinamik yazar bilgisiyle yorum objesi
        comment_obj = {
            "text": comment_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "author": f"{first_name} {last_name}".strip(),
            "email": email
        }

        updated = False
        for n in news_list:
            title = str(n.get('article', {}).get('title', '')).strip()
            url = str(n.get('source', {}).get('url', '')).strip()
            if news_id == title or news_id == url:
                if 'comments' not in n:
                    n['comments'] = []
                n['comments'].append(comment_obj)
                updated = True
                break

        if updated:
            with open('rss_data.json', 'w', encoding='utf-8') as f:
                json.dump(news_list, f, ensure_ascii=False, indent=2)
            return jsonify({"status": "success", "comment": comment_obj})
        
        return jsonify({"error": "Haber bulunamadı."}), 404
    except Exception as e:
        print(f"Yorum Hatası: {e}")
        return jsonify({"error": "Sunucu hatası."}), 500






if __name__ == "__main__":
    print("🚀 Backend API Sunucusu Çalışıyor: http://localhost:5000")
    app.run(debug=True, port=5000)
                
    
        
    
    


    