# Panduan API Sectors untuk AMBANG

Dokumen ini menyaring seluruh referensi API Sectors dan hanya membahas yang relevan untuk proyek AMBANG. Ditulis dengan asumsi pembaca belum paham istilah saham dan ekonomi, jadi setiap istilah teknis diterjemahkan dulu sebelum dipakai.

**Cara membaca dokumen ini:** bagian 1 wajib dibaca semua orang di tim, karena isinya konsep dasar yang dipakai berulang. Bagian 2 adalah endpoint yang benar-benar dipakai proyek, diurutkan dari paling penting. Bagian 3 adalah endpoint yang ada di referensi tapi tidak dipakai, supaya kalian tidak salah pakai waktu untuk mempelajarinya.

---

## 1. Istilah Dasar yang Dipakai Berulang

Pahami sepuluh istilah ini dulu. Begitu paham, membaca sisa dokumen jadi jauh lebih mudah.

| Istilah | Artinya |
|---|---|
| Emiten | Perusahaan yang sahamnya diperdagangkan di bursa. Satu emiten sama dengan satu perusahaan tercatat |
| Simbol atau ticker | Kode empat huruf untuk satu emiten, misalnya BBCA untuk Bank Central Asia |
| IDX | Bursa Efek Indonesia, tempat semua transaksi saham Indonesia terjadi |
| Kuartal | Periode tiga bulan. Kuartal 1 adalah Januari sampai Maret, dan seterusnya. Perusahaan wajib melaporkan keuangannya tiap kuartal |
| Laporan keuangan | Dokumen resmi berisi kondisi keuangan perusahaan pada periode tertentu, isinya laba, aset, utang, dan sejenisnya |
| Ekuitas | Kekayaan bersih perusahaan, dihitung dari total aset dikurangi total utang. Ekuitas negatif berarti utangnya lebih besar dari asetnya |
| Volume | Jumlah lembar saham yang diperjualbelikan pada satu hari |
| Market cap (kapitalisasi pasar) | Nilai total perusahaan di pasar, dihitung dari harga saham dikali jumlah saham beredar |
| Kredit API | Jatah pemakaian yang diberikan panitia hackathon, bukan istilah keuangan. Setiap panggilan ke API Sectors menghabiskan sejumlah kredit ini |
| Free float | Persentase saham yang dipegang publik, bukan oleh pendiri atau pemegang saham utama |

Satu hal yang membingungkan banyak pemula: kata "kredit" di dokumen ini punya dua arti berbeda. **Kredit API** adalah jatah panggilan ke Sectors. **Utang atau kredit** dalam konteks keuangan adalah pinjaman perusahaan. Dua-duanya muncul di dokumen ini, jadi perhatikan konteksnya.

---

## 2. Endpoint yang Dipakai Proyek AMBANG

Diurutkan dari yang paling sering dipanggil dan paling penting.

### 2.1 Stock Suspensions — sumber label kalian

**Apa isinya:** daftar seluruh saham yang pernah dihentikan sementara perdagangannya oleh BEI, lengkap dengan tanggal, alasan resmi, dan tautan dokumen resmi.

**Kenapa ini paling penting:** ini satu-satunya sumber yang memberi tahu kalian "kapan sebuah emiten benar-benar bermasalah di masa lalu". Tanpa endpoint ini, kalian tidak punya jawaban benar untuk melatih model.

**Cara memakainya:**
```
GET /v2/suspensions/
```

Parameter yang berguna: `symbol` untuk melihat riwayat satu emiten saja, `start` dan `end` untuk membatasi rentang tanggal.

**Biaya:** 1 kredit per panggilan, hasil dibagi per halaman (maksimal 30 per halaman).

**Cara mengambil semuanya:** panggil berulang dengan `offset` bertambah 30 tiap kali, sampai hasilnya kosong. Untuk riwayat tiga tahun, perkiraan totalnya di bawah 20 kredit.

---

### 2.2 Latest Quarterly Financial Dates (Universe) — indikator paling murah dan mungkin paling kuat

**Apa isinya:** untuk **semua** emiten sekaligus dalam satu panggilan, kapan tanggal laporan kuartalan terbarunya.

