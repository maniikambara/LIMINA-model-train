# AMBANG

Sistem peringatan dini risiko suspensi untuk emiten Bursa Efek Indonesia.

**Status dokumen:** rancangan pra-implementasi
**Tanggal:** 27 Agustus 2026
**Konteks:** Sectors Hackathon 2026, Track 03 Market Intelligence
**Tim:** 4 orang
**Tenggat:** 30 September 2026, 23.59 WIB

Nama AMBANG adalah nama kerja dan boleh diganti. Nama ini dipilih karena inti produknya bukan meramal peristiwa, melainkan mengukur jarak sebuah emiten terhadap ambang batas risiko yang sudah dipublikasikan oleh BEI.

Seluruh angka dalam dokumen ini yang belum diverifikasi terhadap data ditandai sebagai perkiraan. Angka tersebut wajib diperbarui setelah Fase 1 selesai, dan dokumen ini bukan laporan hasil.

---

## 1. Ringkasan

Investor ritel pemegang saham lapis dua dan tiga umumnya baru mengetahui ada masalah pada emitennya ketika sahamnya sudah tidak bisa dijual. BEI memang menerbitkan Notasi Khusus dan memindahkan emiten bermasalah ke Papan Pemantauan Khusus, tetapi kedua mekanisme itu bersifat menandai kondisi yang sudah terjadi, bukan memperingatkan kondisi yang sedang terbentuk.

AMBANG menghitung ulang kriteria risiko tersebut secara berkelanjutan dari data Sectors, lalu menampilkan emiten mana yang sedang bergerak mendekati ambang batas, beserta alasan kuantitatif mengapa skornya naik.

Klaim produk ini bukan "kami memprediksi suspensi", melainkan "kami menghitung rubrik risiko yang sudah dipublikasikan lebih cepat daripada labelnya diterbitkan".

---

## 2. Masalah

Suspensi perdagangan menghentikan kemampuan pemegang saham untuk keluar dari posisinya. Tiga sifat suspensi membuat kerugiannya berat:

1. **Tidak ada batas waktu yang pasti.** Lama suspensi bergantung pada penyebab dan kemampuan emiten memenuhi kewajibannya kepada regulator.
2. **Konsekuensinya berlapis.** Saham yang dipindahkan ke Papan Pemantauan Khusus dikeluarkan dari indeks papan dan diperdagangkan dengan mekanisme call auction, sehingga likuiditasnya berubah drastis meskipun sahamnya belum disuspensi penuh.
3. **Peringatannya terlambat.** Notasi Khusus baru muncul setelah kondisinya terpenuhi. Notasi S misalnya baru diberikan setelah laporan keuangan terakhir menunjukkan tidak ada pendapatan usaha, dan notasi Y baru diberikan setelah lewat enam bulan tanpa RUPST.

Artinya, pada saat label resmi muncul, informasi yang mendasarinya sudah tersedia di data publik sejak beberapa waktu sebelumnya. Selisih waktu itulah yang menjadi ruang hidup produk ini.

---

## 3. Pengguna Sasaran

**Pengguna utama:** investor ritel yang memegang saham lapis dua dan tiga, memantau portofolionya sendiri, dan tidak memiliki akses ke riset sekuritas.

**Pengguna sekunder:** penulis dan pengelola komunitas investasi yang membutuhkan dasar kuantitatif ketika membahas emiten berisiko.

**Bukan pengguna sasaran:** investor institusional dan analis profesional, yang sudah memiliki proses pemantauan sendiri.

---

## 4. Lanskap Saat Ini

Pemetaan ini dilakukan sebelum pembangunan dimulai, untuk memastikan produk tidak mengulang sesuatu yang sudah ada.

