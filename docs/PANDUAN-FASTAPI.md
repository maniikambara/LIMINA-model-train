# Panduan FastAPI untuk LIMINA/AMBA (`api/`)

`api/` membungkus `sectors_fetcher/service.py::AMBAScoringService`
(sudah dirancang untuk backend API) jadi endpoint HTTP, supaya
frontend/klien lain bisa minta skor risiko suspensi tanpa menjalankan
notebook manual. Tidak ada logika scoring baru di sini -- `api/` murni
lapisan HTTP di atas `score_latest_universe()` dan `score_single_ticker()`
yang sudah ada.

```
api/
  main.py           app FastAPI + endpoint /health
  dependencies.py   singleton AMBAScoringService (model dimuat sekali)
  schemas.py         model Pydantic response (SkorEmiten, HealthResponse)
  routers/
    scores.py         GET /scores, GET /scores/{symbol}

sectors_fetcher/storage/
  supabase_client.py  SupabaseStorage.select_all() -- jalur BACA yang
                       dibutuhkan AMBAScoringService (lihat Bagian 1)

Dockerfile          image untuk api/
tests/test_api.py   smoke test /health
```

## 1. Status `sectors_fetcher/storage/`: BACA sudah ada, TULIS belum

`AMBAScoringService` (dipakai `api/`) cuma butuh method
`select_all(table_name) -> list[dict]`, dan itu sudah diimplementasikan
di `sectors_fetcher/storage/supabase_client.py`. **Cukup untuk
menjalankan `api/` ini.**

Yang **belum** ada (tidak dibutuhkan `api/`, tapi dibutuhkan
`sectors_fetcher/main.py` / workflow `fetch-sectors-to-supabase.yml`):
enam modul `storage/save_*.py`, satu per tabel
(`save_quarterly_financials`, `save_daily_transaction`, `save_free_float`,
`save_full_universe_close`, `save_suspensions`, `save_company_overview`).
Tambahkan itu kapan pun mau mengaktifkan jalur TULIS -- tidak menghalangi
`api/`.

## 2. Instal dependensi

Sudah ditambahkan ke `requirements.txt` (`fastapi`, `uvicorn[standard]`):

```bash
pip install -r requirements.txt
```

## 3. Jalankan lokal

```bash
export SUPABASE_URL=...
export SUPABASE_KEY=...
uvicorn api.main:app --reload --port 8000
```

Buka `http://localhost:8000/docs` -- Swagger UI otomatis dari
`api/schemas.py`, langsung bisa dites dari browser. Coba
`http://localhost:8000/scores/BBCA` untuk satu emiten, atau
`http://localhost:8000/health` untuk cek status model.

`SECTORS_API_KEY` **tidak** dibutuhkan `api/` -- sama seperti
`retrain-random-forest.yml`, cuma baca tabel Supabase yang sudah terisi.

## 4. Endpoint yang tersedia

| Endpoint | Fungsi |
|---|---|
| `GET /health` | Status app + apakah model sudah termuat |
| `GET /scores` | Skor seluruh emiten (`AMBAScoringService.score_latest_universe`). Query opsional: `tickers` (bisa berulang), `as_of_date` |
| `GET /scores/{symbol}` | Skor satu emiten (`score_single_ticker`). 404 kalau simbol tidak ditemukan |

Respons mengikuti `SkorEmiten` di `api/schemas.py`: `skor`, `persentil`,
`kategori`, `arah_30h`, `status`, `indikator_dominan`, `kontribusi`,
persis field yang dihasilkan `service.py::score_features_dataframe()`.

## 5. Dari mana model `.joblib`-nya? (sudah beres, di-commit otomatis)

`output/` **sudah dihapus dari `.gitignore`**, dan
`retrain-random-forest.yml` meng-commit balik seluruh isi `output/`
(dataset, `scores.json`, `backtest.json`, model `*.joblib`) ke branch
`main` di langkah "Commit output" -- hanya kalau ketiga notebook sukses
penuh, jadi yang ter-commit selalu dari siklus retrain yang utuh. Artinya
`git clone`/`git pull` biasa dari `main` sudah cukup buat menjalankan
`api/` -- tidak perlu langkah tambahan.

Konsekuensinya: ukuran repo membengkak sedikit tiap kali retrain jalan
(model + dataset ditimpa ulang tiap siklus, bukan ditambah -- jadi
pertumbuhannya dari histori git, bukan dari jumlah file). Kalau nanti itu
jadi masalah, dua alternatif:

- **Git LFS** untuk `output/*.joblib` dan `output/*.parquet` -- histori
  git tetap ringan, file besarnya disimpan terpisah.
- **Supabase Storage (bucket)** -- unggah `.joblib` di akhir
  `retrain-random-forest.yml`, lalu `api/dependencies.py` mengunduhnya
  ke `output/` saat aplikasi start kalau belum ada secara lokal. `output/`
  bisa dikembalikan ke `.gitignore` kalau pakai cara ini.

Kalau `FileNotFoundError` tetap muncul (mis. baru clone sebelum retrain
pertama pernah jalan sama sekali), `/scores` balas HTTP 503 -- sudah
ditangani di `api/routers/scores.py`, jadi jelas penyebabnya, bukan
crash 500 mentah.

## 6. CORS (kalau dipanggil dari web frontend)

Sudah disiapkan dikomentari di `api/main.py` -- tinggal buka komentarnya
dan isi `allow_origins` dengan domain frontend Anda.

## 7. Deploy dengan Docker

`Dockerfile` sudah ada di root repo:

```bash
docker build -t limina-api .
docker run -p 8000:8000 -e SUPABASE_URL=... -e SUPABASE_KEY=... limina-api
```

Platform yang cocok untuk skala kecil (deploy langsung dari
`Dockerfile`, tinggal set env var lewat menu masing-masing): Railway,
Render, Fly.io.

## 8. Pengujian

```bash
pytest tests/test_api.py -v
```

`tests/test_api.py` pakai `TestClient` FastAPI -- tetap butuh
`SUPABASE_URL`/`SUPABASE_KEY` valid karena `/health` memanggil
`get_scoring_service()` (yang membuka koneksi Supabase).
