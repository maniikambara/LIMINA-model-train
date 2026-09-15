# AMBANG: Rancangan Kerja Peran Model dan Evaluasi

**Proyek:** AMBANG, sistem peringatan dini risiko suspensi emiten IDX
**Kompetisi:** Sectors Hackathon 2026, Track 03 Market Intelligence
**Peran:** Model dan Evaluasi
**Periode:** 27 Agustus sampai 30 September 2026
**Status dokumen:** rancangan pra-implementasi

Seluruh angka anggaran dalam dokumen ini adalah perkiraan dan wajib diperbarui setelah verifikasi. Dokumen ini bukan laporan hasil.

---

## 1. Cakupan Peran

### Yang dimiliki peran ini

1. Kerangka evaluasi: pemisahan data, metrik, pembanding dasar, pelaporan
2. Model klasifikasi dan penyetelannya
3. Perhitungan skor, persentil, dan kontribusi indikator
4. Perhitungan selisih waktu terhadap label resmi
5. Analisis alarm palsu dan kejadian terlewat
6. Penegakan pemeriksaan kebocoran pada data yang masuk
7. Eksekusi gerbang keputusan 10 September
8. Dua berkas artefak keluaran untuk antarmuka

### Yang bukan milik peran ini

1. Taksonomi alasan suspensi dan definisi label, dimiliki peran data
2. Rumus indikator dan pengambilan data mentah, dimiliki peran data
3. Tampilan antarmuka, dimiliki peran front-end
4. Naskah dan produksi video, dimiliki pemegang narasi

### Batas yang perlu ditegaskan

Peran ini berada di hilir. Jika data yang masuk cacat, hasil peran ini ikut cacat tanpa peran ini bisa mencegahnya. Karena itu pemeriksaan kebocoran dijalankan sebagai gerbang masuk, dan data yang gagal dikembalikan ke pemiliknya, bukan diperbaiki diam-diam. Perbaikan diam-diam menghilangkan gejalanya tetapi membiarkan penyebabnya, dan masalah yang sama akan muncul lagi minggu berikutnya.

---

## 2. Dua Permintaan yang Harus Diajukan Hari Ini

Kedua permintaan ini menentukan apakah pekerjaan peran ini bisa diselesaikan. Ajukan tertulis, bukan lisan, sebelum pengambilan data besar dimulai. Setelah data ditarik, biaya perubahan menjadi dua kali lipat.

### Permintaan 1: dataset berbentuk panel

Dataset satu baris per peristiwa sudah cukup untuk melatih model, tetapi tidak cukup untuk menghitung selisih waktu. Halaman Bukti membutuhkan skor emiten pada banyak titik waktu, bukan satu.

Bentuk yang diminta: satu baris per kombinasi emiten dan tanggal, berkala mingguan, mencakup 12 bulan sebelum tanggal peristiwa untuk setiap emiten positif, dan periode setara untuk emiten pembanding.

### Permintaan 2: enam tanggal potret uji

Bukan satu potret, melainkan enam, berjarak kuartalan sepanjang 18 bulan. Perbedaannya menentukan kekuatan klaim:

| Dengan satu potret | Dengan enam potret |
|---|---|
| Precision@20 kami 0,35 | Precision@20 kami berkisar 0,28 sampai 0,41 pada enam kuartal berbeda |
| Juri tidak dapat membedakan hasil ini dari kebetulan | Terbukti bertahan lintas kondisi pasar |

Tanggal yang diusulkan, dengan syarat jendela label 90 hari sesudahnya sudah selesai teramati:

```
2025-01-15
2025-04-15
2025-07-15
2025-10-15
2026-01-15
2026-04-15
```

Tanggal terakhir ditambah 90 hari jatuh pada pertengahan Juli 2026, sehingga seluruh jendela label sudah dapat diamati pada saat pengerjaan.

---

## 3. Kontrak Data Masuk

Skema di bawah ini disepakati dengan peran data sebelum ada data asli, agar pekerjaan peran ini dapat dimulai menggunakan data sintetis.

### 3.1 Berkas panel

Nama berkas: `data/panel.parquet`