**Kenapa penting untuk kalian:** ingat indikator "jarak lapor" yang kita bahas sebagai indikator paling murah dan berpotensi paling kuat. Endpoint inilah sumbernya. Kalian menghitung selisih hari antara tanggal laporan terbaru dan titik potong analisis. Emiten yang telat lapor sering kali sedang bermasalah, jauh sebelum masalahnya terlihat di tempat lain.

**Cara memakainya:**
```
GET /v2/companies/quarterly-financial-dates/
```

Fitur penting: parameter `since` membuat kalian hanya menerima emiten yang **baru saja** melaporkan sejak tanggal tertentu, bukan menarik ulang semuanya. Ini menghemat kredit kalau kalian memantau perkembangan secara berkala.

**Biaya:** 1 kredit per halaman. Seluruh alam semesta sekitar 950 emiten butuh sekitar 32 halaman, jadi sekitar 32 kredit untuk sekali tarik penuh.

---

### 2.3 Company Quarterly Financials — sumber indikator kesehatan keuangan

**Apa isinya:** angka-angka laporan keuangan resmi satu emiten pada satu kuartal tertentu: pendapatan, laba, total aset, total ekuitas, dan sejenisnya.

**Kenapa penting:** dari sinilah kalian menghitung tiga indikator yang kita rancang sebelumnya.

| Indikator kalian | Field API yang dipakai | Cara menghitung |
|---|---|---|
| Tanpa pendapatan usaha | `revenue` | Bernilai nol atau sangat kecil |
| Ekuitas negatif | `total_equity` | Bernilai di bawah nol |
| Arus kas operasi negatif | `operating_cash_flow` | Bernilai di bawah nol, dihitung berapa kuartal berturut-turut |

Penjelasan istilah tambahan yang muncul di respons endpoint ini:

| Field | Artinya sederhana |
|---|---|
| `earnings` | Laba bersih perusahaan pada kuartal itu |
| `total_liabilities` | Total utang perusahaan |
| `total_debt` | Utang berbunga saja, bagian dari total utang |
| `free_cash_flow` | Uang tunai yang benar-benar tersisa setelah semua pengeluaran operasional dan investasi |

**Cara memakainya:**
```
GET /v2/financials/quarterly/{symbol}/
```

Kalian butuh `report_date` yang valid. Dapatkan dulu dari endpoint 2.4 di bawah, jangan menebak tanggalnya.

**Biaya:** 1 kredit per kuartal yang dikembalikan. Kalau kalian minta 4 kuartal untuk satu emiten, itu 4 kredit.

**Peringatan penting untuk aturan point-in-time kalian:** endpoint ini akan memberi laporan **terbaru** kalau kalian tidak menentukan `report_date`. Untuk sampel historis, misalnya emiten yang disuspensi Maret 2025, kalian **wajib** menentukan `report_date` yang berlaku sebelum Maret 2025, bukan membiarkan API memberi laporan terbaru tahun 2026. Kalau ini terlewat, seluruh hasil model kalian tidak sah karena model "melihat masa depan".

---

### 2.4 Quarterly Financial Dates — pasangan wajib untuk endpoint 2.3

**Apa isinya:** untuk **satu** emiten, daftar seluruh tanggal laporan yang pernah ada, dikelompokkan per tahun.

**Kenapa dibutuhkan:** endpoint 2.3 di atas butuh `report_date` yang valid sebagai input, dan endpoint inilah yang memberi tahu tanggal mana saja yang valid untuk emiten tersebut.

```
GET /v2/company/get_quarterly_financial_dates/{symbol}/
```

**Biaya:** 1 kredit per emiten.

---

### 2.5 Daily Transaction Data — sumber indikator likuiditas dan harga

**Apa isinya:** harga penutupan harian, volume, dan market cap untuk satu emiten, sampai rentang 90 hari.

**Kenapa penting:** dari sini kalian menghitung seluruh indikator kelompok likuiditas dan perilaku harga.

| Indikator kalian | Cara menghitung dari data ini |
|---|---|
| Hari tanpa transaksi | Hitung berapa hari `volume` bernilai nol dalam 90 hari |
| Pengeringan volume | Rata-rata `volume` 30 hari terakhir dibagi rata-rata 90 hari |
| Menempel di batas bawah | Hitung berapa hari `close` bernilai Rp50. Ini batas harga terendah yang diizinkan BEI, jadi kalau harga sampai di sini artinya sudah sangat lemah |
| Penurunan dari puncak | Selisih `close` hari ini terhadap harga tertinggi dalam 90 hari |
| Volatilitas | Seberapa liar harga naik turun harian, dihitung sebagai simpangan baku |