| Lapis | Yang sudah ada | Batasannya |
|---|---|---|
| Regulator | Notasi Khusus dan Papan Pemantauan Khusus dari BEI | Label atas kondisi yang sudah terjadi, bersifat biner, bukan prediksi |
| Aplikasi ritel | Stockbit, RTI Business, BIONS, dan aplikasi sekuritas lain menampilkan notasi khusus | Meneruskan label BEI apa adanya, tidak ada perhitungan turunan |
| Akademik | Riset machine learning pasar modal Indonesia | Didominasi prediksi harga, sedikit yang menggarap suspensi atau financial distress |

BEI sendiri menyatakan bahwa Notasi Khusus hanya merupakan informasi awal dan investor sebaiknya mencari informasi yang lebih lengkap. AMBANG memposisikan diri sebagai lapisan tersebut.

**Celah yang diisi:** peringatannya sudah ada, unsur dininya belum.

---

## 5. Posisi Produk

### Yang diklaim

- Menghitung indikator risiko yang bersumber pada kriteria publik BEI, secara berkelanjutan dan untuk seluruh emiten dalam cakupan.
- Menampilkan peringkat emiten berdasarkan skor risiko, disertai penjelasan kontribusi tiap indikator.
- Menunjukkan bukti historis berupa selisih waktu antara naiknya skor dan terbitnya label resmi.

### Yang tidak diklaim

- Bukan prediksi kebangkrutan, kecurangan, atau delisting.
- Bukan rekomendasi beli, jual, atau tahan.
- Bukan pengganti pengumuman resmi BEI.
- Tidak memberikan estimasi durasi suspensi.

Pembatasan klaim ini bukan sekadar kehati-hatian hukum. Ini menyelaraskan produk dengan aturan kompetisi yang melarang pemberian saran investasi, sekaligus membuat klaimnya dapat diuji.

---

## 6. Wujud Akhir

Bagian ini menjawab pertanyaan "kalau sudah jadi, bentuknya seperti apa". Empat permukaan di bawah ini adalah definisi selesai. Apa pun di luar daftar ini dianggap di luar cakupan.

### 6.1 Halaman Peringkat

Daftar emiten dalam cakupan, diurutkan dari skor risiko tertinggi. Tiap baris memuat kode emiten, nama, skor, arah pergerakan skor dalam 30 hari terakhir, dan indikator paling dominan yang menaikkan skornya. Dilengkapi penyaring berdasarkan sektor dan papan pencatatan.

### 6.2 Halaman Detail Emiten

Menjawab satu pertanyaan: mengapa skor emiten ini tinggi.

Isinya adalah rincian kontribusi tiap indikator terhadap skor akhir, grafik pergerakan skor sepanjang riwayat yang tersedia, nilai mentah tiap indikator berdampingan dengan ambang batasnya, serta tanggal data terakhir yang dipakai. Tidak ada satu pun angka pada halaman ini yang bisa disalin langsung dari respons API tanpa perhitungan.

### 6.3 Halaman Bukti

Halaman ini yang membedakan produk dari dasbor biasa.

Berisi studi kasus emiten yang benar-benar pernah disuspensi, ditampilkan sebagai garis waktu: kapan skor AMBANG mulai naik, kapan label resmi terbit, dan berapa hari selisihnya. Disertai distribusi selisih waktu untuk seluruh kasus uji, serta jumlah sampel yang dipakai, ditulis terbuka tanpa dibulatkan ke atas.

### 6.4 Halaman Metodologi

Berisi definisi label, daftar indikator beserta rumusnya, penjelasan aturan point-in-time, cakupan data, keterbatasan yang diketahui, dan disclaimer. Ditulis untuk dibaca orang yang skeptis.

### 6.5 Alur Pemakaian

1. Pengguna membuka halaman peringkat dan mencari emiten yang dipegangnya.
2. Jika emiten itu berada di peringkat atas, pengguna membuka halaman detail untuk melihat indikator mana yang bermasalah.
3. Pengguna memverifikasi sendiri ke sumber resmi, misalnya laporan keuangan atau pengumuman BEI.
4. Pengguna mengambil keputusannya sendiri.