| Kolom | Tipe | Keterangan |
|---|---|---|
| `symbol` | str | Kode emiten empat huruf |
| `as_of_date` | date | Titik potong, seluruh indikator dihitung pada tanggal ini |
| `is_event_90d` | int | 1 jika peristiwa kategori C terjadi pada rentang setelah `as_of_date` sampai 90 hari sesudahnya |
| `event_date` | date atau kosong | Tanggal peristiwa, jika ada |
| `event_category` | str atau kosong | A, B, atau C sesuai taksonomi peran data |
| `already_flagged` | int | 1 jika emiten sudah menyandang label resmi pada `as_of_date` |
| `data_complete` | int | 1 jika data cukup untuk diberi skor |
| `sector` | str | Sektor |
| `board` | str | Papan pencatatan |
| `feature_max_source_date` | date | Tanggal ketersediaan terbaru dari seluruh data yang dipakai baris ini |

Kolom indikator, seluruhnya dihitung pada `as_of_date`:

| Kolom | Tipe | Keterangan |
|---|---|---|
| `lapor_jarak_hari` | int | Selisih hari antara laporan kuartalan terakhir dan titik potong |
| `lapor_terlambat` | int | 1 jika melampaui tenggat wajib |
| `tanpa_pendapatan` | int | 1 jika pendapatan usaha nol atau mendekati nol |
| `ekuitas_negatif` | int | 1 jika total ekuitas di bawah nol |
| `utang_terhadap_aset` | float | Total liabilitas dibagi total aset |
| `ako_negatif_berturut` | int | Jumlah kuartal berturut-turut arus kas operasi negatif |
| `hari_tanpa_transaksi_90d` | int | Jumlah hari volume nol dalam 90 hari terakhir |
| `rasio_volume_30_90` | float | Rata-rata volume 30 hari dibagi rata-rata volume 90 hari |
| `hari_di_batas_bawah_90d` | int | Jumlah hari harga berada di Rp50 |
| `turun_dari_puncak_90d` | float | Selisih relatif harga terhadap puncak 90 hari |
| `volatilitas_90d` | float | Simpangan baku imbal hasil harian 90 hari |

Kolom `feature_max_source_date` adalah kunci pemeriksaan kebocoran. Tanpa kolom ini, kebocoran tidak dapat dideteksi secara otomatis dan seluruh hasil tidak dapat dipertanggungjawabkan.

### 3.2 Berkas potret

Nama berkas: `data/snapshot_<tanggal>.parquet`

Skema sama dengan panel, dengan tambahan syarat: berisi **seluruh** emiten dalam cakupan pada tanggal tersebut, bukan sampel berimbang. Inilah yang membuat angka precision menjadi realistis.

---

## 4. Kerangka Evaluasi

### 4.1 Pemisahan data

Pemisahan bersifat temporal, tidak pernah acak.

```
Latih : seluruh peristiwa dengan event_date sebelum 2025-01-01
Uji   : enam potret pada 2025 sampai 2026
```

Validasi silang acak akan mencampur masa depan ke dalam data latih dan menghasilkan angka yang menyesatkan. Jika ada anggota tim yang mengusulkan k-fold acak, tolak dengan alasan ini.

### 4.2 Ketimpangan kelas dan konsekuensinya

Peran data membangun sampel dengan perbandingan satu positif berbanding tiga negatif, sehingga 25 persen sampel latih bersifat positif. Di pasar sebenarnya, proporsinya mungkin sekitar 2 sampai 4 persen.

Akibatnya, precision yang diukur pada data latih berimbang akan **jauh lebih tinggi** daripada precision yang dialami pengguna. Melaporkan angka dari data berimbang sebagai performa produk adalah klaim yang salah.

Aturan yang mengikat:

- **Latih** dengan data berimbang dan pembobotan kelas.
- **Uji** hanya pada potret realistis yang memuat seluruh emiten.
- **Laporkan** hanya angka dari potret realistis.

### 4.3 Metrik

| Metrik | Rumus atau definisi | Ditampilkan publik |
|---|---|---|
| Precision@20 | Dari 20 emiten berskor tertinggi pada satu potret, berapa proporsi yang mengalami peristiwa dalam 90 hari | Ya, metrik utama |
| Recall 90 hari | Dari seluruh peristiwa dalam 90 hari setelah potret, berapa proporsi yang masuk 20 besar | Ya |
| Selisih waktu | Selisih hari antara saat skor pertama kali melewati ambang dan tanggal peristiwa | Ya, ini inti cerita produk |
| AUC | Area di bawah kurva ROC | Ya, sebagai pelengkap |
| Akurasi | Proporsi prediksi benar | **Tidak pernah** |

