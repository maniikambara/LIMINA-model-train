# LIMINA

Sistem peringatan dini risiko suspensi saham di Bursa Efek Indonesia (BEI).
LIMINA menghitung ulang kriteria risiko suspensi yang dipublikasikan BEI dari
data di Supabase, lalu menampilkan emiten yang bergerak mendekati ambang batas
tersebut sebelum label resminya terbit.

LIMINA bukan nasihat investasi, bukan prediksi kebangkrutan atau kecurangan,
dan bukan pengganti pengumuman resmi BEI.

Dibuat untuk Sectors Hackathon 2026, Track 03 Market Intelligence.

## Dua pipeline

| | **Produksi** (utama) | **Arsip** |
|---|---|---|
| Kode | `sectors_fetcher/`, `preprocessing/notebook/` | `limina/`, `notebooks/`, `tests/` |
| Model | Logistic Regression (baseline dan tertuning), Random Forest, Blend LR+RF; semua memakai class weighting; model dengan Average Precision CV tertinggi dipilih otomatis | Logistic Regression vs. gradient boosting; fallback Isolation Forest / rule-based |
| Keluaran | `output/` (di-commit balik oleh CI) | `artifacts/` |
| Workflow | `retrain-random-forest.yml` (aktif) | `retrain-limina-main.yml` (manual) |
| Status | Berhasil melatih model | Bug diketahui: `data_complete==1` bisa kosong; watchlist nyaris tidak beririsan dengan emiten yang pernah suspensi |

Pipeline arsip dipertahankan sebagai referensi; ia punya test suite (`tests/`)
dan modul inti (`limina/`) dengan pemeriksaan point-in-time dan kebocoran yang lebih ketat.

## Struktur

```
sectors_fetcher/            fetch Sectors API, baca Supabase, LiminaScoringService
  storage/                  SupabaseStorage (jalur baca)
  ensemble.py               BlendedClassifier
preprocessing/notebook/     pipeline produksi: 01_ambil_data, eda_and_feature_engineering, modeling_and_evaluation
output/                     dataset, scores.json, backtest.json, model *.joblib
api/                        FastAPI (GET /scores, /scores/{symbol}, /health)
limina/  notebooks/  tests/ pipeline arsip
data/labels/                taksonomi alasan suspensi (A/B/C)
artifacts/                  keluaran pipeline arsip
docs/                       PANDUAN-FASTAPI.md, README-pipeline-random-forest.md
.github/workflows/          4 workflow
```

## 1. Persiapan

```
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Python 3.11 atau lebih baru.

Salin `.env.example` (root, pipeline arsip) dan `sectors_fetcher/.env.example`
(pipeline produksi; menambah `SECTORS_API_KEY`) menjadi `.env`, lalu isi
nilainya. Berkas `.env` sudah masuk `.gitignore`.

Tabel Supabase yang dibaca (nama tabel/kolom diatur di `sectors_fetcher/config.py`
dan `limina/config.py`):

| Tabel | Kolom |
|---|---|
| `quarterly_financials` | symbol, report_date, revenue, earnings, total_equity, total_liabilities, total_assets, total_debt, operating_cash_flow, free_cash_flow |
| `daily_transaction` | symbol, date, close, volume, market_cap |
| `daily_full_universe_close` | symbol, date, close, volume, market_cap |
| `free_float_snapshot` | symbol, snapshot_date, free_float, sub_sector |
| `company_overview` | symbol, company_name, sector, sub_sector, board |
| `stock_suspensions` | symbol, suspension_date, reason, pdf_url |

## 2. GitHub Actions

Hanya `retrain-random-forest.yml` yang jalan otomatis; tiga lainnya hanya bisa
dipicu manual (`workflow_dispatch`). Secrets: `SUPABASE_URL`, `SUPABASE_KEY`,
dan `SECTORS_API_KEY` (hanya untuk workflow fetch).

1. **`retrain-random-forest.yml`** (aktif, harian 15:00 UTC): menjalankan tiga
   notebook produksi, lalu meng-commit `output/` dan notebook yang dieksekusi
   ke `main` (hanya kalau semuanya sukses).
2. **`retrain-limina-main.yml`** (manual): menjalankan `notebooks/01`-`05` dan
   meng-commit `artifacts/`.
3. **`fetch-sectors-to-supabase.yml`** (manual): `python -m sectors_fetcher.main`.
   Masih gagal jika dipicu, karena enam modul `storage/save_*.py` (jalur tulis)
   belum dibuat.
4. **`lint.yml`** (manual): cek sintaks modul Python dan sel notebook.

## 3. Pipeline arsip

1. `01_ambil_data`: unduh enam tabel ke `data/raw/`.
2. `02_preprocessing_dan_normalisasi`: klasifikasi alasan suspensi, bangun `data/panel.csv` dan snapshot.
3. `03_pelatihan_model`: Logistic Regression + gradient boosting; fallback Isolation Forest / rule-based.
4. `04_evaluasi_model`: Precision@20, Recall@90 hari, AUC, `artifacts/backtest.json`.
5. `05_penilaian_dan_artefak`: skor seluruh emiten hari ini, `artifacts/scores.json`.

Pengujian: `pytest tests/ -v`.

## 4. Pipeline produksi

Dokumentasi lengkap: `docs/README-pipeline-random-forest.md`. Ringkasan
`modeling_and_evaluation.ipynb`:

- 14 fitur (11 indikator + `earnings_margin`, `fcf_margin`, `ocf_to_debt`).
- Imputasi median di dalam tiap Pipeline (hanya dari fold train).
- Repeated `StratifiedGroupKFold` per emiten (`cv_repeated`, 3x) untuk tuning dan perbandingan.
- Metrik utama: Average Precision dan Precision@Top20%, bukan akurasi.

## 5. FastAPI

```
export SUPABASE_URL=...
export SUPABASE_KEY=...
uvicorn api.main:app --reload --port 8000
```

Swagger UI di `http://localhost:8000/docs`. Detail dan deploy: `docs/PANDUAN-FASTAPI.md`.

## 6. Keterbatasan

- Jalur tulis Supabase (`storage/save_*.py`) dan `sql/schema.sql` belum ada.
- `docs/rancangan/` dan dokumen `docs/LIMINA-*.md` dirujuk di beberapa modul tetapi tidak ada di repo.
- Cakupan data saat ini hanya memuat segelintir emiten dengan riwayat suspensi, sehingga metrik CV bervariasi antar run.
