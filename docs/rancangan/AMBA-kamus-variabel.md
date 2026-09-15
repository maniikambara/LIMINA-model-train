# AMBA: Kamus Variabel

Dokumen ini mendaftar seluruh variabel yang dipakai proyek AMBA, dari data mentah sampai yang tampil ke pengguna. Ditulis sebagai rujukan bersama antar peran, supaya semua orang memakai nama variabel yang sama dan tahu persis dari mana asalnya.

**Status dokumen:** rujukan teknis, bagian dari rancangan AMBA
**Terkait:** AMBA-konsep-dan-rancangan.md, AMBA-peran-model-dan-evaluasi.md, AMBA-panduan-api-sectors.md

---

## Cara Membaca Dokumen Ini

Ada empat lapis variabel, mengalir satu arah:

```
Variabel mentah dari API
        |
        v
Variabel turunan / indikator (dihitung sendiri)
        |
        v
Variabel keluaran (digabung jadi skor, lalu disajikan)
        |
        v
Variabel evaluasi (dipakai tim, tidak dilihat pengguna)
```

Aturan yang mengikat seluruh dokumen ini: **variabel turunan tidak boleh sama persis dengan variabel mentah.** Kalau sebuah angka di layar bisa didapat dengan menyalin langsung dari respons API tanpa perhitungan apapun, itu melanggar syarat lolos Track 3 Market Intelligence.

---

## 1. Variabel Identitas dan Label

Menempelkan setiap baris data ke satu emiten pada satu titik waktu. Bukan indikator risiko.

| Variabel | Tipe | Keterangan |
|---|---|---|
| `symbol` | teks | Kode emiten, empat huruf, misalnya BBCA |
| `as_of_date` | tanggal | Titik potong, seluruh indikator pada baris ini dihitung per tanggal ini |
| `sector` | teks | Klasifikasi sektor emiten |
| `sub_sector` | teks | Klasifikasi sub-sektor emiten |
| `board` | teks | Papan pencatatan: Main, Development, atau Acceleration |
| `is_event_90d` | 0 / 1 | Label. 1 jika emiten mengalami peristiwa suspensi kategori C dalam 90 hari setelah `as_of_date` |
| `event_date` | tanggal atau kosong | Tanggal peristiwa suspensi, jika ada |
| `event_category` | A / B / C / kosong | Taksonomi alasan suspensi. Hanya kategori C yang menjadi label positif |
| `already_flagged` | 0 / 1 | 1 jika emiten sudah menyandang label resmi BEI pada `as_of_date` |
| `data_complete` | 0 / 1 | 1 jika data cukup lengkap untuk diberi skor |
| `feature_max_source_date` | tanggal | Tanggal ketersediaan terbaru dari seluruh sumber yang dipakai baris ini. Kunci pemeriksaan kebocoran temporal |

Kepemilikan: taksonomi `event_category` dan definisi `is_event_90d` dimiliki peran Data dan Label. Peran Model dan Evaluasi menerima kolom ini sebagai masukan, tidak mendefinisikan ulang.

---

## 2. Variabel Mentah dari API

Data yang ditarik langsung dari Sectors API, belum dihitung apa pun. Tidak satupun dari variabel ini boleh muncul langsung di layar pengguna sebagai representasi skor risiko.

### 2.1 Dari laporan keuangan kuartalan

Sumber: endpoint Company Quarterly Financials.

| Variabel | Artinya sederhana |
|---|---|
| `revenue` | Pendapatan usaha pada kuartal itu |
| `earnings` | Laba bersih perusahaan pada kuartal itu |
| `total_equity` | Kekayaan bersih perusahaan, aset dikurangi utang |
| `total_liabilities` | Total utang perusahaan |
| `total_assets` | Total aset perusahaan |
| `total_debt` | Utang berbunga saja, bagian dari total utang |
| `operating_cash_flow` | Uang tunai yang dihasilkan dari kegiatan usaha inti |
| `free_cash_flow` | Uang tunai tersisa setelah pengeluaran operasional dan investasi |
| `report_date` | Tanggal laporan itu resmi diterbitkan |