Produk berhenti di langkah ketiga. Langkah keempat sepenuhnya milik pengguna, dan itu disengaja.

---

## 7. Rancangan Sistem

### 7.1 Prinsip Arsitektur

Perhitungan dilakukan luring, hasilnya diekspor sebagai berkas statis, dan antarmuka hanya membaca berkas tersebut.

```
Sectors API  ->  Lapisan pengambilan  ->  Cache lokal  ->  Rekayasa fitur
                                                                |
                                                                v
Antarmuka statis  <-  Berkas artefak JSON  <-  Model dan pemberian skor
```

Konsekuensi yang disengaja:

- Tidak ada server yang perlu dijaga hidup.
- Kunci API tidak pernah berada di sisi klien.
- Antarmuka dapat ditempatkan di layanan hosting statis tanpa biaya.
- Perekaman video tidak bergantung pada ketersediaan jaringan atau sisa kuota.

Kompetisi tidak mewajibkan deployment langsung. Repositori publik dan video yang menunjukkan alur kerja inti sudah memenuhi syarat.

### 7.2 Sumber Data

Seluruh fitur berasal dari Sectors API. Produk kehilangan fungsi intinya jika data Sectors dicabut, sesuai persyaratan umum kompetisi.

| Kegunaan | Endpoint | Sifat biaya |
|---|---|---|
| Label historis | Stock Suspensions | Murah, terpaginasi |
| Deteksi keterlambatan lapor | Latest Quarterly Financial Dates (Universe) | Murah, satu feed untuk semua emiten |
| Fitur fundamental | Company Quarterly Financials | Sedang, per emiten |
| Fitur harga dan likuiditas | Daily Transaction Data | Sedang, jendela sampai 90 hari per panggilan |
| Pemberian skor seluruh pasar | Daily Full-Universe Close | Murah untuk cakupan luas |
| Struktur kepemilikan | Free Float Market Analysis | Murah, level universe |
| Cadangan, hanya jika kredit sisa | Broker Activity Per Symbol, Daily Net Foreign Inflow | Mahal, dibatasi 14 hari per panggilan |

Endpoint broker sengaja dikeluarkan dari rancangan awal. Batas 14 hari per panggilan membuat biayanya tidak sebanding pada tahap pelatihan.

### 7.3 Definisi Label

Tidak semua suspensi menandakan masalah. Emiten dapat meminta suspensi sendiri ketika ada aksi korporasi atau informasi material, dan banyak saham yang disuspensi kemudian diperdagangkan kembali.

Alasan resmi suspensi dikelompokkan menjadi tiga kategori:

| Kategori | Contoh | Perlakuan |
|---|---|---|
| A. Sukarela atau aksi korporasi | Permintaan emiten, menunggu keterbukaan informasi | Dibuang, bukan label positif |
| B. Teknis jangka pendek | Aktivitas pasar tidak wajar, lonjakan harga | Dibuang dari label utama, disimpan sebagai kelompok pembanding |
| C. Kepatuhan atau distress | Keterlambatan laporan keuangan, sanksi, going concern | Label positif |

Hanya kategori C yang menjadi label positif. Pengelompokan dilakukan dari medan alasan resmi pada endpoint suspensi, dan pemetaan lengkapnya disimpan sebagai berkas terpisah dalam repositori agar dapat diperiksa juri.

### 7.4 Indikator

Semua indikator dihitung pada titik potong T dikurangi 30 hari, dengan T adalah tanggal peristiwa.

**Kelompok kepatuhan pelaporan**

| Indikator | Definisi |
|---|---|
| Jarak lapor | Selisih hari antara tanggal laporan kuartalan terakhir dan titik potong |
| Status keterlambatan | Apakah jarak lapor melampaui tenggat wajib |

Kelompok ini diperkirakan paling murah sekaligus paling informatif, karena emiten bermasalah cenderung terlambat melapor sebelum gejala lain terlihat. Perkiraan ini wajib diuji, bukan diasumsikan.

