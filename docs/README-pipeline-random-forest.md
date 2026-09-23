# AMBA: Early Warning System Risiko Suspensi Saham IDX

AMBA menilai kemungkinan sebuah emiten IDX kena suspensi karena masalah
fundamental (bukan sekadar volatilitas harga) dalam 90 hari ke depan,
memakai 11 indikator turunan dari laporan keuangan, transaksi harian, dan
struktur kepemilikan. Dibangun untuk Sectors Hackathon 2026, Track 03
Market Intelligence.

Branch ini (`feature-random-forest`) menambahkan Random Forest sebagai
model non-linear di samping Logistic Regression, dengan hyperparameter
tuning (`GridSearchCV`).

## Struktur Proyek

```
sectors_fetcher/          Pengambilan data dari Sectors API + logika bisnis
  client.py                HTTP client Sectors API v2 (retry, rate limit)
  config.py                Kredensial, endpoint, ambang indikator
  supabase_io.py            Pembaca Supabase (baca saja) dipakai 01_ambil_data.ipynb
  endpoints/                Satu modul per endpoint API (fetch mentah saja)
  features/                 Perhitungan 11 indikator turunan (lihat catatan di bawah)
  service.py                AMBAScoringService: preprocessing + inferensi + skor produksi
  main.py                   Entry point: fetch semua tabel -> simpan ke Supabase

preprocessing/notebook/
  01_ambil_data.ipynb                 Unduh enam tabel mentah dari Supabase (baca saja) -> data/raw/
  eda_and_feature_engineering.ipynb   Audit data mentah, taksonomi suspensi,
                                       feature engineering point-in-time -> output/dataset_modeling_ambang.csv
  modeling_and_evaluation.ipynb       Logistic Regression, Random Forest + tuning,
                                       evaluasi, ekspor scores.json/backtest.json

docs/
  AMBA-dokumentasi-variabel-dan-pemodelan.md   Definisi lengkap tiap variabel dan rumus
  AMBANG-panduan-api-sectors.md                Referensi endpoint Sectors API v2
```

## Alur Data

```
Sectors API v2 --> sectors_fetcher (fetch) --> Supabase (simpan mentah)
                                                     |
                                                     v
                                        01_ambil_data.ipynb
                                  (baca Supabase -> cache data/raw/*.csv)
                                                     |
                                                     v
                              eda_and_feature_engineering.ipynb
                         (point-in-time feature engineering + label)
                                                     |
                                                     v
                              output/dataset_modeling_ambang.csv
                                                     |
                                                     v
                              modeling_and_evaluation.ipynb
                    (Logistic Regression, Random Forest + tuning, evaluasi)
                                                     |
                                                     v
                         output/scores.json, output/backtest.json, model *.joblib
```

`01_ambil_data.ipynb` dan `sectors_fetcher/supabase_io.py` adalah jalur
BACA yang independen dari `sectors_fetcher/main.py` (jalur TULIS, butuh
paket `sectors_fetcher/storage/` yang belum ada di checkout ini -- lihat
Keterbatasan). Notebook ini bisa dijalankan berkali-kali (pengambilan
pertama maupun pembaruan harian) tanpa bergantung pada paket yang hilang
itu, karena hanya melakukan `select()` ke enam tabel yang sudah ada di
Supabase Anda, sama seperti proyek kakaknya (LIMINA/AMBANG) yang membaca
Supabase yang sama.

Prinsip point-in-time (dipakai konsisten di `service.py` dan kedua
notebook): setiap fitur untuk `as_of_date` tertentu hanya boleh dihitung
dari data yang terbit pada atau sebelum `as_of_date` itu. Target model
(`y` di `modeling_and_evaluation.ipynb`) adalah `event_category.notna()`,
menengok 90 hari ke DEPAN dari `as_of_date`: bernilai 1 kalau emiten
mengalami suspensi Kategori A (lonjakan harga), B (penurunan harga),
**atau** C (kepatuhan/going concern) dalam jendela itu. Kolom `is_event_90d`
(Kategori C saja) tetap ada di dataset sebagai alternatif yang lebih sempit,
tapi tidak dipakai sebagai target saat ini. Definisi lengkap ada di
`docs/AMBA-dokumentasi-variabel-dan-pemodelan.md` Bagian 5.

## Menjalankan