**Cara memakainya:**
```
GET /v2/daily/{symbol}/
```

Parameter `start` dan `end` menentukan rentang. Maksimal 90 hari per panggilan, jadi kalau butuh data 12 bulan, kalian perlu memanggil ulang beberapa kali dengan rentang tanggal berbeda.

**Biaya:** 1 kredit per panggilan, terlepas dari berapa hari yang diminta dalam batas 90 hari. Ini sebabnya lebih efisien minta 90 hari sekaligus daripada memanggil per minggu.

---

### 2.6 Daily Full-Universe Close — untuk memberi skor ke seluruh pasar

**Apa isinya:** harga penutupan **seluruh** emiten IDX pada satu hari tertentu, dalam satu tarikan.

**Kenapa penting:** bedanya dengan endpoint 2.5 di atas. Endpoint 2.5 memberi riwayat panjang untuk **satu** emiten. Endpoint ini memberi **satu hari** untuk **semua** emiten. Kalian pakai ini pada tahap akhir, saat menghitung skor untuk seluruh pasar sekaligus di halaman Peringkat, bukan saat melatih model per emiten.

```
GET /v2/close/
```

Parameter `date` menentukan hari yang diminta. Kalau tidak diisi, otomatis mengambil hari bursa terbaru.

**Biaya:** 1 kredit per halaman, sekitar 32 halaman untuk seluruh pasar dalam satu hari, jadi sekitar 32 kredit sekali tarik.

---

### 2.7 Free Float Market Analysis — indikator struktur kepemilikan

**Apa isinya:** persentase saham yang dipegang publik untuk banyak emiten sekaligus, dikelompokkan per sektor.

**Kenapa penting, tapi hati-hati:** free float yang rendah berarti sedikit saham yang beredar bebas di pasar, sehingga harga lebih mudah digerakkan dan lebih sulit dijual dalam jumlah besar. Ini indikator yang relevan untuk risiko likuiditas.

**Peringatan yang sudah kita bahas sebelumnya:** endpoint ini kemungkinan hanya memberi nilai **saat ini**, bukan nilai historis pada tanggal tertentu di masa lalu. Kalau benar begitu, indikator ini **tidak boleh** dipakai untuk melatih model dari sampel historis, karena akan membocorkan informasi masa depan ke data masa lalu. Pakai hanya saat menghitung skor emiten hari ini, bukan saat melatih.

```
GET /v2/free-float/
```

Hanya boleh mengisi satu parameter filter per panggilan: `sector`, `sub_sector`, `industry`, atau `sub_industry`.

**Biaya:** 1 kredit per 100 perusahaan yang dikembalikan, dibulatkan ke atas.

---

### 2.8 Companies Screener — untuk menyusun daftar cakupan awal

**Apa isinya:** endpoint pencarian dan penyaringan emiten paling serbaguna di seluruh API Sectors. Bisa dipakai untuk menyaring emiten berdasarkan hampir semua kriteria: sektor, ukuran perusahaan, rasio keuangan, dan sebagainya.

**Kenapa dipakai proyek kalian:** di tahap awal, dipakai untuk menyusun daftar cakupan emiten yang akan dianalisis. Misalnya menyaring emiten dengan `market_cap` di atas ambang tertentu supaya cakupan kalian tidak mencakup 950 emiten sekaligus, karena itu akan menghabiskan kredit.

**Dua cara memakai endpoint ini, pilih salah satu:**

Cara pertama, pakai `where` untuk kondisi terstruktur mirip SQL:
```
where = market_cap > 100000000000 and listing_board = 'Main'
```

Cara kedua, pakai `q` untuk bahasa natural, misalnya menuliskan langsung "perusahaan sektor keuangan dengan market cap di atas 100 miliar". Cara kedua ini lebih mahal, jadi untuk proyek kalian **gunakan cara pertama.**

**Biaya:** 1 kredit untuk query terstruktur (`where`), tapi 3 kredit kalau memakai bahasa natural (`q`). Selalu pakai `where`, karena kalian tahu persis kriteria cakupan kalian dan tidak perlu bahasa natural.

**Istilah yang muncul di field endpoint ini:**

