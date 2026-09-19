# LIMINA

Sistem peringatan dini risiko suspensi saham di Bursa Efek Indonesia (BEI).
LIMINA menghitung ulang kriteria risiko suspensi yang sudah dipublikasikan
BEI secara berkelanjutan dari data yang tersimpan di Supabase, lalu
menampilkan emiten mana yang sedang bergerak mendekati ambang batas
tersebut, lebih cepat daripada label resminya terbit.

LIMINA bukan nasihat investasi, bukan prediksi kebangkrutan atau
kecurangan, dan bukan pengganti pengumuman resmi BEI. Keputusan membeli,
menjual, atau menahan saham sepenuhnya tanggung jawab pengguna sendiri.

## Tentang nama dan asal proyek

Proyek ini sebelumnya dirancang dengan nama kerja AMBANG/AMBA untuk
Sectors Hackathon 2026, Track 03 Market Intelligence. Rancangan awal
(termasuk daftar variabel, arsitektur, dan metodologi evaluasi) masih
berlaku penuh dan diarsipkan apa adanya di `docs/rancangan/`. Yang
berubah pada tahap ini adalah namanya menjadi LIMINA, sumber datanya
langsung dari Supabase (bukan lagi memanggil Sectors API secara
langsung), dan seluruh kode ditata ulang menjadi notebook modular yang
bisa dijalankan berkala untuk melatih ulang model secara otomatis.

## Struktur proyek

```
LIMINA/
  notebooks/
    01_ambil_data.ipynb                   ambil/perbarui data dari Supabase
    02_preprocessing_dan_normalisasi.ipynb bangun panel + label + standardisasi
    03_pelatihan_model.ipynb               latih model, empat pemeriksaan kebocoran
    04_evaluasi_model.ipynb                backtest, gerbang keputusan, selisih waktu
    05_penilaian_dan_artefak.ipynb         skor pasar hari ini, artefak produk
  limina/                                  kode inti yang dipakai seluruh notebook
  tests/                                   pengujian unit (pytest)
  data/
    labels/taksonomi_alasan_suspensi.json  taksonomi alasan suspensi (A/B/C)
    raw/, panel.csv, snapshot_*.csv        dihasilkan ulang tiap siklus (gitignored)
  artifacts/                               model terlatih, scores.json, backtest.json
  docs/rancangan/                          dokumen rancangan asli (AMBANG/AMBA), arsip
  .github/workflows/update-model.yml       jadwal pembaruan otomatis harian
```

## 1. Persiapan

