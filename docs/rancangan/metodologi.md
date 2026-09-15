# Metodologi AMBANG

Status: kerangka awal, ditulis sebelum data asli tersedia. Setiap bagian
bertanda `[ISI SETELAH DATA ASLI]` wajib diperbarui, bukan dihapus, begitu
angka sebenarnya ada. Ditulis untuk dibaca orang yang skeptis.

---

## 1. Apa yang Dihitung AMBANG

AMBANG menghitung ulang kriteria risiko suspensi yang sudah dipublikasikan
BEI secara berkelanjutan dari data Sectors, lalu menampilkan emiten mana
yang sedang bergerak mendekati ambang batas tersebut.

**Yang diklaim:** menghitung indikator risiko berbasis kriteria publik
BEI, menampilkan peringkat dengan penjelasan kontribusi tiap indikator,
menunjukkan bukti historis selisih waktu antara naiknya skor dan
terbitnya label resmi.

**Yang tidak diklaim:** prediksi kebangkrutan, kecurangan, atau
delisting; rekomendasi beli/jual/tahan; pengganti pengumuman resmi BEI;
estimasi durasi suspensi.

## 2. Definisi Label

`is_event_90d = 1` jika emiten mengalami peristiwa suspensi **kategori C**
(kepatuhan atau distress) dalam 90 hari setelah `as_of_date`. Kategori A
(sukarela/aksi korporasi) dan B (teknis jangka pendek) tidak dihitung
sebagai label positif. Peta lengkap alasan resmi ke kategori disimpan di
`data/labels/taksonomi_alasan_suspensi.json`, dapat diperiksa siapa saja.

`[ISI SETELAH DATA ASLI]` Jumlah peristiwa per kategori, rentang tanggal
riwayat yang dipakai.

## 3. Daftar Indikator

| Indikator | Rumus singkat | Kelompok |
|---|---|---|
| Jarak lapor | `as_of_date - report_date` terakhir | Kepatuhan pelaporan |
| Status telat lapor | jarak lapor > tenggat wajib | Kepatuhan pelaporan |
| Tanpa pendapatan usaha | revenue ~ 0 | Kesehatan finansial |
| Ekuitas negatif | total_equity < 0 | Kesehatan finansial |
| Rasio utang terhadap aset | total_liabilities / total_assets | Kesehatan finansial |
| Arus kas operasi negatif berturut | jumlah kuartal OCF < 0 berturut | Kesehatan finansial |
| Hari tanpa transaksi | hari volume = 0 dalam 90 hari | Likuiditas dan harga |
| Pengeringan volume | rata-rata volume 30h / 90h | Likuiditas dan harga |
| Menempel di batas bawah | hari close = Rp50 dalam 90 hari | Likuiditas dan harga |
| Penurunan dari puncak | close hari ini vs puncak 90 hari | Likuiditas dan harga |
| Volatilitas | simpangan baku imbal hasil harian 90 hari | Likuiditas dan harga |
| Free float rendah | free float di bawah ambang | Struktur kepemilikan, hanya skor terkini |

Rumus lengkap dan alasan tiap indikator ada di `AMBA-kamus-variabel.md`
dan `AMBANG-panduan-api-sectors.md` bagian 2.

## 4. Aturan Point-in-Time

> Untuk sampel dengan tanggal peristiwa T, tidak boleh ada satu pun
> indikator yang memakai data yang baru tersedia setelah T dikurangi 30 hari.

Ditegakkan secara teknis lewat `src/pit.py` (sisi pengambilan data) dan
`src/eval/leakage.py` (sisi dataset yang sudah jadi), bukan kesepakatan lisan.

## 5. Model

Model utama: regresi logistik dengan pembobotan kelas berimbang,
regularisasi L2, fitur distandardisasi. Pembanding: gradient boosting
dangkal, aturan tunggal (jarak lapor saja), dan skor rule-based tertimbang
berbasis kriteria Notasi Khusus BEI.

`[ISI SETELAH DATA ASLI]` Kandidat mana yang menjadi mesin utama produk,
hasil gerbang keputusan 10 September, dan alasannya.

## 6. Cara Membaca Skor

Skor **tidak** disajikan sebagai probabilitas. Yang ditampilkan adalah
**persentil** terhadap seluruh cakupan (misalnya "lebih berisiko
dibanding 94 persen emiten lain"), dengan kategori Rendah/Sedang/Tinggi/
Sangat Tinggi sebagai lapisan tambahan.

## 7. Cakupan Data

`[ISI SETELAH DATA ASLI]` Jumlah emiten yang diberi skor, jumlah yang
ditandai `tidak_dapat_dinilai`, jumlah yang `sudah_ditandai`.

## 8. Hasil Uji

`[ISI SETELAH DATA ASLI]` Precision@20 lintas enam potret, median selisih
waktu, jumlah kejadian terlewat, jumlah alarm palsu. Akurasi TIDAK
dilaporkan di bagian ini maupun di bagian manapun (lihat bagian 10).

## 9. Keterbatasan yang Diketahui

1. Jumlah sampel positif kemungkinan kecil, sehingga selang kepercayaan
   seluruh metrik lebar.
2. Pengelompokan alasan suspensi bersifat penilaian manusia tim, bukan
   kebenaran objektif tunggal.
3. Skor tidak berlaku untuk emiten dengan data tidak lengkap; emiten
   semacam ini dikeluarkan dari cakupan dan ditandai, bukan diberi skor
   rendah secara diam-diam.
4. Produk tidak dapat melihat informasi non-publik.
5. Selisih waktu historis bukan jaminan masa depan.
6. Cakupan dibatasi secara sengaja karena anggaran kredit API.

## 10. Yang Sengaja Tidak Dilakukan

- Tidak melaporkan akurasi di mana pun yang dilihat publik.
- Tidak menyajikan skor sebagai probabilitas.
- Tidak memakai validasi silang acak.
- Tidak memakai deep learning.
- Tidak memperbaiki data bocor secara diam-diam.
- Tidak melihat potret uji lebih dari satu kali evaluasi akhir.

## Disclaimer

AMBANG bukan nasihat investasi. Produk ini menghitung ulang kriteria
risiko publik lebih cepat daripada label resminya terbit, tidak lebih
dari itu. Keputusan membeli, menjual, atau menahan saham sepenuhnya
tanggung jawab pengguna sendiri.