### 2.2 Dari data harga harian

Sumber: endpoint Daily Transaction Data dan Daily Full-Universe Close.

| Variabel | Artinya sederhana |
|---|---|
| `close` | Harga penutupan saham pada satu hari |
| `volume` | Jumlah lembar saham yang diperdagangkan pada satu hari |
| `market_cap` | Nilai total perusahaan di pasar pada hari itu |

### 2.3 Dari struktur kepemilikan

Sumber: endpoint Free Float Market Analysis.

| Variabel | Artinya sederhana |
|---|---|
| `free_float` | Persentase saham yang dipegang publik, bukan pendiri atau pemegang saham utama |

**Peringatan pemakaian:** `free_float` kemungkinan besar hanya tersedia sebagai nilai terkini, bukan riwayat historis. Karena itu variabel ini hanya boleh dipakai saat menghitung skor emiten hari ini, tidak boleh dipakai saat melatih model dari sampel historis. Memakainya untuk data lama akan membocorkan informasi masa depan ke dalam data masa lalu.

---

## 3. Variabel Turunan: Indikator Risiko

Bagian paling penting dari dokumen ini. Setiap variabel di sini dihitung dari variabel mentah pada bagian 2, tidak ada satupun yang disalin langsung. Inilah yang membuat AMBA memenuhi syarat wawasan turunan pada Track 3.

### 3.1 Kelompok kepatuhan pelaporan

| Variabel | Rumus | Kenapa relevan |
|---|---|---|
| `lapor_jarak_hari` | `as_of_date` dikurangi `report_date` terakhir, dalam hari | Emiten bermasalah sering telat lapor sebelum masalah lain terlihat di data lain |
| `lapor_terlambat` | 1 jika `lapor_jarak_hari` melampaui tenggat wajib, 0 jika tidak | Versi biner dari indikator di atas, gampang ditampilkan sebagai status |

### 3.2 Kelompok kesehatan finansial

| Variabel | Rumus | Kenapa relevan |
|---|---|---|
| `tanpa_pendapatan` | 1 jika `revenue` nol atau mendekati nol | Sejalan dengan kriteria notasi khusus BEI untuk emiten tanpa pendapatan usaha |
| `ekuitas_negatif` | 1 jika `total_equity` di bawah nol | Utang perusahaan sudah melebihi total asetnya |
| `utang_terhadap_aset` | `total_liabilities` dibagi `total_assets` | Makin tinggi, makin besar porsi perusahaan yang dibiayai utang |
| `ako_negatif_berturut` | Jumlah kuartal berturut-turut `operating_cash_flow` di bawah nol | Kegiatan usaha yang terus mengeluarkan uang lebih banyak daripada yang masuk |

### 3.3 Kelompok likuiditas dan perilaku harga

| Variabel | Rumus | Kenapa relevan |
|---|---|---|
| `hari_tanpa_transaksi_90d` | Jumlah hari `volume` bernilai nol dalam 90 hari terakhir | Saham yang jarang diperdagangkan sulit dijual saat dibutuhkan |
| `rasio_volume_30_90` | Rata-rata `volume` 30 hari dibagi rata-rata `volume` 90 hari | Menunjukkan apakah minat pasar terhadap saham ini sedang mengering |
| `hari_di_batas_bawah_90d` | Jumlah hari `close` bernilai Rp50, batas harga terendah yang diizinkan BEI | Harga menempel di batas bawah adalah tanda kelemahan ekstrem |
| `turun_dari_puncak_90d` | Selisih relatif `close` hari ini terhadap `close` tertinggi dalam 90 hari | Mengukur seberapa jauh saham sudah jatuh dari titik terbaiknya |
| `volatilitas_90d` | Simpangan baku imbal hasil harian selama 90 hari | Makin liar naik turunnya harga, makin tidak stabil kondisinya |