```
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Python 3.10 atau lebih baru.

### Isi kredensial Supabase

Salin `.env.example` menjadi `.env`, lalu isi dua nilainya:

```
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_KEY=isi_anon_atau_publishable_key_anda
```

`.env` sudah masuk `.gitignore`, tidak akan pernah ikut ter-commit.
Seluruh kode di proyek ini hanya membaca (`select`) tabel yang sudah ada
di Supabase Anda; tidak ada satu baris kode pun yang menulis, mengubah,
atau membuat struktur tabel baru. Kalau kredensial belum diisi, notebook
01 berhenti dengan pesan yang menjelaskan persis apa yang kurang, bukan
gagal diam-diam atau memakai data contoh.

### Skema tabel Supabase yang diharapkan

Enam tabel, dibaca apa adanya. Kalau nama tabel atau kolom Anda berbeda,
ubah di satu tempat: `limina/config.py`.

| Tabel | Kolom yang dipakai |
|---|---|
| `quarterly_financials` | symbol, report_date, revenue, earnings, total_equity, total_liabilities, total_assets, total_debt, operating_cash_flow, free_cash_flow |
| `daily_transaction` | symbol, date, close, volume, market_cap |
| `daily_full_universe_close` | symbol, date, close, volume, market_cap |
| `free_float_snapshot` | symbol, snapshot_date, free_float, sub_sector |
| `company_overview` | symbol, company_name, sector, sub_sector, board |
| `stock_suspensions` | symbol, suspension_date (atau nama lain, atur di config.py), reason, pdf_url |

`company_overview` opsional secara teknis (kode berjalan tanpanya), tapi
sangat disarankan diisi: tanpa tabel ini, seluruh emiten dianggap papan
"Main" secara default, dan sektor didekati dari `free_float_snapshot`
saja.

## 2. Menjalankan siklus latih pertama kali

Jalankan kelima notebook berurutan, satu kali, dari awal:

1. **01_ambil_data** -- mengunduh keenam tabel dari Supabase apa adanya
   (seluruh histori yang sudah terkumpul di sana, tidak dibatasi tanggal),
   menyimpan cache lokal di `data/raw/`.
2. **02_preprocessing_dan_normalisasi** -- mengklasifikasikan alasan
   suspensi ke kategori A/B/C, membangun `data/panel.csv` (data latih,
   sampel berimbang) dan enam `data/snapshot_<tanggal>.csv` (potret
   evaluasi, proporsi kejadian apa adanya), lalu menyimpan jendela
   latih/uji yang dipakai siklus ini ke `data/jendela_latih.json`.
3. **03_pelatihan_model** -- memilih salah satu dari tiga jalur tergantung
   baris `data_complete == 1` yang tersedia: (a) >=20 baris dan >=2 positif
   -> melatih regresi logistik (model utama) dan gradient boosting
   (pembanding), menjalankan empat pemeriksaan kebocoran; (b) positif
   kurang tapi >=5 baris lengkap -> Kandidat 5 (Isolation Forest, anomali
   tanpa label); (c) selain itu -> rule_based_penuh, tidak ada yang
   dilatih. Keputusan dicatat ke `artifacts/keputusan.json`.
4. **04_evaluasi_model** -- Precision@20/Recall@90 hari/AUC lintas enam
   potret, gerbang keputusan (regresi logistik vs. rule-based),
   rekonstruksi selisih waktu deteksi sungguhan, menulis
   `artifacts/backtest.json` dan `artifacts/ringkasan_evaluasi.md`. Seluruh
   isi notebook ini membandingkan terhadap Kandidat 1 -- kalau notebook 03
   mengambil jalur (b)/(c) di atas, notebook ini mencetak penjelasan dan
   melewati evaluasinya (tidak menulis backtest.json siklus itu), bukan
   gagal dengan galat berkas tidak ditemukan.
5. **05_penilaian_dan_artefak** -- menilai seluruh cakupan emiten dengan
   data pasar hari ini, menulis `artifacts/scores.json` -- inilah keluaran
   yang dibaca dashboard/produk. Memakai kandidat terbaik yang tersedia,
   berurutan: Kandidat 1 (regresi logistik) -> Kandidat 5 (anomali tanpa
   label) -> Kandidat 4 (rule-based, tidak perlu pelatihan) -- dan beralih
   naik ke kandidat yang lebih baik dengan sendirinya begitu notebook 03
   berhasil melatihnya.

Ini disebut "notebook 01-05" sepanjang dokumen ini karena semua penomoran
mengikuti urutan file, bukan urutan cell di dalam satu notebook.

Ini adalah **pelatihan pertama**: model dilatih dari seluruh data yang
sudah terkumpul di Supabase pada saat itu (biasa disebut di percakapan
tim sebagai "data yang sudah diambil, 90 hari atau lebih").

Kalau `data/panel.csv` yang terbentuk punya kurang dari sekitar 30
peristiwa kategori C, notebook 02 mencetak peringatan eksplisit. Model
tetap dilatih dan tetap dievaluasi -- ini bukan alasan berhenti -- tapi
seluruh metrik pada sampel sekecil itu punya selang kepercayaan lebar
dan wajib disebutkan begitu setiap kali hasilnya dilaporkan ke orang
lain (lihat `docs/rancangan/metodologi.md` bagian 9).

## 3. Kalau notebook 02/03 melapor data tidak lengkap

Tiap potret/baris panel punya kolom `data_complete`. Notebook 02
mencetak diagnosa cakupan sebelum membangun apa pun dan proporsi baris
lengkap setelahnya. Notebook 03 menyaring `data_complete == 0` sebelum
melatih dan berhenti dengan pesan jelas kalau sisanya terlalu sedikit,
bukan galat sklearn membingungkan soal "Input X contains NaN".

Penyebab paling umum, berurutan:

1. **Format symbol tidak konsisten antar tabel.** Cek
   `contoh_symbol_universe`/`contoh_symbol_quarterly_financials`/
   `contoh_symbol_harga` di cetakan diagnosa notebook 02 -- kalau satu
   daftar berakhiran `.JK` dan yang lain tidak, itu sumbernya
   (`tumpang_tindih_*_persen` jauh di bawah 100 memastikannya). Nama
   kolom tabel suspensi sudah disesuaikan otomatis
   (`supabase_io.py::normalisasi_tabel_suspensi`); kelima tabel lain
   divalidasi lewat `supabase_io.py::validasi_kolom_tabel`.
2. **Riwayat `quarterly_financials`/`daily_transaction` belum cukup
   panjang.** Bandingkan `report_date_min/max` dan `harga_date_min/max`
   dengan `tanggal_potret` yang dicetak berikutnya -- memperpendek
   jendela (`JENDELA_PIT_HARI`/`JENDELA_HARGA_HARI`) tidak menyiasati
   ini kalau peristiwanya sudah terjadi sebelum riwayat mulai terekam.

Kalau `jumlah_symbol_kategori_c_siap_dilatih` nol, prioritas tertinggi:
perluas cakupan `quarterly_financials`/`daily_transaction` ke symbol di
`symbol_kategori_c_belum_punya_quarterly_financials_contoh` -- itulah
emiten yang riwayatnya paling penting dipelajari model. Kalau mahal
per-symbol, cakupan per-sektor (emiten sesektor dengan yang pernah kena
kategori C) adalah alternatif yang lebih murah untuk memulai.

## 4. Pembaruan berkala (harian/mingguan)

Menjalankan ulang notebook 01-05 ADALAH cara memperbarui model.
Tidak ada perbedaan kode antara "pelatihan pertama" dan "pembaruan
ke-100": `limina/splits.py` menghitung ulang jendela latih dan enam
tanggal potret evaluasi setiap kali dijalankan, RELATIF terhadap
tanggal hari itu -- bukan tanggal tetap yang tertulis di kode. Setiap
kali Supabase punya data lebih baru, siklus berikutnya otomatis
memakainya, tanpa menyunting satu baris kode pun.

Model lama tidak pernah hilang begitu saja: `03_pelatihan_model`
menyimpan salinan kanonis (dipakai notebook 04/05) DAN satu salinan
berstempel waktu di `artifacts/models/<stempel>/` setiap kali
dijalankan, supaya ada riwayat versi untuk dibandingkan atau
dikembalikan manual kalau suatu siklus retraining menghasilkan model
yang tiba-tiba jauh lebih buruk.

### Opsi A -- GitHub Actions (sudah disiapkan)

`.github/workflows/update-model.yml` menjalankan kelima notebook secara
berurutan setiap hari jam 22:00 UTC (05:00 WIB), lalu meng-commit balik
`artifacts/scores.json`, `artifacts/backtest.json`,
`artifacts/ringkasan_evaluasi.md`, dan `artifacts/riwayat_skor.csv` ke
repositori. Yang perlu disiapkan:

1. Push proyek ini ke repositori GitHub.
2. Di Settings > Secrets and variables > Actions, tambahkan
   `SUPABASE_URL` dan `SUPABASE_KEY`.
3. Ubah jadwal cron di berkas workflow kalau ingin mingguan, bukan
   harian (contoh sudah dikomentari di dalam berkasnya).

Model dan scaler (berkas `.joblib`) sengaja TIDAK ikut di-commit (lihat
`.gitignore`) -- setiap siklus melatih ulang dari nol dari data
Supabase saat itu, konsisten dengan cara notebook 01 mengambil seluruh
data yang tersedia, bukan hanya delta harian.

### Opsi B -- cron di server/VPS sendiri

```
0 22 * * * cd /path/ke/LIMINA && .venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/01_ambil_data.ipynb && .venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/02_preprocessing_dan_normalisasi.ipynb && .venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/03_pelatihan_model.ipynb && .venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/04_evaluasi_model.ipynb && .venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/05_penilaian_dan_artefak.ipynb
```

Pastikan `SUPABASE_URL`/`SUPABASE_KEY` diekspor di environment cron
(atau taruh di `.env` pada folder proyek).

### Opsi C -- platform hosting dengan cron job terjadwal

Platform dengan cron job berjadwal untuk perintah Python (Railway,
Render, dsb.) bisa memakai perintah yang sama seperti Opsi B, dengan
`SUPABASE_URL`/`SUPABASE_KEY` diisi lewat environment variable/secret
platform tersebut. Folder proyek dan `artifacts/` perlu tetap ada antar
run (untuk versi model dan `riwayat_skor.csv`).

## 5. Metodologi (ringkas)

Rincian penuh ada di `docs/rancangan/`. Poin yang mengikat seluruh kode:

- **Point-in-time**: setiap baris hanya boleh memakai data yang sudah
  tersedia pada `as_of_date`-nya, dengan jeda aman 30 hari
  (`limina/pit.py`). Ditegakkan dua lapis: saat pengambilan data
  (`limina/raw_ingest.py`) dan saat memeriksa dataset yang sudah jadi
  (`limina/leakage.py`, empat pemeriksaan, dijalankan tiap siklus latih).
- **Skor bukan probabilitas**: yang ditampilkan ke pengguna adalah
  `persentil` dan `kategori` (Rendah/Sedang/Tinggi/Sangat Tinggi), tidak
  pernah angka mentah model sebagai "kemungkinan sekian persen" --
  jumlah sampel positif yang tersedia terlalu kecil untuk mengklaim
  model terkalibrasi.
- **Akurasi tidak pernah dilaporkan** sebagai metrik utama (kelas
  sangat timpang membuatnya menyesatkan). Metrik yang dilaporkan:
  Precision@20, Recall@90 hari, AUC, dan selisih waktu deteksi
  terhadap label resmi.
- **Gerbang keputusan** (`limina/snapshot.py::gerbang_keputusan`)
  membandingkan regresi logistik terhadap pembanding rule-based setiap
  siklus evaluasi; kalau model tidak menang mayoritas potret, rule-based
  yang jadi mesin utama, model tetap ditampilkan sebagai pembanding.
- **Validasi silang acak tidak pernah dipakai.** Pemisahan selalu
  temporal (`limina/splits.py`), karena mencampur masa depan ke data
  latih adalah bentuk kebocoran, bukan validasi yang sah.

## 6. Keterbatasan yang diketahui

1. `already_flagged` (status Notasi Khusus BEI resmi pada satu
   `as_of_date`) belum punya sumber data mentah di enam tabel Supabase
   di atas, jadi diisi 0 untuk seluruh baris. Kalau Anda punya sumber
   datanya, ini titik yang perlu diperluas di `limina/raw_ingest.py`.
2. `board` (papan pencatatan) jatuh ke default "Main" untuk emiten yang
   belum tercakup `company_overview`.
3. `free_float_rendah` hanya dipakai saat penilaian langsung (notebook
   05), tidak pernah saat melatih, karena `free_float_snapshot`
   kemungkinan besar hanya menyimpan nilai terkini, bukan riwayat.
4. `arah_30h`/`delta_30h` pada `scores.json` baru bermakna setelah
   `artifacts/riwayat_skor.csv` terkumpul sekitar 30 hari; sebelum itu
   seluruh emiten akan tertulis "stabil" apa adanya, bukan galat.
5. Taksonomi alasan suspensi (`data/labels/taksonomi_alasan_suspensi.json`)
   sudah divalidasi terhadap riwayat suspensi sungguhan, tapi bukan
   daftar final -- notebook 02 mencetak baris yang tidak cocok kata
   kunci manapun setiap kali dijalankan; tinjau baris itu secara manual.
6. Selisih waktu deteksi historis tidak menjamin performa masa depan.

## 7. Pengujian

```
pytest tests/ -v
```

Pengujian memakai data sintetis yang dibuat khusus untuk uji statistik
(`tests/conftest.py`), bukan pengganti data produk -- tidak ada satu
jalur produksi pun (notebook 01-05) yang memakai data buatan; seluruhnya
memakai data Supabase sungguhan.