Alasan akurasi dilarang: dengan sekitar 900 emiten dan mungkin 20 sampai 40 peristiwa per tahun, model yang menebak seluruh emiten aman tanpa perhitungan apa pun akan mencapai akurasi di atas 95 persen. Metrik yang memberi nilai tinggi kepada model yang tidak bekerja bukan metrik yang berguna. Boleh dihitung untuk keperluan internal, tidak boleh muncul di README, video, maupun halaman metodologi.

### 4.4 Definisi selisih waktu

Perhitungan ini memerlukan panel dan tidak dapat dilakukan tanpa Permintaan 1.

1. Kalibrasi ambang pada data latih. Ambang ditetapkan sebagai skor pada persentil yang setara dengan 20 emiten teratas dari seluruh cakupan.
2. Untuk tiap emiten positif, telusuri panel dari 365 hari sebelum peristiwa sampai tanggal peristiwa.
3. Tandai tanggal pertama ketika skor melewati ambang **dan bertahan pada dua titik panel berturut-turut**. Syarat dua titik ini mencegah lonjakan sesaat dihitung sebagai peringatan.
4. Selisih waktu adalah jumlah hari antara tanggal tersebut dan tanggal peristiwa.
5. Jika skor tidak pernah melewati ambang, kasus tersebut dicatat sebagai **kejadian terlewat** dan dikeluarkan dari distribusi selisih waktu, tetapi tetap dilaporkan jumlahnya.

Melaporkan rata-rata selisih waktu tanpa menyebutkan jumlah kejadian terlewat adalah penyajian yang menyesatkan, karena rata-rata itu hanya berlaku pada kasus yang berhasil.

### 4.5 Pembanding dasar

Ketiganya dibangun sebelum model apa pun. Tanpa pembanding, angka model tidak memiliki arti.

| Pembanding | Definisi | Fungsi |
|---|---|---|
| Acak | Ambil 20 emiten sembarang dari cakupan | Lantai dasar mutlak |
| Aturan tunggal | Urutkan hanya berdasarkan `lapor_jarak_hari` | Menguji apakah satu indikator sudah cukup |
| Rule-based gabungan | Skor tertimbang dari kriteria Notasi Khusus, bobot ditetapkan di muka | Pembanding sebenarnya, sekaligus jalur cadangan |

Pembanding aturan tunggal adalah yang paling penting. Jika satu indikator saja sudah hampir sekuat model lengkap, itu temuan yang berharga dan layak diceritakan, bukan kegagalan.

Jika model tidak mengalahkan pembanding rule-based, itu bukan kegagalan peran ini. Itu jawaban yang benar, dan tim beralih jalur berdasarkan bukti kuantitatif, bukan karena menyerah.

---

## 5. Model

### 5.1 Pilihan model

**Utama:** regresi logistik dengan pembobotan kelas berimbang, regularisasi L2, seluruh fitur distandardisasi.

Alasannya bukan kesederhanaan semata. Kontribusi tiap indikator diperoleh langsung dari koefisien dikali nilai terstandardisasi, sehingga halaman Detail Emiten dapat menjelaskan skor tanpa alat tambahan, dan penjelasannya dapat disampaikan dalam satu kalimat pada video.

**Pembanding:** gradient boosting dengan kedalaman terbatas.

**Tidak dipakai:** deep learning dalam bentuk apa pun. Jumlah sampel tidak mendukung, dan tidak ada satu pun butir rubrik penilaian yang memberi nilai untuk itu.

### 5.2 Penyajian skor

Skor **tidak** disajikan sebagai probabilitas. Menyebut angka seperti kemungkinan 73 persen berarti mengklaim model terkalibrasi, dan kalibrasi memerlukan pengujian tersendiri dengan jumlah sampel yang tidak tersedia.

Skor disajikan sebagai persentil terhadap seluruh cakupan, misalnya lebih berisiko dibanding 94 persen emiten lain, dengan kategori Rendah, Sedang, Tinggi, dan Sangat Tinggi sebagai lapisan tambahan.

### 5.3 Penyetelan

Penyetelan dilakukan hanya pada data latih, menggunakan pemisahan temporal internal, yaitu peristiwa paling akhir dalam data latih dijadikan data validasi. Potret uji tidak boleh disentuh sampai gerbang 10 September.

Setiap kali potret uji dilihat lalu model diubah, potret itu kehilangan sifatnya sebagai data uji. Batasi menjadi satu kali evaluasi akhir.

---

## 6. Pemeriksaan Kebocoran

Kebocoran temporal adalah satu-satunya kesalahan yang membuat seluruh hasil tidak sah tanpa memunculkan pesan galat apa pun. Empat pemeriksaan berikut dijalankan otomatis pada setiap dataset yang masuk.