### 3.4 Kelompok struktur kepemilikan, hanya untuk skor terkini

| Variabel | Rumus | Catatan pemakaian |
|---|---|---|
| `free_float_rendah` | 1 jika `free_float` di bawah ambang tertentu | Hanya dipakai saat scoring live, tidak dipakai saat pelatihan, sesuai peringatan pada bagian 2.3 |

Kepemilikan: seluruh rumus pada bagian 3 dimiliki peran Data dan Label untuk implementasinya, tetapi didefinisikan bersama dengan peran Model dan Evaluasi karena berpengaruh langsung pada apa yang bisa dipelajari model.

---

## 4. Variabel Keluaran: Yang Tampil ke Pengguna

Hasil akhir setelah seluruh indikator pada bagian 3 digabungkan oleh model atau rumus rule-based. Ini yang mengisi berkas `artifacts/scores.json`.

| Variabel | Tipe | Artinya |
|---|---|---|
| `skor` | angka | Hasil mentah model atau rumus. Tidak ditampilkan langsung ke pengguna karena tidak bermakna sendirian |
| `persentil` | angka 0-100 | Posisi emiten dibanding emiten lain, misalnya "lebih berisiko dibanding 94 persen emiten lain". Ini yang ditampilkan ke pengguna, bukan `skor` mentah |
| `kategori` | teks | Rendah, Sedang, Tinggi, atau Sangat Tinggi. Hasil pengelompokan dari `persentil` |
| `arah_30h` | naik / turun / stabil | Perbandingan `persentil` hari ini dengan posisi 30 hari lalu |
| `status` | teks | `dinilai`, `sudah_ditandai`, atau `tidak_dapat_dinilai`. Memisahkan emiten yang sudah kena label resmi dari peringkat utama |
| `indikator_dominan` | teks | Nama indikator dari bagian 3 yang paling besar menyumbang ke skor emiten tersebut |
| `kontribusi` (per indikator) | angka | Untuk regresi logistik, dihitung dari koefisien dikali nilai terstandardisasi. Mengisi rincian di halaman Detail Emiten |

**Aturan penyajian yang mengikat:** `skor` tidak pernah disajikan sebagai probabilitas ("kemungkinan 73 persen"), karena itu mengklaim model terkalibrasi, sesuatu yang tidak bisa dipertahankan dengan jumlah sampel sekecil ini. Selalu disajikan sebagai `persentil`.

**Aturan status yang mengikat:** emiten dengan `already_flagged` bernilai 1 tidak boleh mendominasi peringkat utama meski `skor`-nya tinggi. Field `status` harus memisahkannya secara eksplisit, karena produk ini menjual peringatan sebelum label resmi, bukan pengulangan label yang sudah ada.

---

## 5. Variabel Evaluasi

Tidak dilihat pengguna. Dipakai tim untuk mengukur apakah model bekerja, dan mengisi berkas `artifacts/backtest.json`.

| Variabel | Artinya |
|---|---|
| `precision_at_20` | Dari 20 emiten skor tertinggi pada satu potret, berapa persen yang benar-benar mengalami peristiwa dalam 90 hari |
| `recall_90h` | Dari seluruh peristiwa yang terjadi dalam 90 hari, berapa persen berhasil masuk 20 besar |
| `auc` | Ukuran seberapa baik model membedakan emiten berisiko dari yang tidak. Pembanding umum antar model, tidak ditampilkan sebagai klaim utama |
| `akurasi` | Proporsi prediksi benar. **Dihitung untuk keperluan internal saja, tidak pernah dilaporkan ke publik**, karena menyesatkan pada kelas yang timpang |
| `selisih_hari` | Berapa hari `persentil` mulai melewati ambang lebih awal dibanding `event_date` resmi |
| `kejadian_terlewat` | Kasus di mana `persentil` tidak pernah melewati ambang sebelum `event_date` terjadi |
| `alarm_palsu` | Kasus di mana `persentil` melewati ambang tapi tidak ada `is_event_90d` yang terjadi |