**Kelompok kesehatan finansial**

| Indikator | Definisi | Rujukan |
|---|---|---|
| Tanpa pendapatan usaha | Pendapatan usaha nol atau mendekati nol pada laporan terakhir | Sejalan dengan kriteria notasi S |
| Ekuitas negatif | Total ekuitas di bawah nol | Indikator distress baku |
| Rasio utang terhadap aset | Total liabilitas dibagi total aset | Indikator distress baku |
| Arus kas operasi negatif | Jumlah kuartal berturut-turut dengan arus kas operasi negatif | Indikator distress baku |

**Kelompok likuiditas dan perilaku harga**

| Indikator | Definisi |
|---|---|
| Hari tanpa transaksi | Jumlah hari dengan volume nol dalam 90 hari terakhir |
| Pengeringan volume | Rasio rata-rata volume 30 hari terhadap 90 hari |
| Menempel di batas bawah | Jumlah hari harga berada di Rp50 |
| Penurunan dari puncak | Selisih harga terhadap puncak 90 hari |
| Volatilitas terealisasi | Simpangan baku imbal hasil harian 90 hari |

Catatan mengenai free float: jika endpoint hanya menyediakan nilai terkini dan bukan nilai historis, indikator ini akan bocor bila dipakai untuk sampel lama. Dalam kasus itu, free float hanya dipakai pada pemberian skor terkini dan tidak dipakai saat pelatihan. Keputusan ini beserta alasannya dicatat di halaman metodologi.

### 7.5 Aturan Point-in-Time

Satu aturan yang menentukan sah atau tidaknya seluruh hasil:

> Untuk sampel dengan tanggal peristiwa T, tidak boleh ada satu pun indikator yang memakai data yang baru tersedia setelah T dikurangi 30 hari.

Penegakannya bersifat teknis, bukan berupa kesepakatan lisan. Setiap sampel melewati fungsi pemeriksa yang membandingkan tanggal ketersediaan tiap sumber data terhadap titik potong, dan menggagalkan proses jika ada pelanggaran. Fungsi ini ditulis sebelum indikator pertama dibuat.

Pelanggaran paling mungkin terjadi pada data fundamental. Permintaan laporan keuangan terakhir untuk emiten yang disuspensi pada 2025 akan mengembalikan laporan 2026 jika tidak disaring. Penyaringan dilakukan menggunakan tanggal laporan dari endpoint helper, bukan dengan asumsi.

### 7.6 Sampel Pembanding

Setiap sampel positif dipasangkan dengan tiga sampel negatif yang memenuhi syarat berikut:

- Berasal dari jendela waktu yang sama, agar kondisi pasar setara.
- Berada pada papan pencatatan yang sebanding.
- Tidak mengalami peristiwa kategori C dalam 180 hari setelah titik potongnya.

Sampel negatif tidak boleh diambil hanya dari emiten yang masih tercatat hari ini, karena itu menimbulkan bias keberlangsungan.

### 7.7 Model dan Evaluasi

**Pemisahan data bersifat temporal, bukan acak.** Peristiwa sebelum 2025 untuk pelatihan, peristiwa 2025 sampai 2026 untuk pengujian. Validasi silang acak akan bocor dan menghasilkan angka yang menyesatkan.

**Model dijaga tetap sederhana.** Regresi logistik dengan pembobotan kelas sebagai model utama, gradient boosting sebagai pembanding. Deep learning tidak dipakai karena jumlah sampel tidak mendukung dan tidak menambah nilai pada rubrik penilaian.

**Metrik.** Akurasi tidak dilaporkan dalam bentuk apa pun, karena pada kelas yang sangat timpang akurasi tinggi dapat dicapai dengan menebak seluruh sampel sebagai negatif. Metrik yang dipakai:

| Metrik | Alasan |
|---|---|
| Precision@20 | Produk menampilkan 20 emiten teratas, jadi inilah yang benar-benar dialami pengguna |
| Rata-rata selisih waktu | Berapa hari skor naik lebih awal dibanding label resmi terbit |
| AUC | Pembanding umum, dilaporkan sebagai pelengkap |

**Jalur cadangan.** Jika jumlah sampel atau performa tidak memadai, mesin skor diganti menjadi rule-based memakai kriteria Notasi Khusus, dengan pembobotan yang ditetapkan di muka dan didokumentasikan. Seluruh permukaan produk, isi video, dan tujuan penggunaan tidak berubah. Hanya mesin di belakangnya yang berbeda.

### 7.8 Struktur Proyek

```
ambang/
  src/
    client.py            Pembungkus API, pencatat kredit, cache
    labels.py            Pengelompokan alasan suspensi, pembentukan label
    features.py          Perhitungan indikator
    pit.py               Pemeriksa point-in-time
    sampling.py          Pembentukan sampel pembanding
    model.py             Pelatihan dan evaluasi
    export.py            Penulisan artefak JSON
  data/
    cache/               Respons mentah, tidak masuk kontrol versi
    labels/              Pemetaan alasan suspensi
  artifacts/
    scores.json          Keluaran untuk antarmuka
    backtest.json        Data halaman bukti
  web/                   Antarmuka Vue 3, Vite, Tailwind
  notebooks/             Eksplorasi, bukan jalur produksi
  docs/
    metodologi.md
  README.md
```

Tumpukan teknologi: Python untuk seluruh alur data dan pemodelan, Vue 3 dengan Vite dan Tailwind untuk antarmuka, ApexCharts untuk grafik.

---

## 8. Anggaran Kredit API

Tim menerima 1.000 kredit dan jumlah itu tidak dapat ditambah. Tabel berikut adalah perkiraan, dengan asumsi satu panggilan sama dengan satu kredit. Asumsi ini wajib diverifikasi ke panitia sebelum pengambilan data besar dimulai, khususnya mengenai apakah tiap halaman pagination dihitung terpisah.

| Keperluan | Perkiraan kredit |
|---|---|
| Riwayat suspensi 36 bulan | 10 sampai 20 |
| Tanggal laporan kuartalan universe | 5 sampai 15 |
| Finansial kuartalan per emiten unik | 150 sampai 250 |
| Data harga per sampel | 240 sampai 320 |
| Free float | 1 sampai 5 |
| Pemberian skor seluruh cakupan | 100 sampai 150 |
| Cadangan tidak boleh disentuh | 150 |

Tiga aturan yang mengikat:

1. Seluruh panggilan melewati satu pembungkus yang mencatat endpoint, parameter, waktu, dan sisa kuota ke berkas log. Tidak ada yang memanggil API langsung dari notebook.
2. Setiap respons disimpan ke cache sejak panggilan pertama. Eksperimen, penyetelan, dan perekaman video berjalan dari cache.
3. Cadangan 150 kredit hanya boleh dibuka setelah 22 September.

---

## 9. Ukuran Keberhasilan

**Ukuran produk**

| Ukuran | Target |
|---|---|
| Cakupan emiten yang diberi skor | Seluruh emiten yang datanya memadai, jumlah pastinya dilaporkan apa adanya |
| Rata-rata selisih waktu terhadap label resmi | Positif dan konsisten pada data uji |
| Precision@20 | Lebih baik daripada dasar acak, selisihnya dilaporkan |

**Ukuran keterpakaian**

Pengguna dapat membuka produk, menemukan emiten yang dipegangnya, memahami alasan skornya, dan mengetahui data apa yang perlu diperiksa selanjutnya, tanpa membaca dokumentasi.

**Ukuran kejujuran**

Halaman metodologi memuat jumlah sampel sebenarnya, keterbatasan yang diketahui, dan indikator yang dibuang beserta alasannya. Ukuran ini setara pentingnya dengan dua ukuran di atas.