| Field | Artinya sederhana |
|---|---|
| `listing_board` | Papan pencatatan emiten, ada Main, Development, atau Acceleration. Emiten lapis dua dan tiga yang jadi target pengguna kalian umumnya ada di Development atau Acceleration |
| `market_cap_rank` | Peringkat emiten berdasarkan ukuran, angka 1 berarti perusahaan terbesar |
| `der_mrq` | Rasio utang terhadap ekuitas, kuartal terakhir. Makin tinggi, makin banyak utang dibanding modal sendiri |
| `roa_ttm` dan `roe_ttm` | Ukuran seberapa efisien perusahaan menghasilkan laba dari aset dan modalnya, dua belas bulan terakhir |

---

### 2.9 Subsectors, Industries, Subindustries — daftar rujukan, dipanggil sekali saja

**Apa isinya:** tiga endpoint kecil yang masing-masing memberi daftar kode sektor, industri, dan sub-industri yang valid di sistem Sectors.

**Kenapa dibutuhkan:** kalau kalian mau menyaring berdasarkan sektor di endpoint Companies Screener atau Free Float, kalian butuh kode yang tepat, misalnya `banks` bukan "Perbankan". Endpoint ini memberi daftar kode yang sah.

```
GET /v2/subsectors/
GET /v2/industries/
GET /v2/subindustries/
```

**Biaya:** 1 kredit tiap endpoint, dan hanya perlu dipanggil sekali di awal proyek, lalu disimpan sebagai berkas rujukan lokal. Tidak perlu dipanggil ulang.

---

## 3. Endpoint yang Kalian Miliki Tapi Tidak Dipakai

Bagian ini penting supaya kalian tidak menghabiskan waktu mempelajari sesuatu yang tidak relevan dengan skop proyek kalian.

### Tidak dipakai versi awal, dipertimbangkan hanya kalau kredit sisa banyak setelah 15 September

**Broker Activity Per Symbol dan Broker Registry.** Ini memberi tahu broker mana yang paling aktif membeli atau menjual satu saham. Datanya menarik untuk mendeteksi pola "orang dalam menjual diam-diam", tapi dibatasi 14 hari per panggilan, sehingga menarik data setahun untuk satu emiten bisa menghabiskan puluhan kredit. Ini sudah kita bahas sebagai fitur tahap lanjut, bukan fondasi.

**Company Filings.** Data transaksi jual beli oleh orang dalam perusahaan. Relevan secara konsep, tapi bukan bagian dari rancangan indikator utama AMBANG saat ini.

**Company Revenue Segments.** Rincian dari mana saja pendapatan perusahaan berasal. Ini relevan untuk ide Track 3 yang lain, yaitu konsentrasi pendapatan, tapi tidak dipakai di T3-1.

### Tidak relevan untuk arah proyek kalian

**Corporate Actions, Company IPO & Listing Performance, Top Company Movers, Most Traded Stocks, News Articles, Index Daily Transaction Data, IDX Market Summary, Shareholders Composition, Company Report, Subsector Report.**

Endpoint-endpoint ini masing-masing berguna untuk kasus produk lain, misalnya pelacakan dividen, ringkasan berita, atau laporan menyeluruh satu perusahaan untuk investor. Tidak satupun dari sinyal risiko suspensi yang kalian rancang bergantung pada data ini. Kalau ada anggota tim yang tertarik menambahkannya "biar lengkap", ingatkan bahwa halaman Peringkat kalian sudah punya definisi selesai yang mengikat, dan menambah endpoint baru berarti menambah indikator baru yang tidak direncanakan.

---

## 4. Ringkasan Peta Endpoint ke Indikator

Tabel ini menjawab pertanyaan "kalau saya sedang mengerjakan indikator X, saya harus buka endpoint yang mana".