Butuh environment variable `SECTORS_API_KEY`, `SUPABASE_URL`,
`SUPABASE_KEY` (lihat `sectors_fetcher/config.py`), bisa juga lewat
berkas `.env` di folder `sectors_fetcher/`.

```
pip install -r requirements.txt
export SECTORS_API_KEY="..."
export SUPABASE_URL="..."
export SUPABASE_KEY="..."
python -m sectors_fetcher.main                # opsional: ambil dari Sectors API, simpan ke Supabase
                                                # (butuh sectors_fetcher/storage/, lihat Keterbatasan)
jupyter nbconvert --execute --to notebook --inplace preprocessing/notebook/01_ambil_data.ipynb
jupyter nbconvert --execute --to notebook --inplace preprocessing/notebook/eda_and_feature_engineering.ipynb
jupyter nbconvert --execute --to notebook --inplace preprocessing/notebook/modeling_and_evaluation.ipynb
```

Kalau tabel Supabase Anda sudah terisi (lewat `sectors_fetcher.main` atau
proses lain), langkah `python -m sectors_fetcher.main` bisa dilewati --
`01_ambil_data.ipynb` hanya perlu `SUPABASE_URL`/`SUPABASE_KEY` untuk
membaca tabel yang sudah ada.

## Model dan Tuning

`modeling_and_evaluation.ipynb` melatih dan membandingkan tiga model lewat
validasi silang berstrata **dan berkelompok** (`StratifiedGroupKFold`,
dikelompokkan per `symbol`). Ini penting: satu emiten muncul berkali-kali
(satu baris per snapshot `as_of_date`) dengan 11 indikator yang berubah
pelan antar snapshot, jadi `StratifiedKFold` biasa bisa menaruh baris
emiten yang sama di fold train dan test sekaligus (kebocoran per-grup,
bikin metrik tampak lebih bagus dari yang sebenarnya).
`StratifiedGroupKFold` memastikan seluruh baris satu emiten selalu ada di
fold yang sama. Jumlah fold otomatis diturunkan kalau jumlah **emiten**
(bukan baris) berkelas positif lebih sedikit dari 5, dan seluruh
CV/tuning supervised dilewati (beralih ke skor anomali unsupervised) kalau
emiten berkelas positif kurang dari 2 -- lihat Bagian 4.1 notebook.

1. Logistic Regression baseline (tidak di-tuning, jadi acuan pembanding).
2. Logistic Regression, `class_weight="balanced"`, di-tuning lewat
   `GridSearchCV` atas `C` (termasuk nilai sangat kecil, 0.001-0.03, karena
   regularisasi kuat cenderung menang pada data sekecil ini), `penalty`
   (`l2` dan `l1` -- `l1` bisa menekan koefisien fitur lemah ke nol), dan
   `solver`.
3. **Random Forest** lewat `BalancedRandomForestClassifier`
   (`imbalanced-learn`, otomatis jatuh ke `RandomForestClassifier` biasa +
   `class_weight="balanced"` kalau paket itu belum terpasang) -- tiap pohon
   dilatih dari bootstrap sample yang sudah diseimbangkan per kelas, bukan
   cuma pembobotan loss seperti `class_weight` saja. Hyperparameter dicari
   2 tahap: `RandomizedSearchCV` (60 kombinasi acak atas `n_estimators`,
   `max_depth`, `min_samples_split`, `min_samples_leaf`, `max_features`,
   `criterion`, `class_weight`), lalu `GridSearchCV` halus di sekitar hasil
   terbaiknya -- disetel memakai skor `average_precision` (bukan akurasi;
   lihat bagian Keterbatasan).

Ketiganya dibandingkan lewat ROC-AUC, Average Precision, Precision@Top20%,
Precision/Recall/F1 (ambang 0.5), ROC curve, dan confusion matrix. **Model
dengan Average Precision CV tertinggi dipilih otomatis** sebagai model
produksi (`model_terpilih`) yang dipakai Bagian 9 untuk skor final dan
`scores.json`/`backtest.json` -- ini TIDAK selalu Random Forest; pada
dataset kecil, Logistic Regression yang diregularisasi kuat sering
menggeneralisasi lebih baik. Atribusi `indikator_dominan`/`kontribusi`
dihitung exact dari koefisien model terpilih kalau itu Logistic Regression;
kalau model terpilih adalah Random Forest, dipakai arah koefisien Logistic
Regression (Balanced) sebagai proksi penjelas (Random Forest tidak
punya kontribusi per-baris bertanda yang murah dihitung exact tanpa
pustaka tambahan seperti SHAP/treeinterpreter). Kalau cakupan data belum
punya minimal 2 emiten berkelas positif, ketiga model di atas dilewati dan
diganti sementara oleh `SkorAnomaliMahalanobis`
(`sectors_fetcher/risk_scorer_fallback.py`) -- model unsupervised berbasis
jarak Mahalanobis yang tidak butuh label sama sekali, dengan seluruh
output ditandai eksplisit sebagai belum divalidasi secara statistik.