### Pemeriksaan 1: tanggal sumber

```
untuk setiap baris:
    pastikan feature_max_source_date <= as_of_date
```

Gagal berarti dataset dikembalikan ke peran data, tidak diperbaiki sendiri.

### Pemeriksaan 2: pengacakan label

Acak seluruh label, latih ulang, hitung AUC. Hasil yang benar berada di sekitar 0,50. Jika masih jauh di atas itu, ada kesalahan pada alur pemrosesan, bukan pada data.

### Pemeriksaan 3: fitur kendali

Sisipkan satu kolom berisi bilangan acak. Jika kolom tersebut muncul sebagai indikator berpengaruh, ada kesalahan pada perhitungan kepentingan fitur.

### Pemeriksaan 4: batas kewajaran

AUC di atas 0,90 pada percobaan pertama diperlakukan sebagai gejala kebocoran, bukan keberhasilan. Hentikan, telusuri, laporkan ke tim.

Tanamkan ini sebagai refleks: **hasil yang terlalu bagus adalah gejala, bukan kabar baik.**

---

## 7. Gerbang Keputusan 10 September

Angka di bawah ini diumumkan ke tim paling lambat 1 September, sebelum ada hasil apa pun. Gerbang yang disepakati sebelum hasil keluar jauh lebih mudah dijalankan daripada gerbang yang diusulkan setelah hasilnya mengecewakan.

| Kondisi | Keputusan |
|---|---|
| Model mengalahkan pembanding rule-based pada Precision@20 di mayoritas potret | Jalur machine learning diteruskan |
| Model setara atau lebih buruk | Rule-based menjadi mesin utama, model tetap ditampilkan sebagai pembanding di halaman metodologi |
| AUC di bawah 0,60 | Rule-based penuh, dieksekusi hari itu juga |

Pada seluruh cabang, permukaan produk, isi video, dan tujuan penggunaan tidak berubah. Hanya mesin di belakangnya yang berbeda. Peralihan jalur adalah keputusan terjadwal, bukan kegagalan.

---

## 8. Artefak Keluaran

Dua berkas ini adalah kontrak peran ini kepada front-end. Strukturnya disepakati sebelum data asli tersedia, agar front-end dapat bekerja paralel menggunakan berkas tiruan.

### 8.1 `artifacts/scores.json`

```json
{
  "dibuat_pada": "2026-09-15",
  "cakupan": {
    "total_emiten": 0,
    "diberi_skor": 0,
    "tidak_dapat_dinilai": 0,
    "sudah_ditandai": 0
  },
  "model": {
    "jenis": "regresi_logistik",
    "dilatih_pada": "peristiwa sebelum 2025-01-01",
    "jumlah_sampel_positif_latih": 0
  },
  "ambang": {
    "persentil": 97.8,
    "nilai": 0.0
  },
  "emiten": [
    {
      "symbol": "XXXX",
      "nama": "",
      "sektor": "",
      "papan": "",
      "status": "dinilai",
      "skor": 0.0,
      "persentil": 0.0,
      "kategori": "Tinggi",
      "arah_30h": "naik",
      "delta_30h": 0.0,
      "indikator": [
        {
          "nama": "lapor_jarak_hari",
          "label": "Keterlambatan laporan keuangan",
          "nilai_mentah": 0,
          "ambang": 0,
          "kontribusi": 0.0,
          "penjelasan": "Laporan kuartalan terakhir sudah lewat sekian hari dari tenggat"
        }
      ],
      "data_terakhir": "2026-09-10"
    }
  ]
}
```

Medan `status` memiliki tiga nilai: `dinilai`, `sudah_ditandai`, dan `tidak_dapat_dinilai`. Pemisahan ini penting. Emiten yang sudah menyandang label resmi tidak boleh mendominasi peringkat utama, karena produk ini menjual peringatan sebelum label, bukan pengulangan label. Emiten berdata tidak lengkap tidak boleh terlihat aman, karena statusnya sebenarnya tidak diketahui.

### 8.2 `artifacts/backtest.json`

