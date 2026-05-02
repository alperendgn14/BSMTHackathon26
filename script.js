const API_BASE = "http://localhost:5500/api";
let allNews = [];

// Sayfa yüklendiğinde verileri getir
document.addEventListener('DOMContentLoaded', () => {
    fetchRSSList();
    fetchNews();
});

// 1. Haberleri Çek (F10)
async function fetchNews() {
    try {
        const res = await fetch(`${API_BASE}/news`);
        allNews = await res.json();
        renderNews(allNews);
    } catch (err) { console.error("Haberler yüklenemedi:", err); }
}

// 2. RSS Listesini Çek (F2)
async function fetchRSSList() {
    try {
        const res = await fetch(`${API_BASE}/rss`);
        const list = await res.json();
        const container = document.getElementById('rssList');
        container.innerHTML = list.map(rss => `
            <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition group">
                <div class="flex items-center gap-3 overflow-hidden">
                    <i class="fas fa-rss text-orange-500 text-xs"></i>
                    <span class="text-sm font-medium truncate text-gray-700">${rss.name}</span>
                </div>
            </div>
        `).join('');
    } catch (err) { console.error("RSS listesi alınamadı:", err); }
}

// 3. Yeni RSS Ekle (F1, F3)
async function addRSS() {
    const input = document.getElementById('rssInput');
    const error = document.getElementById('rssError');
    if (!input.value) return;

    try {
        const res = await fetch(`${API_BASE}/rss`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: input.value })
        });
        const data = await res.json();
        if (data.error) {
            error.innerText = data.error;
            error.classList.remove('hidden');
        } else {
            input.value = "";
            error.classList.add('hidden');
            fetchRSSList();
        }
    } catch (err) { console.error("RSS eklenemedi:", err); }
}

// 4. Haberleri Yenile (F4)
async function refreshNews() {
    const overlay = document.getElementById('loadingOverlay');
    overlay.classList.remove('hidden');
    try {
        await fetch(`${API_BASE}/refresh`, { method: 'POST' });
        fetchNews();
        document.getElementById('lastUpdate').innerText = `Son güncelleme: ${new Date().toLocaleTimeString()}`;
    } catch (err) { alert("Yenileme başarısız!"); }
    finally { overlay.classList.add('hidden'); }
}

// 5. Haberleri Ekrana Bas (F7b)
function renderNews(news) {
    const container = document.getElementById('newsFeed');
    container.innerHTML = news.map(item => {
        let scoreClass = "score-none";
        if (item.score >= 80) scoreClass = "score-high";
        else if (item.score >= 65) scoreClass = "score-medium";
        else if (item.score >= 50) scoreClass = "score-low";

        return `
            <div class="news-card bg-white p-6 rounded-xl shadow-sm border ${scoreClass}">
                <div class="flex justify-between items-start mb-4">
                    <span class="text-[10px] font-black uppercase px-2 py-1 bg-gray-100 text-gray-500 rounded">${item.event_type}</span>
                    <span class="text-lg font-black ${item.score >= 80 ? 'text-green-600' : 'text-blue-600'}">${item.score}/100</span>
                </div>
                <h3 class="font-bold text-gray-900 mb-2 leading-snug">${item.original_title}</h3>
                <p class="text-sm text-gray-600 mb-4 line-clamp-3 italic">"${item.summary_tr}"</p>
                
                <div class="grid grid-cols-2 gap-3 mb-4 text-xs">
                    <div class="flex items-center gap-2 text-gray-500">
                        <i class="fas fa-building w-4"></i> <strong>${item.company || 'Bilinmiyor'}</strong>
                    </div>
                    <div class="flex items-center gap-2 text-gray-500">
                        <i class="fas fa-industry w-4"></i> <strong>${item.sector || 'Genel'}</strong>
                    </div>
                    <div class="flex items-center gap-2 text-blue-600 font-bold">
                        <i class="fas fa-map-marker-alt w-4"></i> ${item.from_location || '?'} ➔ ${item.to_location || '?'}
                    </div>
                </div>

                <div class="flex justify-between items-center pt-4 border-t border-dashed">
                    <span class="text-[10px] text-gray-400">${item.published_date}</span>
                    <a href="${item.url}" target="_blank" class="text-blue-600 text-xs font-bold hover:underline">Haber Kaynağı <i class="fas fa-external-link-alt ml-1"></i></a>
                </div>
            </div>
        `;
    }).join('');
}

// 6. Basit Arama Filtresi (F9)
function filterNews(query) {
    const filtered = allNews.filter(n => 
        n.original_title.toLowerCase().includes(query.toLowerCase()) || 
        (n.company && n.company.toLowerCase().includes(query.toLowerCase())) ||
        n.summary_tr.toLowerCase().includes(query.toLowerCase())
    );
    renderNews(filtered);
}