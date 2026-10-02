# Panduan FastAPI untuk LIMINA (`api/`)

`api/` membungkus `sectors_fetcher/service.py::LiminaScoringService` jadi
endpoint HTTP. Tidak ada logika scoring baru -- murni lapisan HTTP di atas
`score_latest_universe()` dan `score_single_ticker()`.

```
api/
  main.py             app FastAPI + GET /health
  dependencies.py     singleton LiminaScoringService
  schemas.py           SkorEmiten, HealthResponse
  routers/scores.py    GET /scores, GET /scores/{symbol}
sectors_fetcher/storage/supabase_client.py   SupabaseStorage.select_all() (jalur baca)
Dockerfile
tests/test_api.py
```

## 1. Status `sectors_fetcher/storage/`

Jalur BACA (`select_all`) sudah ada dan cukup untuk `api/`. Jalur TULIS
(enam modul `storage/save_*.py`, dipakai `sectors_fetcher/main.py` /
`fetch-sectors-to-supabase.yml`) belum dibuat, tapi tidak menghalangi `api/`.

## 2. Jalankan lokal

```bash
pip install -r requirements.txt
export SUPABASE_URL=...
export SUPABASE_KEY=...
uvicorn api.main:app --reload --port 8000
```

Swagger UI: `http://localhost:8000/docs`. `SECTORS_API_KEY` tidak dibutuhkan --
`api/` cuma baca tabel Supabase yang sudah terisi.

## 3. Endpoint

| Endpoint | Fungsi |
|---|---|
| `GET /health` | Status app + apakah model sudah termuat |
| `GET /scores` | Skor seluruh emiten. Query opsional: `tickers`, `as_of_date` |
| `GET /scores/{symbol}` | Skor satu emiten. 404 kalau tidak ditemukan |

Respons mengikuti `SkorEmiten` (`api/schemas.py`): `skor`, `persentil`,
`kategori`, `arah_30h`, `status`, `indikator_dominan`, `kontribusi`.

## 4. Model `.joblib`

`output/` tidak di-gitignore -- `retrain-random-forest.yml` meng-commit
isinya ke `main` tiap kali ketiga notebook sukses, jadi `git pull` biasa
sudah cukup untuk `api/`. Kalau ukuran repo jadi masalah: Git LFS untuk
`output/*.joblib`/`*.parquet`, atau unggah ke Supabase Storage dan unduh
saat `api/dependencies.py` start (lalu `output/` bisa di-gitignore lagi).

Kalau model belum pernah di-generate, `/scores` balas HTTP 503 (bukan
crash 500 mentah) -- lihat `api/routers/scores.py`.

## 5. CORS

Dikomentari di `api/main.py` -- buka komentarnya dan isi `allow_origins`
kalau dipanggil dari web frontend domain lain.

## 6. Deploy

```bash
docker build -t limina-api .
docker run -p 8000:8000 -e SUPABASE_URL=... -e SUPABASE_KEY=... limina-api
```

Cocok untuk skala kecil: Railway, Render, Fly.io.

## 7. Pengujian

```bash
pytest tests/test_api.py -v
```

Butuh `SUPABASE_URL`/`SUPABASE_KEY` valid (`/health` membuka koneksi Supabase).
