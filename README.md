# LIMINA

Sistem peringatan dini risiko suspensi saham di Bursa Efek Indonesia (BEI).
LIMINA menghitung ulang kriteria risiko suspensi yang sudah dipublikasikan
BEI secara berkelanjutan dari data yang tersimpan di Supabase, lalu
menampilkan emiten mana yang sedang bergerak mendekati ambang batas
tersebut, lebih cepat daripada label resminya terbit.

LIMINA bukan nasihat investasi, bukan prediksi kebangkrutan atau
kecurangan, dan bukan pengganti pengumuman resmi BEI. Keputusan membeli,
menjual, atau menahan saham sepenuhnya tanggung jawab pengguna sendiri.

Proyek ini sebelumnya dirancang dengan nama kerja AMBANG/AMBA untuk
Sectors Hackathon 2026, Track 03 Market Intelligence.

## Dua pipeline di repo ini

Repo ini adalah gabungan dua branch/proyek yang tadinya terpisah. Tidak
ada berkas yang dihapus saat digabung -- keduanya berjalan berdampingan:

| | Pipeline **produksi** (utama) | Pipeline **arsip** |
|---|---|---|
| Asal | `LIMINA-model-train-feature-random-forest` | `LIMINA-model-train-main` |
| Status | **Berhasil melatih model** -- dipakai sebagai acuan utama | Bug diketahui: `data_complete==1` bisa kosong (lihat `notebooks/03_pelatihan_model.ipynb`), watchlist 12 emiten blue-chip nyaris tidak beririsan dengan emiten yang pernah suspensi |
| Kode | `sectors_fetcher/`, `preprocessing/notebook/` | `limina/`, `notebooks/`, `tests/` |
| Model | Logistic Regression + **Random Forest** (`BalancedRandomForestClassifier`, tuning 2 tahap), model dengan Average Precision CV tertinggi dipilih otomatis | Logistic Regression (utama) vs. gradient boosting (pembanding), plus rule-based/Isolation Forest sebagai fallback |
| Keluaran | `output/` (gitignored, diunggah sebagai artifact CI) | `artifacts/` (sebagian di-commit balik lewat CI dengan `git add -f`) |
| Workflow | `.github/workflows/retrain-random-forest.yml` | `.github/workflows/retrain-limina-main.yml` |
| Dokumentasi asli | `docs/README-pipeline-random-forest.md` (README lengkap branch ini) | Bagian di bawah pada README ini |

Karena pipeline produksi yang terbukti berhasil melatih modelnya,
gunakan itu sebagai jalur utama. Pipeline arsip tetap dipertahankan apa
adanya untuk referensi, riwayat, dan karena berisi test suite (`tests/`)
serta modul inti (`limina/`) yang lebih matang secara arsitektur
(point-in-time enforcement dua lapis, empat pemeriksaan kebocoran,
gerbang keputusan model-vs-rule-based) -- lihat bagian "Metodologi" di
bawah.

## Struktur proyek

```
LIMINA/
  sectors_fetcher/                        pipeline PRODUKSI -- fetch Sectors API + tulis Supabase
    client.py, config.py, main.py           HTTP client, konfigurasi, entry point fetch->Supabase
    supabase_io.py                          pembaca Supabase (baca saja), dipakai notebook 01
    endpoints/                              satu modul per endpoint API (fetch mentah saja)
    features/                               11 indikator turunan (referensi, lihat catatan duplikasi)
    service.py                              AMBAScoringService: preprocessing + inferensi + skor produksi
  preprocessing/notebook/                 pipeline PRODUKSI -- notebook latih
    01_ambil_data.ipynb                     unduh 6 tabel Supabase (baca saja) -> data/raw/
    eda_and_feature_engineering.ipynb       audit data, taksonomi suspensi, feature engineering PIT
    modeling_and_evaluation.ipynb           Logistic Regression + Random Forest + tuning, evaluasi
  output/                                 keluaran pipeline produksi (gitignored): dataset, scores.json,
                                           backtest.json, model *.joblib

  limina/                                 pipeline ARSIP -- kode inti dipakai notebooks/ + tests/
  notebooks/                              pipeline ARSIP -- notebook 01-05 (lihat README lama di bawah)
  tests/                                  pengujian unit (pytest) untuk limina/
  data/labels/taksonomi_alasan_suspensi.json  taksonomi alasan suspensi (A/B/C), dipakai kedua pipeline
  artifacts/                              keluaran pipeline arsip: model terlatih, scores.json, backtest.json

  docs/README-pipeline-random-forest.md   README asli lengkap pipeline produksi (feature-random-forest)
  .github/workflows/
    retrain-random-forest.yml               jadwal retrain pipeline produksi
    retrain-limina-main.yml                 jadwal retrain pipeline arsip
    fetch-sectors-to-supabase.yml           jalur TULIS: Sectors API -> Supabase (lihat catatan di bawah)
    lint.yml                                cek sintaks Python + notebook di tiap push/PR (tidak butuh secrets)
```