| Indikator AMBANG | Endpoint sumber | Nomor bagian |
|---|---|---|
| Label suspensi (positif atau negatif) | Stock Suspensions | 2.1 |
| Jarak lapor | Latest Quarterly Financial Dates (Universe) | 2.2 |
| Tanpa pendapatan usaha | Company Quarterly Financials | 2.3 |
| Ekuitas negatif | Company Quarterly Financials | 2.3 |
| Rasio utang terhadap aset | Company Quarterly Financials | 2.3 |
| Arus kas operasi negatif berturut | Company Quarterly Financials | 2.3 |
| Hari tanpa transaksi | Daily Transaction Data | 2.5 |
| Pengeringan volume | Daily Transaction Data | 2.5 |
| Menempel di batas bawah | Daily Transaction Data | 2.5 |
| Penurunan dari puncak | Daily Transaction Data | 2.5 |
| Volatilitas | Daily Transaction Data | 2.5 |
| Free float (hanya untuk skor terkini) | Free Float Market Analysis | 2.7 |
| Skor seluruh pasar (tahap akhir) | Daily Full-Universe Close | 2.6 |
| Penyaringan cakupan awal | Companies Screener | 2.8 |
| Kode sektor yang valid | Subsectors, Industries, Subindustries | 2.9 |

---

## 5. Urutan Pemanggilan yang Disarankan

Ini urutan praktis, bukan sekadar daftar endpoint, supaya kalian tidak bolak-balik dan boros kredit.

**Langkah 1, sekali saja di awal proyek:** panggil Subsectors, Industries, Subindustries, simpan hasilnya sebagai berkas lokal.

**Langkah 2:** panggil Stock Suspensions untuk seluruh riwayat yang dibutuhkan, simpan ke cache. Ini menentukan berapa banyak sampel positif yang kalian punya.

**Langkah 3:** panggil Companies Screener sekali untuk menyusun cakupan emiten yang akan dianalisis, simpan daftar simbolnya.

**Langkah 4, per emiten dalam cakupan:** panggil Quarterly Financial Dates untuk tahu tanggal laporan yang valid, lalu Company Quarterly Financials dengan `report_date` yang tepat sesuai aturan point-in-time.

**Langkah 5, per emiten dalam cakupan:** panggil Daily Transaction Data untuk jendela 90 hari sebelum titik potong masing-masing sampel.

**Langkah 6, sekali di tahap akhir:** panggil Daily Full-Universe Close dan Free Float Market Analysis untuk menghitung skor seluruh pasar yang tampil di produk.

Jangan membalik urutan ini. Memanggil Daily Transaction Data sebelum tahu cakupan emiten yang pasti akan membuat kalian menarik data untuk emiten yang ternyata tidak dipakai, dan itu kredit yang terbuang percuma.

---

## 6. Istilah yang Kemungkinan Muncul Saat Kalian Membaca Respons API

Daftar tambahan untuk istilah yang tidak masuk tabel di atas tapi mungkin membingungkan saat kalian membuka respons JSON.

| Istilah | Artinya sederhana |
|---|---|
| `pe_ttm`, PE ratio | Rasio harga saham terhadap laba perusahaan. Bukan indikator yang dipakai AMBANG, aman diabaikan kalau muncul di respons endpoint lain |
| `dar_mrq` | Rasio utang terhadap aset, kuartal terakhir. Ini yang dipakai untuk indikator kalian, tapi didapat dari Company Quarterly Financials dengan menghitung sendiri `total_liabilities` dibagi `total_assets`, bukan dari field `dar_mrq` di Companies Screener |
| MRQ | Singkatan dari "most recent quarter", kuartal paling baru |
| TTM | Singkatan dari "trailing twelve months", dua belas bulan ke belakang dari hari ini |
| YoY | Singkatan dari "year over year", perbandingan dengan periode yang sama setahun lalu |
| `.JK` | Akhiran yang kadang ditempel di kode simbol untuk menandakan bursa Jakarta, misalnya BBCA.JK. Beberapa endpoint memakainya, beberapa tidak, periksa contoh di tiap endpoint |

---

## 7. Pertanyaan yang Masih Perlu Dijawab Panitia

Dua hal ini disebutkan di rencana kerja tim, ditegaskan kembali di sini supaya tidak terlewat:

1. Apakah satu halaman hasil (`pagination`) dihitung sebagai satu kredit terpisah pada endpoint yang menyebut "per halaman", seperti Stock Suspensions, Latest Quarterly Financial Dates, dan Daily Full-Universe Close.
2. Konfirmasi tertulis bahwa tiap anggota tim boleh memakai kunci API akun masing-masing untuk mengerjakan bagiannya pada proyek yang sama, karena kredit sekarang tersebar 600 per anggota, bukan terkumpul di satu akun perwakilan.

Sudah dikonfirmasi sebelumnya bahwa poin dua diperbolehkan, catatan ini disimpan sebagai rujukan tertulis.