---

## 10. Rencana Kerja

Tersedia 34 hari, dari 27 Agustus sampai 30 September 2026.

### Fase 0, 27 sampai 28 Agustus, prasyarat

| Kegiatan | Catatan |
|---|---|
| Seluruh anggota menyelesaikan onboarding Sectors | Wajib sebelum satu baris kode ditulis, diverifikasi saat pemeriksaan kelayakan |
| Pendaftaran tim dan penguncian roster | Roster terkunci saat bonus kredit diklaim |
| Klaim 1.000 kredit | Setelah roster final |
| Pembuatan repositori | Wajib dibuat di dalam periode pembangunan |
| Pertanyaan penghitungan kredit ke panitia | Menentukan seluruh anggaran |
| Penetapan kontrak JSON antarmuka | Membuka kerja paralel sejak hari pertama |

### Fase 1, 28 sampai 31 Agustus, tulang punggung data

Keluaran fase ini bukan model, melainkan satu angka: jumlah sampel positif yang layak pakai setelah penyaringan.

Kegiatan: pembungkus API dan pencatat kredit, pengambilan riwayat suspensi, penyusunan taksonomi alasan, penghitungan sampel tersisa.

**Gerbang keputusan 31 Agustus**

| Jumlah sampel positif | Keputusan |
|---|---|
| 60 ke atas | Jalur machine learning |
| 25 sampai 60 | Jalur hibrida, skor rule-based sebagai mesin utama, model sebagai pembanding |
| Di bawah 25 | Jalur rule-based penuh berbasis kriteria Notasi Khusus |

Gerbang ini ditulis di README sebelum datanya ada, agar peralihan jalur menjadi keputusan terencana dan bukan kepanikan.

### Fase 2, 1 sampai 7 September, indikator

Fungsi pemeriksa point-in-time ditulis lebih dahulu, baru indikatornya. Diakhiri pembentukan sampel pembanding dan berkas dataset akhir.

### Fase 3, 8 sampai 10 September, model

Model dasar, pemisahan temporal, perhitungan Precision@20 dan selisih waktu, penghitungan kontribusi indikator untuk halaman detail.

**Gerbang keputusan 10 September.** Jika AUC berada di bawah sekitar 0,60 atau Precision@20 tidak lebih baik daripada dasar acak, jalur cadangan rule-based dijalankan pada hari itu juga. Tidak ada perpanjangan, tidak ada penambahan indikator, tidak ada negosiasi ulang.

### Fase 4, 11 sampai 19 September, permukaan produk

Empat halaman pada bagian 6 dibangun. Tidak ada penambahan fitur di luar daftar itu.

Yang secara tegas tidak dibangun: autentikasi, notifikasi, integrasi portofolio, pembaruan waktu nyata, aplikasi seluler, dan parameter backtest yang dapat diubah pengguna.

### Fase 5, 20 sampai 27 September, video

Fitur dibekukan pada 22 September. Setelah tanggal itu hanya perbaikan galat dan produksi video.

Bobot penilaian video adalah 30 persen, sehingga porsi waktunya memang harus mendekati sepertiga dari keseluruhan.

### Fase 6, 28 sampai 30 September, pengiriman

Pemeriksaan akhir, penghapusan seluruh kunci API, penulisan pernyataan masalah, unggah dua video, unggahan media sosial dengan menandai akun resmi Sectors, dan pengiriman melalui portal.

Pengiriman membekukan repositori. Setelah dikirim tidak boleh ada commit apa pun, termasuk perbaikan galat. Karena itu pengiriman dilakukan mendekati tenggat, dengan sisa margin beberapa jam untuk kendala teknis portal.

---

## 11. Pembagian Tugas

Pembagian berdasarkan kepemilikan, disusun agar tidak ada anggota yang menunggu anggota lain.

### Peran A, Data dan Kredit