## CI/CD (GitHub Actions)

`.github/workflows/lint.yml` mengecek sintaks seluruh modul Python dan sel
notebook di setiap push/PR (tidak butuh kredensial). `.github/workflows/retrain.yml`
menjalankan ulang ketiga notebook secara terjadwal (dan bisa dipicu manual
lewat tab Actions), lalu mengunggah `output/` dan notebook hasil eksekusi
sebagai artifact. Butuh secrets repo `SECTORS_API_KEY`, `SUPABASE_URL`,
`SUPABASE_KEY` (Settings -> Secrets and variables -> Actions) -- tanpa
ketiganya, job `retrain` akan gagal di langkah `01_ambil_data.ipynb`.
`python -m sectors_fetcher.main` sengaja tidak ikut dijalankan di CI, lihat
bagian Keterbatasan soal `sectors_fetcher/storage/`.

## Keterbatasan yang Diketahui

- **`sectors_fetcher/storage/` tidak ada di checkout ini.** Ini submodul
  yang menyimpan hasil fetch KE Supabase (`SupabaseStorage`, `save_*`
  per tabel) -- dirujuk oleh `main.py` dan `service.py`. `service.py`
  sudah dibuat toleran (import ditunda, `AMBAScoringService` melempar
  pesan jelas kalau storage tak tersedia dan tidak disuntikkan manual),
  jadi `import sectors_fetcher` dan fungsi murni (`classify_suspension_reason`,
  `preprocess_single_ticker`, seluruh `features/*.py`) tetap bisa dipakai.
  Jalur BACA dari Supabase tidak lagi bergantung pada submodul yang
  hilang ini: `01_ambil_data.ipynb` beserta `sectors_fetcher/supabase_io.py`
  membaca enam tabel langsung lewat Supabase Data API, independen dari
  `storage/`. Yang masih butuh `storage/` hanyalah jalur TULIS
  (`sectors_fetcher.main`, untuk mengambil data baru dari Sectors API dan
  menyimpannya ke Supabase) -- kalau tabel Supabase Anda sudah terisi
  lewat proses lain, seluruh alur di README ini (01_ambil_data.ipynb dan
  kedua notebook berikutnya) bisa berjalan tanpa submodul itu sama sekali.
- `output/` (dataset, `scores.json`, `backtest.json`, model `.joblib`)
  dihasilkan oleh kedua notebook, bukan disertakan di repo --
  `.gitignore` sengaja mengecualikannya.
- `sql/schema.sql` yang dirujuk `main.py` juga tidak ada di checkout ini.
- `sectors_fetcher/features/*.py` (satu modul per kelompok indikator)
  saat ini tidak dipanggil oleh `service.py` maupun kedua notebook --
  keduanya punya salinan logika perhitungan indikator sendiri secara
  inline. Ketiganya sudah diperiksa konsisten (lihat riwayat perbaikan
  `free_float_rendah` di `features/ownership.py`), tapi duplikasi ini
  berisiko divergen lagi ke depannya kalau salah satu diubah tanpa
  mengubah yang lain.
- Akurasi tidak dipakai sebagai metrik utama di mana pun dalam proyek
  ini -- kelas target sangat timpang (kejadian suspensi kategori C
  jarang), jadi metrik yang dipakai adalah ROC-AUC, Precision, Recall,
  F1, dan `Precision@20`/`Recall@90h` (lihat
  `AMBA-dokumentasi-variabel-dan-pemodelan.md` bagian 7). Satu nilai
  `akurasi_internal_only` tetap dicatat di `backtest.json` untuk
  referensi internal, secara eksplisit diberi label demikian supaya
  tidak disalahartikan sebagai metrik penilaian utama.
