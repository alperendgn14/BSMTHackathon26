# BIOS AI News Agent

**Avrupa Endüstriyel Haber Tarama Ajanı**

Bu proje, özellikle Avrupa bölgesindeki endüstriyel yatırımları, yeni fabrika açılışlarını ve kapasite artışlarını otonom olarak takip eden, bu verileri anlamlandıran ve B2B iş akışları için aksiyona dönüştüren bir yapay zeka ajanıdır.

* **Kaynak Kod:** [GitHub Repo Linki Buraya Eklenecek]
* **Demo:** [https://bsmthackathon26.onrender.com/](https://bsmthackathon26.onrender.com/)
* **Sunum:** Proje sunum dosyası (PDF/PPTX) repo içerisinde yer almaktadır ve 14:00–15:00 arası jüri önünde sunulacaktır.

---

## Kısa Mimari Açıklaması
Sistem, Avrupa endüstriyel pazarındaki gelişmeleri otonom olarak izlemek ve analiz etmek üzere üç ana katmandan oluşan bir mimariyle tasarlanmıştır:

1. **Veri Toplama Katmanı (Collector):** Arka planda 7/24 çalışan `APScheduler`, tanımlı Avrupa odaklı ve küresel RSS kaynaklarını periyodik olarak tarar. Yeni haberleri `Feedparser` yardımıyla yakalayıp JSON tabanlı yerel veritabanına işler.
2. **Ajan & Analiz Katmanı (LLM):** Yakalanan ham veriler, Groq API üzerinden Llama 3.1 70B modeline gönderilir. Yapay zeka ajanı; Avrupa merkezli haberleri özetler, yatırımın kıtadaki stratejik önemine göre "BIOS-fit" skoru (0-100) verir, projelerin CAPEX (tahmini bütçe) analizini yapar ve tedarik rotalarını (Örn: Almanya -> Polonya) çıkarır.
3. **Kullanıcı ve Aksiyon Katmanı (UI):** Kullanıcılar, HTML/JS ve Tailwind CSS ile hazırlanan arayüz üzerinden verileri filtreler ve Leaflet.js destekli harita üzerinden Avrupa'daki yatırım yoğunluklarını (Heatmap) izler. Sistem, ilgili yatırımla temas kurmak için tek tıkla hedef odaklı B2B mail taslağı oluşturma ve RAG tabanlı sohbet otomasyonu sunar.

---

## Kullanılan Teknolojiler
* **Backend:** Python, Flask
* **Yapay Zeka (LLM):** Groq API, Llama 3.1 70B (Agentic analiz, skorlama ve metin üretimi)
* **Otomasyon & Veri Toplama:** APScheduler, Feedparser
* **Frontend:** HTML5, Tailwind CSS, Vanilla JavaScript
* **Haritalandırma & Görselleştirme:** Leaflet.js, Leaflet.heat (Avrupa lokasyon analizleri için)

---

## Gereken API Anahtarları
Projeyi yerel ortamda çalıştırmak için Groq Cloud üzerinden alınmış ücretsiz bir API anahtarına ihtiyacınız bulunmaktadır.
* `GROQ_API_KEY`: Llama 3.1 modeline erişim, Avrupa haberlerinin analizi ve RAG süreçlerini yürütebilmek için gereklidir.

---

## Kurulum Adımları
Projeyi kendi bilgisayarınızda çalıştırmak için aşağıdaki adımları sırasıyla izleyin:

**Adım 1: Depoyu Klonlayın**
Terminalinizi açın ve projeyi yerel bilgisayarınıza indirin:
```bash
git clone <repo-linki>
cd <repo-klasoru>

Adım 2: Gerekli Kütüphaneleri Yükleyin
Python ortamınızda projenin sorunsuz çalışması için gerekli olan bağımlılıkları kurun:
```bash
pip install -r requirements.txt

Adım 3: Ortam Değişkenlerini (API Anahtarı) Ayarlayın
Projenin ana dizininde .env adında yeni bir dosya oluşturun. İçerisine Groq üzerinden aldığınız API anahtarını aşağıdaki formatta ekleyin (Bu adım, yapay zeka analizlerinin çalışması için kritik öneme sahiptir):
GROQ_API_KEY=gsk_sizin_api_anahtariniz_buraya


Adım 4: Uygulamayı Başlatın
Bağımlılıklar ve API anahtarı hazır olduğunda Flask sunucusunu ve otonom tarama motorunu başlatın:
```bash
python app.py

Örnek RSS Listesi (Test Kaynakları)

Arayüzdeki "Kaynaklar" bölümünden sistemi test etmek için, Avrupa ve küresel endüstriyel gelişmeleri takip edebileceğiniz aşağıdaki RSS kaynaklarını kullanabilirsiniz:

    Reuters - European Business News: (Avrupa endüstri ve iş dünyası haberleri)
    http://feeds.reuters.com/reuters/businessNews

    Yahoo Finance Europe: (Avrupa merkezli şirket yatırımları ve CAPEX sinyalleri)
    https://finance.yahoo.com/news/rss

    CNBC - Europe News: (Kıtadaki ekonomik gelişmeler ve yeni tesis duyuruları)
    https://search.cnbc.com/rs/search/combinedcms/view.xml?profile=120000000&id=10001147

    TechCrunch - Hardware & Manufacturing: (Teknoloji ve donanım üretimi yatırımları)
    https://techcrunch.com/feed/