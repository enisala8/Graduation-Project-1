"""Örnek proje Excel'ini üretir: uv run python scripts/make_sample_excel.py"""
from pathlib import Path

from openpyxl import Workbook

HEADERS = ["ID", "Görev", "Sorumlu_Mail", "Başlangıç_Tarihi", "Bitiş_Tarihi", "Bağımlı_Olduğu_ID", "Durum"]

# (id, görev, sorumlu, başlangıç, bitiş, bağımlı olduğu görev id'leri, durum)
ROWS = [
    (1, "Gereksinim Analizi", "ayse@example.com", "2026-11-02", "2026-11-13", "", "Tamamlandı"),
    (2, "UI/UX Tasarımı", "mehmet@example.com", "2026-11-16", "2026-11-27", "1", "Devam Ediyor"),
    (3, "Veritabanı Şeması", "ahmet@example.com", "2026-11-16", "2026-11-20", "1", "Tamamlandı"),
    (4, "Backend API Geliştirme", "ahmet@example.com", "2026-11-23", "2026-12-11", "3", "Devam Ediyor"),
    (5, "Mobil Arayüz Geliştirme", "zeynep@example.com", "2026-12-14", "2026-12-31", "2, 4", "Bekliyor"),
    (6, "Entegrasyon Testleri", "can@example.com", "2027-01-04", "2027-01-08", "4, 5", "Bekliyor"),
    (7, "Güvenlik Denetimi", "selin@example.com", "2026-12-14", "2026-12-23", "4", "Bekliyor"),
    (8, "Kullanıcı Kabul Testi", "can@example.com", "2027-01-11", "2027-01-22", "6, 7", "Bekliyor"),
    (9, "Mağaza Yayını", "zeynep@example.com", "2027-01-25", "2027-01-29", "8", "Bekliyor"),
]

out = Path(__file__).resolve().parent.parent / "data" / "ornek_proje.xlsx"
wb = Workbook()
ws = wb.active
ws.title = "Plan"
ws.append(HEADERS)
for r in ROWS:
    ws.append(list(r))
wb.save(out)
print(f"yazıldı: {out}")