Pembungkus API, cache, pencatat kredit, pengambilan data, penegakan point-in-time pada sisi pengambilan.

Pemegang tunggal kunci API dan satu-satunya yang berwenang menaikkan pemakaian kredit. Beban terberat pada minggu pertama, kemudian menurun dan beralih membantu evaluasi.

### Peran B, Label dan Indikator

Taksonomi alasan suspensi, definisi label, pembentukan sampel pembanding, perhitungan indikator, fungsi pemeriksa kebocoran.

Peran yang paling menentukan keabsahan hasil sekaligus paling tidak terlihat dari luar. Peran ini juga memegang wewenang menutup cakupan, yaitu hak untuk menolak penambahan fitur setelah Fase 4 dimulai.

### Peran C, Model dan Evaluasi

Model dasar, pemisahan temporal, metrik, perhitungan selisih waktu, kontribusi indikator.

Sebelum data siap, membangun kerangka evaluasi memakai data sintetis agar tidak menganggur pada minggu pertama.

### Peran D, Produk dan Narasi

Antarmuka, kemudian video. Bekerja sejak hari pertama menggunakan berkas JSON tiruan sesuai kontrak yang disepakati, sehingga tidak pernah terhambat ketersediaan data.

Sejak 20 September berhenti menulis kode dan memegang penuh kedua video. Peran ini memegang 30 persen bobot penilaian sendirian dan bukan peran sisa.

### Ritme

Pertemuan harian 15 menit dengan tiga pertanyaan tetap: apa yang selesai, berapa kredit terpakai, apa yang menghambat.

Dua tanggal yang tidak dapat diganggu gugat: 10 September untuk gerbang model, dan 22 September untuk pembekuan fitur.

---

## 12. Risiko dan Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Sampel positif terlalu sedikit | Model tidak dapat dilatih | Gerbang 31 Agustus dan jalur cadangan rule-based yang sudah dirancang |
| Kebocoran data temporal | Seluruh hasil tidak sah | Fungsi pemeriksa ditulis sebelum indikator, dijalankan pada setiap sampel |
| Kredit habis sebelum tahap skor | Produk tidak dapat diselesaikan | Pembungkus wajib, cache sejak awal, cadangan 150 kredit terkunci |
| Alasan suspensi sulit dikelompokkan | Label tercemar | Taksonomi dibuat manual, disimpan sebagai berkas yang dapat diperiksa |
| Free float tidak tersedia historis | Indikator bocor tanpa disadari | Dipakai hanya untuk skor terkini, dicatat di metodologi |
| Cakupan melebar | Tenggat terlewat | Definisi selesai pada bagian 6 bersifat mengikat, Peran B memegang hak menolak |
| Video dikerjakan terburu-buru | Kehilangan 30 persen bobot | Pembekuan fitur 22 September, satu orang penuh selama delapan hari |
| Produk terbaca sebagai saran investasi | Pelanggaran kode etik kompetisi | Pembatasan klaim pada bagian 5, disclaimer di produk dan video |

Risiko terbesar tim ini bukan kesalahan teknis, melainkan perubahan konsep di tengah jalan. Karena itu konsep dikunci pada 31 Agustus dan setelah 10 September hanya boleh dipersempit, tidak boleh diganti.

---

## 13. Kepatuhan Aturan Kompetisi

| Persyaratan | Pemenuhan |
|---|---|
| Onboarding seluruh anggota sebelum kode ditulis | Fase 0 |
| Repositori dibuat dalam periode pembangunan | Fase 0, 27 Agustus |
| Data Sectors sebagai sumber inti | Seluruh indikator berasal dari Sectors, produk kehilangan fungsi tanpanya |
| Menghasilkan wawasan turunan, bukan tampilan data mentah | Setiap angka pada antarmuka adalah hasil perhitungan |
| Tanpa eksekusi transaksi otomatis | Produk tidak terhubung ke rekening efek mana pun |
| Tanpa saran investasi | Pembatasan klaim pada bagian 5 |
| Kunci API dihapus sebelum pengiriman | Fase 6 |
| Repositori tetap publik 90 hari setelah pengumuman | Disepakati tim di muka |
| Proyek eksklusif untuk kompetisi ini | Kode baru seluruhnya, tidak dikirim ke kompetisi lain |