```json
{
  "ringkasan": {
    "jumlah_potret": 6,
    "jumlah_sampel_positif_latih": 0,
    "jumlah_peristiwa_pada_periode_uji": 0,
    "selisih_waktu_median_hari": 0,
    "selisih_waktu_p25_hari": 0,
    "selisih_waktu_p75_hari": 0,
    "kejadian_terlewat": 0,
    "rata_rata_alarm_palsu_per_potret": 0.0
  },
  "potret": [
    {
      "tanggal": "2025-01-15",
      "emiten_dinilai": 0,
      "peristiwa_dalam_90_hari": 0,
      "precision_at_20": 0.0,
      "recall_90h": 0.0,
      "auc": 0.0,
      "pembanding": {
        "acak": 0.0,
        "aturan_tunggal": 0.0,
        "rule_based": 0.0
      }
    }
  ],
  "studi_kasus": [
    {
      "symbol": "XXXX",
      "tanggal_peristiwa": "2025-06-10",
      "kategori_alasan": "C",
      "selisih_hari": 0,
      "riwayat_skor": [
        {"tanggal": "2024-06-15", "skor": 0.0, "persentil": 0.0}
      ]
    }
  ],
  "alarm_palsu": [
    {
      "symbol": "XXXX",
      "tanggal_potret": "2025-04-15",
      "persentil": 0.0,
      "indikator_dominan": "",
      "apa_yang_terjadi": "Tidak ada peristiwa dalam 90 hari"
    }
  ],
  "kejadian_terlewat": [
    {
      "symbol": "XXXX",
      "tanggal_peristiwa": "2025-09-02",
      "persentil_tertinggi_sebelumnya": 0.0,
      "dugaan_penyebab": ""
    }
  ]
}
```

Dua medan terakhir, `alarm_palsu` dan `kejadian_terlewat`, adalah yang paling menentukan kredibilitas produk. Halaman Bukti yang hanya memuat kasus berhasil adalah pemilihan ceri, dan juri yang teliti akan menyadarinya. Menampilkan kegagalan sendiri menaikkan kepercayaan secara tajam dan konsisten dengan sikap jujur yang sudah diambil di seluruh dokumen proyek.

---

## 9. Struktur Modul

```
src/eval/
  contracts.py     Skema dataset dan validator
  synth.py         Pembangkit data sintetis sesuai kontrak
  splits.py        Pemisahan temporal
  metrics.py       Precision@k, recall, AUC, selisih waktu
  baselines.py     Tiga pembanding dasar
  leakage.py       Empat pemeriksaan kebocoran
  models.py        Regresi logistik dan gradient boosting
  snapshot.py      Evaluasi potret realistis
  export.py        Penulis scores.json dan backtest.json
  report.py        Ringkasan hasil ke berkas markdown
tests/
  test_metrics.py  Uji metrik dengan kasus yang jawabannya diketahui
  test_leakage.py  Uji pemeriksa dengan dataset yang sengaja dibocorkan
```

Berkas `synth.py` adalah yang pertama dibuat. Dengan berkas itu, seluruh modul lain dapat dibangun dan diuji tanpa menunggu data asli.

Berkas `test_metrics.py` menguji perhitungan metrik menggunakan kasus buatan yang jawabannya sudah diketahui secara manual. Metrik yang salah hitung akan menghasilkan angka yang terlihat wajar tetapi keliru, dan kesalahan seperti itu tidak akan pernah ketahuan tanpa pengujian.

---

## 10. Anggaran Kredit

Tiap anggota memiliki kredit dari akunnya sendiri, sekitar 600. Konfirmasi tertulis dari panitia sudah diperoleh mengenai pemakaian kunci masing-masing anggota untuk proyek tim yang sama.

Angka berikut adalah perkiraan, dengan asumsi satu panggilan setara satu kredit. Verifikasi apakah tiap halaman pagination dihitung terpisah, karena jawabannya mengubah seluruh tabel.

| Keperluan | Perkiraan | Penanggung |
|---|---|---|
| Panel historis untuk selisih waktu | 200 sampai 300 | Peran data |
| Enam potret, data level universe | 120 sampai 180 | Peran ini |
| Cadangan pengulangan potret | 100 | Peran ini |
| Cadangan tidak disentuh sampai 22 September | 150 | Peran ini |

Disiplin yang berlaku meskipun kredit lebih longgar:

1. **Satu cache bersama, bukan empat.** Jika tiap orang menarik ke folder masing-masing, akan muncul empat versi dataset dan tidak ada yang tahu mana yang dipakai model.
2. **Catat asal tiap berkas**, yaitu diambil kapan dan oleh kunci siapa. Juri boleh memeriksa repositori, dan riwayat pengambilan yang rapi memperkuat kesan proyek ini nyata.
3. **Tidak ada kunci API di repositori.** Empat kunci berarti empat peluang bocor.
4. **Pencatat kredit tetap wajib**, kini per akun, bukan hanya total.

