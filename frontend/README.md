# Chronos Agent: Dashboard

React (Vite) + Tailwind CSS. Backend'e `http://localhost:8000` üzerinden bağlanır (`VITE_API_URL` ile değiştirilebilir).

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # üretim derlemesi (dist/)
```

- `src/api.js`: backend istekleri ve hata mesajı çözümleme
- `src/App.jsx`: ana ekran, sekmeler, periyodik yoklama, tema
- `src/components/CardItem.jsx`: karar kartı (etki analizi, taslak düzenleme, onay/ret)
- `src/components/ProjectBar.jsx`: Excel yükleme ve demo mailleri başlatma
- `src/labels.js`: rozet metinleri/renkleri ve tarih biçimleri