---

## 6. Peta Endpoint ke Variabel Mentah

Ringkasan dari mana tiap variabel pada bagian 2 berasal, supaya siapapun yang butuh menarik ulang data tahu endpoint yang tepat.

| Variabel mentah | Endpoint sumber |
|---|---|
| `revenue`, `earnings`, `total_equity`, `total_liabilities`, `total_assets`, `total_debt`, `operating_cash_flow`, `free_cash_flow` | Company Quarterly Financials |
| `report_date` | Quarterly Financial Dates, atau Latest Quarterly Financial Dates untuk seluruh emiten sekaligus |
| `close`, `volume`, `market_cap` (per emiten, riwayat panjang) | Daily Transaction Data |
| `close`, `market_cap` (seluruh emiten, satu hari) | Daily Full-Universe Close |
| `free_float` | Free Float Market Analysis |
| Label suspensi (`event_date`, `event_category`, sumber untuk `is_event_90d`) | Stock Suspensions |

---

## 7. Contoh Satu Baris Data Lengkap

Ilustrasi bagaimana seluruh lapis variabel terhubung untuk satu emiten pada satu tanggal.

```
Identitas:
  symbol = "XYZA"
  as_of_date = "2025-02-15"
  sector = "consumer-non-cyclicals"
  board = "Development"
  is_event_90d = 1
  event_date = "2025-04-02"
  event_category = "C"
  already_flagged = 0
  data_complete = 1

Variabel mentah (contoh sebagian):
  revenue = 0
  total_equity = -12000000000
  report_date = "2024-11-14"
  close = 51
  volume = 0

Variabel turunan:
  lapor_jarak_hari = 93
  lapor_terlambat = 1
  tanpa_pendapatan = 1
  ekuitas_negatif = 1
  hari_tanpa_transaksi_90d = 34
  hari_di_batas_bawah_90d = 12

Variabel keluaran (hasil model):
  skor = 0.81
  persentil = 96.4
  kategori = "Sangat Tinggi"
  status = "dinilai"
  indikator_dominan = "ekuitas_negatif"
```

Emiten fiktif di atas menunjukkan pola khas: telat lapor sekitar tiga bulan, ekuitas negatif, tanpa pendapatan, dan harga sudah menempel di batas bawah. Kombinasi ini yang menghasilkan skor tinggi 47 hari sebelum peristiwa suspensi terjadi.

---

## 8. Ringkasan Jumlah Variabel

| Lapis | Jumlah variabel |
|---|---|
| Identitas dan label | 10 |
| Mentah dari API | 13 |
| Turunan / indikator | 11 |
| Keluaran ke pengguna | 7 |
| Evaluasi internal | 7 |

Satu baris data untuk satu emiten pada satu tanggal membawa sekitar 23 variabel masukan (identitas plus mentah), diolah menjadi 11 indikator turunan, lalu diringkas menjadi sekitar 7 variabel yang benar-benar dilihat pengguna di layar.

---

## 9. Kepemilikan Antar Peran

| Bagian | Dimiliki oleh |
|---|---|
| Identitas dan label (bagian 1) | Peran Data dan Label |
| Variabel mentah (bagian 2) | Peran Data dan Kredit, sesuai pembungkus API |
| Variabel turunan (bagian 3) | Bersama, rumus disepakati Data dan Model |
| Variabel keluaran (bagian 4) | Peran Model dan Evaluasi, dikonsumsi Front-End |
| Variabel evaluasi (bagian 5) | Peran Model dan Evaluasi |

Perubahan pada definisi variabel apapun di dokumen ini wajib diumumkan ke seluruh tim, karena satu perubahan definisi bisa memutus kontrak data antara dua peran tanpa ada yang sadar sampai hasilnya aneh.