---

## 14. Keterbatasan

Bagian ini ditulis sebelum pembangunan dimulai dan wajib diperbarui, bukan dihapus, setelah produk selesai.

1. **Jumlah sampel positif kemungkinan kecil.** Konsekuensinya, selang kepercayaan pada seluruh metrik lebar. Angka sampel dilaporkan apa adanya, tidak dibulatkan ke atas.
2. **Pengelompokan alasan suspensi bersifat penilaian manusia.** Pemetaannya dipublikasikan agar dapat diperdebatkan, tetapi tetap merupakan keputusan tim.
3. **Skor tidak berlaku untuk emiten dengan data tidak lengkap.** Emiten tanpa laporan kuartalan yang memadai dikeluarkan dari cakupan dan ditandai, bukan diberi skor rendah secara diam-diam.
4. **Produk tidak dapat melihat informasi non-publik.** Sebagian suspensi dipicu peristiwa yang tidak meninggalkan jejak pada data pasar maupun laporan keuangan.
5. **Selisih waktu historis bukan jaminan masa depan.** Perubahan aturan bursa dapat mengubah pola yang dipelajari model.
6. **Cakupan dibatasi secara sengaja karena anggaran kredit.** Batasnya disebutkan terbuka pada halaman metodologi dan video, sebagai keputusan rekayasa, bukan kekurangan yang disembunyikan.

---

## Lampiran A. Draf Pernyataan Masalah

> Untuk investor ritel pemegang saham lapis dua dan tiga, yang sering baru mengetahui ada masalah ketika sahamnya sudah tidak dapat dijual, AMBANG menghitung kriteria risiko yang dipublikasikan BEI secara berkelanjutan dan menunjukkan emiten mana yang sedang mendekati ambang batas sebelum label resmi diterbitkan.

## Lampiran B. Struktur Video Penilaian

| Waktu | Isi |
|---|---|
| 0.00 sampai 0.20 | Satu kasus nyata, emiten disuspensi dan pemegang saham tidak dapat keluar, disertai konsekuensi keluar dari indeks papan dan perpindahan ke call auction |
| 0.20 sampai 0.40 | Untuk siapa produk ini dibuat |
| 0.40 sampai 1.00 | Apa yang dibangun, satu kalimat |
| 1.00 sampai 2.00 | Alur kerja inti, rekaman layar dari halaman peringkat sampai penjelasan skor |
| 2.00 sampai 2.40 | Bukti backtest dan selisih waktu, jumlah sampel disebutkan terbuka |
| 2.40 sampai 3.00 | Apa yang produk ini tidak klaim, dan disclaimer |

Bagian 2.00 sampai 2.40 adalah pembeda utama terhadap tim yang hanya memutar rekaman dasbor.

## Lampiran C. Daftar Periksa Sebelum Pengiriman

- [ ] Seluruh kunci API dihapus dari repositori dan riwayat commit
- [ ] Repositori berstatus publik
- [ ] README memuat cara menjalankan ulang seluruh alur dari nol
- [ ] Halaman metodologi memuat jumlah sampel sebenarnya
- [ ] Disclaimer terlihat pada produk dan video
- [ ] Video teaser satu menit terunggah publik
- [ ] Video penilaian tiga menit dapat diakses
- [ ] Pernyataan masalah satu kalimat terisi
- [ ] Track 03 Market Intelligence dipilih
- [ ] Nama seluruh anggota tercantum
- [ ] Unggahan media sosial menandai akun resmi Sectors
- [ ] Tidak ada commit setelah pengiriman
