# Chronos Agent

Yöneticinin Gmail hesabına bağlanıp proje yazışmalarını izleyen, proje iletişimini proje planıyla (Excel) karşılaştırıp riskleri tespit eden ve aksiyon taslağı üreten, **yönetici onayı olmadan hiçbir şey göndermeyen** yapay zeka ajanı. İTÜ Bilgisayar Mühendisliği bitirme projesi (BLG 4901E/4902E).

## Nasıl çalışır?

```
Excel (proje planı) ──► Proje Hafızası (JSON, SQLite)
                                  │
Gmail (yönetici hesabı) ──► Mail ──► LLM (plan + mail birlikte) ──► Sınıflandırma + Taslak
                                                                      │
                                              React Dashboard: Onayla / Reddet
                                                                      │
                                            Onaylanırsa: Gmail gönder / Calendar daveti
```

## Teknoloji

| Katman | Seçim |
|---|---|
| LLM | Groq veya Gemini API (model adı `.env`'den okunur, bkz. `docs/GELISTIRME_REHBERI.md` §3) |
| Backend | Python 3.12, FastAPI, pandas + openpyxl, Pydantic, SQLite |
| Frontend | React (Vite) + Tailwind CSS |
| Entegrasyon | Gmail API, Google Calendar API (geliştirme sırasında sahte "mock" sağlayıcı) |

## Dokümanlar

- [docs/GELISTIRME_REHBERI.md](docs/GELISTIRME_REHBERI.md): güncel mimari, yol haritası, riskler ve orijinal öneriden yapılan düzeltmeler
- `Chronos Agent v2.pdf` / `.docx`: **güncel** proje önerisi
- `Chronos Agent.pdf` / `.docx`: orijinal ilk öneri (değiştirilmedi)
- `Fundamentals.pdf`: bölümün bitirme projesi kuralları

## Durum

Aşama 0-4 tamam: Excel proje hafızası, LLM analizi (Gemini), router, kart ve onay API'si (`backend/`, mock mail sağlayıcıyla) ve React dashboard (`frontend/`). Sıradaki: Aşama 5, Gmail/Calendar entegrasyonu (`docs/GELISTIRME_REHBERI.md` §5).

Çalıştırmak için iki ayrı terminal:

```bash
cd backend && cp .env.example .env   # .env'e LLM anahtarını ve model adını yaz
uv run uvicorn app.main:app --reload # http://localhost:8000 (API dokümanı: /docs)
```

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
```

Panelde önce Excel'i yükle (`backend/data/ornek_proje.xlsx`), sonra "Demo mailleri yükle". Testler: `cd backend && uv run pytest`.