## 1. Persiapan

```
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Python 3.11 atau lebih baru (pipeline arsip pernah diuji di 3.12, pipeline
produksi di 3.11 -- lihat masing-masing workflow).

### Isi kredensial

Dua templat `.env.example` tersedia:

- `.env.example` (root) -- dipakai pipeline arsip (`limina/config.py`),
  hanya butuh `SUPABASE_URL`/`SUPABASE_KEY`.
- `sectors_fetcher/.env.example` -- dipakai pipeline produksi, butuh
  tambahan `SECTORS_API_KEY`.

Salin masing-masing jadi `.env` (tanpa akhiran `.example`) di folder yang
sama, lalu isi nilainya. Kedua `.env` sudah masuk `.gitignore`, tidak akan
pernah ikut ter-commit.

> **Catatan keamanan:** saat digabung, berkas `sectors_fetcher/.env` di
> proyek asal (branch `feature-random-forest`) ternyata berisi URL dan key
> Supabase asli (bukan placeholder). Berkas itu **tidak disertakan** ke
> repo/zip hasil gabungan ini -- diganti `sectors_fetcher/.env.example`
> berisi placeholder saja. Kalau key itu sudah pernah dibagikan/di-commit
> di tempat lain, sebaiknya di-rotate dari dashboard Supabah Anda.

Seluruh kode di kedua pipeline hanya membaca (`select`) tabel yang sudah
ada di Supabase Anda, kecuali `sectors_fetcher.main` (lihat workflow
`fetch-sectors-to-supabase.yml`) yang memang jalur tulis.

### Skema tabel Supabase yang diharapkan

Enam tabel, dibaca apa adanya oleh kedua pipeline:

| Tabel | Kolom yang dipakai |
|---|---|
| `quarterly_financials` | symbol, report_date, revenue, earnings, total_equity, total_liabilities, total_assets, total_debt, operating_cash_flow, free_cash_flow |
| `daily_transaction` | symbol, date, close, volume, market_cap |
| `daily_full_universe_close` | symbol, date, close, volume, market_cap |
| `free_float_snapshot` | symbol, snapshot_date, free_float, sub_sector |
| `company_overview` | symbol, company_name, sector, sub_sector, board |
| `stock_suspensions` | symbol, suspension_date, reason, pdf_url |

Nama tabel/kolom pipeline arsip diatur di `limina/config.py`; pipeline
produksi di `sectors_fetcher/config.py`.

## 2. GitHub Actions (4 workflow)

Tiga workflow inti sesuai permintaan penggabungan proyek ini, plus satu
workflow lint yang sudah ada sebelumnya di branch `feature-random-forest`
dan dipertahankan (tidak dihapus):

1. **`retrain-random-forest.yml`** (pipeline produksi) -- menjalankan
   ulang `preprocessing/notebook/01_ambil_data.ipynb` ->
   `eda_and_feature_engineering.ipynb` -> `modeling_and_evaluation.ipynb`
   setiap hari 15:00 UTC, mengunggah `output/` sebagai artifact CI (tidak
   di-commit balik, konsisten dengan `.gitignore`). Butuh secrets
   `SECTORS_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`.
2. **`retrain-limina-main.yml`** (pipeline arsip) -- menjalankan ulang
   `notebooks/01`-`05` setiap hari 22:00 UTC, meng-commit balik
   `artifacts/scores.json`, `artifacts/backtest.json`,
   `artifacts/ringkasan_evaluasi.md`, `artifacts/riwayat_skor.csv`. Butuh
   secrets `SUPABASE_URL`, `SUPABASE_KEY`.
3. **`fetch-sectors-to-supabase.yml`** (baru) -- jalur TULIS, mengambil
   data mentah dari Sectors API lalu menyimpannya ke Supabase lewat
   `python -m sectors_fetcher.main`. **Jadwalnya sengaja dinonaktifkan**
   (lihat komentar di dalam berkasnya): `sectors_fetcher/main.py`
   mengimpor `sectors_fetcher/storage/`, folder yang menurut
   `docs/README-pipeline-random-forest.md` (bagian Keterbatasan) memang
   belum ada di checkout ini, jadi job ini akan gagal sampai folder
   tersebut ditambahkan. Bisa dipicu manual (`workflow_dispatch`) untuk
   dites begitu `storage/` sudah lengkap.
4. **`lint.yml`** -- cek sintaks seluruh modul Python (`sectors_fetcher/`)
   dan sel kode notebook (`preprocessing/notebook/`) di tiap push/PR,
   tidak butuh secrets.

Secrets diisi di Settings > Secrets and variables > Actions:
`SECTORS_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`.

## 3. Pipeline arsip -- ringkasan (notebooks/01-05, `limina/`)

Bagian ini meringkas README asli branch `main` untuk pipeline arsip.

1. **01_ambil_data** -- mengunduh keenam tabel dari Supabase, cache lokal
   di `data/raw/`.
2. **02_preprocessing_dan_normalisasi** -- klasifikasi alasan suspensi
   A/B/C, membangun `data/panel.csv` + enam `data/snapshot_<tanggal>.csv`.
3. **03_pelatihan_model** -- regresi logistik (utama) + gradient boosting
   (pembanding) kalau data cukup, empat pemeriksaan kebocoran; fallback
   Isolation Forest atau rule-based kalau data kurang.
4. **04_evaluasi_model** -- Precision@20/Recall@90 hari/AUC, gerbang
   keputusan model vs. rule-based, `artifacts/backtest.json`.
5. **05_penilaian_dan_artefak** -- skor seluruh cakupan emiten hari ini,
   `artifacts/scores.json`.

Metodologi yang mengikat pipeline ini: point-in-time dua lapis
(`limina/pit.py`, `limina/leakage.py`), skor ditampilkan sebagai
persentil/kategori (bukan probabilitas mentah), akurasi tidak pernah
dipakai sebagai metrik utama, gerbang keputusan
(`limina/snapshot.py::gerbang_keputusan`), validasi silang selalu
temporal (`limina/splits.py`), tidak pernah acak.

Pengujian: `pytest tests/ -v` (data sintetis khusus uji statistik, bukan
data produksi).

## 4. Pipeline produksi -- ringkasan (`sectors_fetcher/`, `preprocessing/notebook/`)

Lihat `docs/README-pipeline-random-forest.md` untuk dokumentasi lengkap
(alur data, tiga model yang dibandingkan, seleksi otomatis via Average
Precision CV, `StratifiedGroupKFold` per-symbol, dan bagian Keterbatasan
soal `sectors_fetcher/storage/`, `sql/schema.sql`, dan duplikasi logika
`features/*.py` vs. `service.py`).

## 5. Keterbatasan gabungan yang diketahui

- `sectors_fetcher/storage/` dan `sql/schema.sql` tidak ada di checkout
  ini -- lihat catatan di workflow `fetch-sectors-to-supabase.yml`.
- `docs/rancangan/` (dirujuk README asli branch `main`) dan
  `docs/AMBA-dokumentasi-variabel-dan-pemodelan.md` /
  `docs/AMBANG-panduan-api-sectors.md` (dirujuk README asli branch
  `feature-random-forest`) sama-sama dirujuk di README masing-masing
  tapi tidak ada di zip sumbernya -- bukan sesuatu yang terhapus saat
  penggabungan ini, memang sudah tidak ada sejak awal.
- `already_flagged`, `board` default "Main", dan keterbatasan lain per
  pipeline arsip ada di README asli (bagian 6, diarsipkan di riwayat git).
- Bug cakupan data pipeline arsip (`data_complete==1` kosong) belum
  diperbaiki di notebook arsip itu sendiri -- itulah alasan pipeline
  produksi (Random Forest) dijadikan acuan utama di repo gabungan ini.