Yang tidak berubah karena kelonggaran kredit: jumlah sampel positif tetap terbatas oleh sejarah bursa, batasan sebenarnya tetap waktu dan jumlah orang, dan kedua gerbang keputusan tetap berlaku.

---

## 11. Kalender Kerja

| Tanggal | Target |
|---|---|
| 27 Agustus | Ajukan Permintaan 1 dan 2 secara tertulis. Sepakati kontrak dataset dan kontrak artefak |
| 28 sampai 31 Agustus | `synth.py`, `contracts.py`, `metrics.py`, `splits.py`, `baselines.py`, `leakage.py` selesai dan teruji di atas data sintetis |
| 1 September | Umumkan angka gerbang 10 September ke tim |
| 1 sampai 7 September | `snapshot.py` dan perhitungan selisih waktu selesai. Kerangka diuji ulang menyeluruh |
| 7 September | Terima dataset asli. Jalankan empat pemeriksaan kebocoran sebelum menyentuh model |
| 8 sampai 10 September | Model asli, penyetelan pada data latih, evaluasi tunggal pada potret uji |
| 10 September | Eksekusi gerbang |
| 11 sampai 15 September | Ekspor `scores.json` dan `backtest.json` ke front-end |
| 16 sampai 19 September | Analisis alarm palsu dan kejadian terlewat |
| 20 September | Serahkan seluruh angka final ke pemegang narasi. Model tidak disentuh lagi |
| 21 sampai 30 September | Dukungan angka untuk video dan halaman metodologi saja |

Jika target 31 Agustus tercapai, tersedia cadangan waktu tujuh hari. Simpan cadangan itu, jangan dipakai menambah kerumitan model.

---

## 12. Kontribusi ke Video

Pemegang narasi membutuhkan tiga angka dari peran ini, dan hanya tiga. Serahkan paling lambat 20 September dalam bentuk kalimat jadi, bukan tabel mentah.

1. **Selisih waktu median.** Contoh bentuk kalimat: skor kami naik rata-rata sekian hari sebelum label resmi terbit.
2. **Precision@20 lintas potret.** Contoh bentuk kalimat: dari 20 emiten teratas, sekian yang benar-benar mengalami peristiwa dalam 90 hari, konsisten pada enam kuartal berbeda.
3. **Jumlah sampel dan jumlah kegagalan.** Disebutkan terbuka, tanpa dibulatkan ke atas.

Angka ketiga yang paling sering dihilangkan tim lain, dan justru yang paling menaikkan kepercayaan juri.

---

## 13. Yang Tidak Dilakukan

Daftar ini sama mengikatnya dengan daftar pekerjaan.

1. Tidak melaporkan akurasi di mana pun yang dilihat publik
2. Tidak menyajikan skor sebagai probabilitas
3. Tidak memakai validasi silang acak
4. Tidak memakai deep learning
5. Tidak memperbaiki data bocor secara diam-diam, melainkan mengembalikannya
6. Tidak melihat potret uji lebih dari satu kali evaluasi akhir
7. Tidak mengubah model setelah 20 September
8. Tidak menambah indikator setelah gerbang 10 September

---

## 14. Keterbatasan yang Diakui

Bagian ini diperbarui setelah hasil ada, bukan dihapus.

1. **Jumlah sampel positif kemungkinan kecil**, sehingga selang kepercayaan seluruh metrik lebar. Angka sampel dilaporkan apa adanya.
2. **Ambang skor dikalibrasi pada data latih**, sehingga bergantung pada periode pelatihan dan dapat bergeser jika kondisi pasar berubah.
3. **Selisih waktu hanya dihitung pada kasus yang berhasil ditandai.** Kejadian terlewat dilaporkan terpisah dan tidak boleh disembunyikan di balik nilai rata-rata.
4. **Model tidak dapat melihat informasi non-publik.** Sebagian peristiwa dipicu hal yang tidak meninggalkan jejak pada data pasar maupun laporan keuangan.
5. **Cakupan potret dibatasi oleh anggaran kredit.** Batasnya disebutkan terbuka pada halaman metodologi, sebagai keputusan rekayasa dan bukan kekurangan yang disembunyikan.
6. **Kontribusi indikator berasal dari model linear.** Jika jalur gradient boosting yang dipilih, metode penjelasannya harus diganti dan keterbatasan ini diperbarui.
