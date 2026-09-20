# Panduan & Dokumentasi Lengkap Variabel Preprocessing dan Hasil Pemodelan AMBA

Dokumen ini berisi penjelasan komprehensif mengenai **seluruh variabel** yang digunakan dalam proyek **AMBA (Early Warning System Risiko Suspensi Saham IDX)**, mencakup variabel identitas, variabel mentah hasil ekstraksi, 11 indikator risiko turunan, variabel target label, hingga variabel keluaran hasil pemodelan machine learning.

Ditulis dengan bahasa yang mudah dipahami oleh anggota tim teknis maupun non-teknis, lengkap dengan **arti bisnis/konteks**, **rumus/logika perolehan**, **sumber data asal**, dan **alasan relevansinya terhadap sistem peringatan dini**.

---

## Daftar Isi
1. [Arsitektur Aliran Data 4 Lapis](#1-arsitektur-aliran-data-4-lapis)
2. [Variabel Identitas dan Kontrol Temporal](#2-variabel-identitas-dan-kontrol-temporal)
3. [Variabel Mentah Hasil Ekstraksi API](#3-variabel-mentah-hasil-ekstraksi-api)
4. [Variabel Turunan: 11 Indikator Risiko](#4-variabel-turunan-11-indikator-risiko)
5. [Variabel Target Label & Taksonomi Suspensi BEI](#5-variabel-target-label--taksonomi-suspensi-bei)
6. [Variabel Keluaran Hasil Pemodelan (Output Pengguna)](#6-variabel-keluaran-hasil-pemodelan-output-pengguna)
7. [Variabel Evaluasi Performa Model (Internal Tim)](#7-variabel-evaluasi-performa-model-internal-tim)
8. [Matriks Ringkasan Pemetaan Variabel](#8-matriks-ringkasan-pemetaan-variabel)

---

## 1. Arsitektur Aliran Data 4 Lapis

Dalam sistem AMBA, data mengalir melalui 4 tingkatan secara ketat:

```
[ Lapis 1: Data Mentah API Sectors ] 
 (Laporan Keuangan Kuartalan, Transaksi Harian, Suspensi, Profil Emiten, Free Float)
                   |
                   v
[ Lapis 2: Preprocessing & Pembentukan 11 Indikator Risiko ]
 (Point-in-Time: Lookback 90 hari, laporan keuangan dengan report_date <= as_of_date)
                   |
                   v
[ Lapis 3: Pemodelan Machine Learning (Random Forest & Logistic Regression) ]
 (Prediksi probabilitas suspensi dalam horizon 90 hari ke depan)
                   |
                   v
[ Lapis 4: Variabel Keluaran Pengguna & Evaluasi ]
 (Persentil 0-100%, Kategori Risiko, Arah Tren 30 Hari, Status Isolasi, Atribusi Dominan)
```

> [!IMPORTANT]
> **Aturan Wawasan Turunan (Track 3 Market Intelligence):**
> Variabel keluaran yang disajikan kepada pengguna **tidak boleh sama persis** dengan data mentah API. Setiap skor risiko wajib merupakan hasil olahan indikator turunan dan model machine learning.

---

## 2. Variabel Identitas dan Kontrol Temporal

Variabel ini berfungsi untuk menempelkan data ke emiten tertentu pada titik waktu tertentu serta mencegah **kebocoran data masa depan (*temporal data leakage*)**.

| Nama Variabel | Tipe Data | Arti Sederhana | Cara Perolehan & Sumber | Relevansi dalam EWS |
|---|---|---|---|---|
| `symbol` | Teks | Kode ticker saham di bursa (misal: `BBCA.JK`). | Diambil dari endpoint Sectors API dan dinormalisasi dengan akhiran `.JK`. | Kunci identifikasi unik emiten. |
| `company_name` | Teks | Nama resmi perseroan tercatat. | Diambil dari endpoint `company_overview` (Sectors API `/v2/company/report/{ticker}/`). | Memberikan kejelasan identitas di tampilan UI dashboard. |
| `as_of_date` | Tanggal (`YYYY-MM-DD`) | Titik potong waktu (*cut-off date*) analisis. | Ditentukan oleh pengguna/jadwal cronjob sebagai titik $T_0$. | Membatasi bahwa model hanya boleh melihat data yang terbit pada atau sebelum tanggal ini. |
| `sector` | Teks | Sektor industri emiten (misal: `Financials`, `Consumer Non-Cyclicals`). | Diambil dari section `overview` respons Sectors API. | Memungkinkan perbandingan risiko antar emiten dalam sektor yang sejenis. |
| `sub_sector` | Teks | Sub-sektor spesifik industri (misal: `Banks`, `Food & Beverage`). | Diambil dari section `overview` respons Sectors API. | Membedakan karakteristik siklus bisnis yang lebih spesifik. |
| `board` | Teks | Papan pencatatan di BEI (`Main`, `Development`, `Acceleration`, `Watchlist`). | Diambil dari field `listing_board` pada `company_overview`. | Papan *Acceleration* dan *Watchlist* (Papan Pemantauan Khusus) memiliki profil risiko bawaan lebih tinggi. |
| `already_flagged` | Biner (`0` atau `1`) | Bernilai `1` jika emiten sudah resmi disuspensi atau masuk Papan Pemantauan Khusus pada `as_of_date`. | Ditandai `1` jika `board == 'Watchlist'` atau terdapat riwayat suspensi aktif dalam 180 hari sebelum `as_of_date`. | **Kunci Isolasi EWS**: Emiten yang sudah bermasalah resmi dipisahkan statusnya agar tidak menutupi emiten yang *baru mulai* rusak. |
| `data_complete` | Biner (`0` atau `1`) | Status kelengkapan data input utama. | Bernilai `1` jika keempat fitur inti (`lapor_jarak_hari`, `utang_terhadap_aset`, `hari_tanpa_transaksi_90d`, `volatilitas_90d`) tidak bernilai `null`. | Mencegah pemberian skor pada emiten yang datanya tidak layak dinilai (*data quality gate*). |
| `feature_max_source_date` | Tanggal (`YYYY-MM-DD`) | Tanggal terbaru dari seluruh laporan keuangan atau data harga yang dipakai pada baris ini. | `max(last_report_date, latest_transaction_date)`. | **Audit Anti-Leakage**: Digunakan untuk membuktikan bahwa $T_{source} \le as\_of\_date$, menjamin tidak ada *look-ahead bias*. |

---

## 3. Variabel Mentah Hasil Ekstraksi API

Data mentah yang ditarik dari database Supabase sebelum dilakukan transformasi. Disimpan untuk keperluan audit, *feature engineering*, dan *display drill-down* di halaman detail emiten.

### 3.1 Dari Laporan Keuangan Kuartalan (`quarterly_financials`)
*Sumber: Sectors API `/v2/financials/quarterly/{ticker}/`*

| Nama Kolom | Arti Finansial | Satuan | Cara Perolehan & Filter Temporal |
|---|---|---|---|
| `raw_revenue` | Pendapatan usaha bersih dalam satu kuartal. | Rupiah | Mengambil nilai `revenue` dari laporan kuartal terakhir dengan `report_date <= as_of_date`. |
| `raw_earnings` | Laba/rugi bersih perusahaan setelah pajak. | Rupiah | Mengambil nilai `earnings` dari kuartal terakhir yang sah. |
| `raw_total_equity` | Ekuitas / modal bersih (Total Aset dikurangi Total Liabilitas). | Rupiah | Mengambil nilai `total_equity` dari kuartal terakhir yang sah. |
| `raw_total_liabilities`| Total utang/kewajiban jangka pendek dan panjang. | Rupiah | Mengambil nilai `total_liabilities` dari kuartal terakhir yang sah. |
| `raw_total_assets` | Total seluruh kekayaan/aset yang dikuasai perusahaan. | Rupiah | Mengambil nilai `total_assets` dari kuartal terakhir yang sah. |
| `raw_total_debt` | Utang berbunga saja (pinjaman bank, obligasi). | Rupiah | Mengambil nilai `total_debt` dari kuartal terakhir yang sah. |
| `raw_operating_cash_flow` | Arus kas bersih dari aktivitas operasional utama. | Rupiah | Mengambil nilai `operating_cash_flow` dari kuartal terakhir yang sah. |
| `raw_free_cash_flow` | Kas sisa setelah belanja modal (*capex*). | Rupiah | Mengambil nilai `free_cash_flow` dari kuartal terakhir yang sah. |
| `raw_report_date` | Tanggal laporan keuangan tersebut resmi diumumkan ke publik. | Tanggal | Tanggal publikasi laporan. Wajib $\le as\_of\_date$. |

### 3.2 Dari Data Transaksi Harian (`daily_transaction`)
*Sumber: Sectors API `/v2/daily/{ticker}/`*

| Nama Kolom | Arti Pasar | Satuan | Cara Perolehan |
|---|---|---|---|
| `raw_close` | Harga penutupan saham pada hari bursa terakhir. | Rupiah per lembar | Nilai `close` pada tanggal transaksi terbaru $\le as\_of\_date$. |
| `raw_volume` | Jumlah lembar saham yang diperdagangkan pada hari terakhir. | Lembar saham | Nilai `volume` pada tanggal transaksi terbaru $\le as\_of\_date$. |
| `raw_market_cap` | Nilai total kapitalisasi pasar emiten. | Rupiah | Harga saham dikalikan jumlah saham beredar pada tanggal terbaru. |

### 3.3 Dari Struktur Kepemilikan (`free_float_snapshot`)
*Sumber: Sectors API `/v2/free-float/`*

| Nama Kolom | Arti Kepemilikan | Satuan | Cara Perolehan & Catatan Khusus |
|---|---|---|---|
| `raw_free_float` | Proporsi saham yang beredar bebas dan dimiliki masyarakat non-pengendali. | Rasio decimal (misal: 0.44 = 44%) | Mengambil snapshot free float terbaru yang tercatat $\le as\_of\_date$. Hanya digunakan untuk *live scoring*, tidak untuk sampel training lama guna menghindari *leakage*. |

---

## 4. Variabel Turunan: 11 Indikator Risiko

Variabel turunan (*derived indicators*) adalah jantung analisis AMBA. Masing-masing dirancang untuk menangkap gejala awal kerusakan emiten dari 4 sudut pandang berbeda.

### 4.1 Kelompok Kepatuhan Pelaporan (Compliance)
Emiten yang sedang menghadapi krisis internal atau keraguan audit sering kali menunda rilis laporan keuangan.

#### 1. `lapor_jarak_hari`
- **Arti**: Selisih hari antara tanggal analisis ($as\_of\_date$) dengan tanggal laporan keuangan resmi terakhir yang tersedia.
- **Rumus**:
  $$\text{lapor\_jarak\_hari} = as\_of\_date - \text{last\_report\_date}$$
- **Konteks EWS**: Emiten normal biasanya memiliki jarak lapor berkisar 45–90 hari. Jarak yang melampaui 120–180 hari menandakan adanya masalah audit berat atau penolakan opini oleh kantor akuntan publik (KAP).

#### 2. `lapor_terlambat`
- **Arti**: Indikator biner apakah emiten telah melampaui batas toleransi penyampaian laporan kuartalan.
- **Rumus**:
  $$\text{lapor\_terlambat} = \begin{cases} 1, & \text{jika } \text{lapor\_jarak\_hari} > 45\text{ hari} \\ 0, & \text{lainnya} \end{cases}$$
- **Konteks EWS**: Memberikan sinyal biner tegas untuk filter awal di dashboard.

---

### 4.2 Kelompok Kesehatan Finansial (Financial Health)
Menangkap kebangkrutan struktural dan risiko solvabilitas emiten.

#### 3. `tanpa_pendapatan`
- **Arti**: Bernilai `1` jika pendapatan usaha kuartal terbaru nol atau mendekati nol.
- **Rumus**:
  $$\text{tanpa\_pendapatan} = \begin{cases} 1, & \text{jika } \text{raw\_revenue} \le 0 \\ 0, & \text{jika } \text{raw\_revenue} > 0 \end{cases}$$
- **Konteks EWS**: Sejalan dengan Kriteria Notasi Khusus BEI Huruf 'B'. Menandakan operasional perseroan telah mati suri.

#### 4. `ekuitas_negatif`
- **Arti**: Bernilai `1` jika modal bersih perusahaan di bawah nol (utang melampaui total aset).
- **Rumus**:
  $$\text{ekuitas\_negatif} = \begin{cases} 1, & \text{jika } \text{raw\_total\_equity} < 0 \\ 0, & \text{jika } \text{raw\_total\_equity} \ge 0 \end{cases}$$
- **Konteks EWS**: Kriteria Notasi Khusus BEI Huruf 'E'. Secara akuntansi, perusahaan sudah berada dalam keadaan pailit teknis (*balance sheet insolvency*).

#### 5. `utang_terhadap_aset` (*Leverage*)
- **Arti**: Porsi seluruh aset perusahaan yang dibiayai menggunakan utang/liabilitas.
- **Rumus**:
  $$\text{utang\_terhadap\_aset} = \frac{\text{raw\_total\_liabilities}}{\text{raw\_total\_assets}}$$
- **Konteks EWS**: **Indikator dengan bobot risiko tertinggi pada model machine learning**. Semakin mendekati atau melebihi angka 1.0, semakin rentan perusahaan mengalami gagal bayar (*default*) kewajiban saat suku bunga naik atau kas mengering.

#### 6. `ako_negatif_berturut` (*OCF Burn Streak*)
- **Arti**: Jumlah kuartal berturut-turut (dihitung mundur dari kuartal terbaru) di mana arus kas operasi bernilai negatif.
- **Rumus**:
  Menghitung deret waktu mundur: kuartal ke-$t$, ke-$(t-1)$, ke-$(t-2)$ yang memiliki $\text{operating\_cash\_flow} < 0$ hingga terputus oleh nilai positif.
- **Konteks EWS**: Menunjukkan laju pembakaran uang tunai (*cash burn*). Perusahaan yang operasionalnya terus menguras kas tanpa menghasilkan kas masuk akan segera mengalami krisis likuiditas pembayaran gaji dan bunga utang.

---

### 4.3 Kelompok Likuiditas dan Perilaku Harga (Market Dynamics)
Menangkap reaksi mikrostruktur pasar, aksi buang barang (*dumping*), atau anomali harga saham dalam rentang 90 hari sebelum $as\_of\_date$.

#### 7. `hari_tanpa_transaksi_90d`
- **Arti**: Jumlah hari di mana saham sama sekali tidak memiliki transaksi (volume perdagangan = 0) dalam 90 hari terakhir.
- **Rumus**:
  $$\text{hari\_tanpa\_transaksi\_90d} = \sum_{t \in [T_0 - 90\text{d}, T_0]} \mathbb{I}(\text{volume}_t == 0)$$
- **Konteks EWS**: Gejala pengeringan likuiditas pasar (*liquidity freeze*). Saham yang sulit diperjualbelikan memiliki risiko likuiditas tinggi bagi investor ritel karena sulit untuk *cut loss*.

#### 8. `rasio_volume_30_90`
- **Arti**: Perbandingan antara rata-rata volume perdagangan jangka pendek (30 hari terakhir) dengan volume jangka menengah (90 hari terakhir).
- **Rumus**:
  $$\text{rasio\_volume\_30_90} = \frac{\text{Rata-rata Volume 30 Hari}}{\text{Rata-rata Volume 90 Hari}}$$
- **Konteks EWS**: Jika bernilai jauh di bawah 1.0 (misal: 0.2), hal ini mencerminkan minat beli pasar sedang mengering drastis secara tiba-tiba (*liquidity abandonment*).

#### 9. `hari_di_batas_bawah_90d` (*Saham Gocap*)
- **Arti**: Berapa kali harga penutupan saham menyentuh harga Rp50 (batas harga terendah di pasar reguler BEI) dalam 90 hari terakhir.
- **Rumus**:
  $$\text{hari\_di_batas\_bawah\_90d} = \sum_{t \in [T_0 - 90\text{d}, T_0]} \mathbb{I}(\text{close}_t == 50)$$
- **Konteks EWS**: Menempel di harga Rp50 adalah tanda kelemahan pasar ekstrem. Saham tertahan di batas bawah reguler dan berpotensi masuk ke Papan Pemantauan Khusus dengan mekanisme *periodic call auction*.

#### 10. `turun_dari_puncak_90d` (*Drawdown*)
- **Arti**: Persentase penurunan harga penutupan hari ini relatif terhadap harga penutupan tertinggi yang pernah dicapai dalam 90 hari terakhir.
- **Rumus**:
  $$\text{turun\_dari\_puncak\_90d} = \frac{\max_{t}(\text{close}_t) - \text{close}_{\text{hari ini}}}{\max_{t}(\text{close}_t)}$$
- **Konteks EWS**: Mengukur seberapa dalam saham telah jatuh dari titik puncaknya. Mengindikasikan kepanikan pasar atau pelepasan kepemilikan oleh investor besar.

#### 11. `volatilitas_90d`
- **Arti**: Simpangan baku (*standard deviation*) dari imbal hasil harian (*daily pct_change*) saham selama 90 hari terakhir.
- **Rumus**:
  $$R_t = \frac{\text{close}_t - \text{close}_{t-1}}{\text{close}_{t-1}}, \quad \text{volatilitas\_90d} = \text{std}(R_t)$$
- **Konteks EWS**: Mengukur fluktuasi liar harga. Volatilitas harian yang tidak wajar menjadi pemicu utama bursa menjatuhkan status *Unusual Market Activity* (UMA) atau suspensi *cooling down*.

---

### 4.4 Kelompok Struktur Kepemilikan (Ownership)

#### 12. `free_float_rendah`
- **Arti**: Bernilai `1` jika persentase kepemilikan saham oleh publik di bawah ambang batas minimal ketentuan bursa (7.5%).
- **Rumus**:
  $$\text{free\_float\_rendah} = \begin{cases} 1, & \text{jika } \text{raw\_free\_float} < 0.075 \\ 0, & \text{lainnya} \end{cases}$$
- **Konteks EWS**: Saham dengan free float sangat kecil rentan dimanipulasi harga (*cornering/gorengan*), memiliki likuiditas semu, dan terancam suspensi administratif terkait pemenuhan Peraturan Bursa No. I-A.

---

## 5. Variabel Target Label & Taksonomi Suspensi BEI

Data mentah suspensi berasal dari tabel `stock_suspensions` (591 kejadian di BEI) yang kemudian diklasifikasikan ke dalam 3 taksonomi utama AMBA:

### 5.1 Taksonomi Suspensi BEI (`event_category`)
Setiap baris alasan suspensi dianalisis secara semantik ke dalam 3 kategori:
- **Kategori A (Lonjakan Harga / Cooling Down UMA)**:
  - *Ciri Alasan*: "peningkatan harga kumulatif yang signifikan", "cooling down sebagai bentuk perlindungan bagi investor".
  - *Arti*: Suspensi sementara akibat volatilitas kenaikan harga ekstrem, bukan kebangkrutan emiten.
- **Kategori B (Penurunan Harga Kumulatif)**:
  - *Ciri Alasan*: "penurunan harga kumulatif yang signifikan".
  - *Arti*: Suspensi perlindungan akibat aksi jual masif.
- **Kategori C (Risiko Fundamental / Kepatuhan / Going Concern)** $\to$ **LABEL TARGET POSITIF**:
  - *Ciri Alasan*: "Suspend more than 6 month", "Belum menyampaikan laporan keuangan auditan tahunan", "ketidakpastian atas kelangsungan usaha (going concern)", "Belum memenuhi ketentuan V.1.1 peraturan bursa I-A", "keterlambatan pembayaran biaya pencatatan tahunan", "papan pemantauan khusus > 1 tahun", "PKPU", "pailit".
  - *Arti*: Masalah struktural perseroan yang berpotensi memicu delisting atau kerugian permanen investor.

### 5.2 Kolom Target Label
| Nama Kolom | Tipe Data | Definisi & Cara Perolehan |
|---|---|---|
| `is_event_90d` | Biner (`0` atau `1`) | **Label Target Utama**. Bernilai `1` jika emiten mengalami suspensi **Kategori C** dalam interval waktu 90 hari setelah titik potong: $(as\_of\_date, as\_of\_date + 90\text{ hari}]$. |
| `event_date` | Tanggal (`YYYY-MM-DD`) | Tanggal resmi di mana suspensi tersebut terjadi (jika ada). |
| `event_category` | Teks (`A`, `B`, `C`, atau `null`) | Kategori taksonomi suspensi terdekat yang dialami emiten. |

---

## 6. Variabel Keluaran Hasil Pemodelan (Output Pengguna)

Variabel ini adalah hasil sintesis akhir model machine learning yang disimpan ke dalam berkas `output/scores.json` dan ditampilkan ke antarmuka pengguna/dashboard.

```json
{
  "symbol": "UDNG.JK",
  "company_name": "PT Agro Bahari Nusantara Tbk",
  "as_of_date": "2026-09-16",
  "sector": "Consumer Non-Cyclicals",
  "sub_sector": "Food & Beverage",
  "board": "Acceleration",
  "skor": 0.4836,
  "persentil": 100.0,
  "kategori": "Sangat Tinggi",
  "arah_30h": "stabil",
  "status": "sudah_ditandai",
  "indikator_dominan": "utang_terhadap_aset",
  "kontribusi": { ... }
}
```

### Penjelasan Variabel Keluaran:

#### 1. `skor` (Probabilitas Mentah)
- **Tipe**: Angka desimal (0.0000 - 1.0000).
- **Cara Perolehan**: Dihitung dari fungsi `predict_proba(X)[:, 1]` model Random Forest (atau fungsi sigmoid regresi logistik) berdasarkan 11 indikator risiko.
- **Catatan Penyajian**: Nilai probabilitas mentah **tidak disajikan secara langsung ke pengguna** karena data suspensi merupakan kasus langka (*imbalanced class*), sehingga probabilitas mentah tidak terkalibrasi secara absolut.

#### 2. `persentil` (Peringkat Relatif Pasar)
- **Tipe**: Angka (0.0 - 100.0%).
- **Cara Perolehan**:
  $$\text{persentil} = \text{rank}(\text{skor}) \times 100$$
- **Arti untuk Pengguna**: Menunjukkan posisi risiko relatif satu emiten dibanding seluruh emiten lain di bursa. Misalnya: persentil `94.7%` berarti *"saham ini lebih berisiko dibanding 94.7% emiten lain yang dianalisis"*.

#### 3. `kategori` (Tingkat Risiko)
- **Tipe**: Teks (`Rendah`, `Sedang`, `Tinggi`, `Sangat Tinggi`).
- **Aturan Pembagian**:
  - `Sangat Tinggi` : Persentil $\ge 90.0\%$
  - `Tinggi`        : Persentil $75.0\% - 89.9\%$
  - `Sedang`        : Persentil $50.0\% - 74.9\%$
  - `Rendah`        : Persentil $< 50.0\%$

#### 4. `arah_30h` (Dinamika Tren 30 Hari)
- **Tipe**: Teks (`naik`, `turun`, `stabil`).
- **Cara Perolehan**:
  Membandingkan persentil risiko hari ini ($P_t$) dengan persentil risiko 30 hari yang lalu ($P_{t-30}$):
  $$\text{arah\_30h} = \begin{cases} \text{naik}, & \text{jika } (P_t - P_{t-30}) > +5.0\% \\ \text{turun}, & \text{jika } (P_t - P_{t-30}) < -5.0\% \\ \text{stabil}, & \text{lainnya} \end{cases}$$
- **Arti**: Memberikan peringatan apakah kondisi fundamental/pasar emiten sedang mengalami perburukan (*naik*) atau pemulihan (*turun*).

#### 5. `status` (Klasifikasi Pemisahan Peringkat)
- **Tipe**: Teks (`dinilai`, `sudah_ditandai`, `tidak_dapat_dinilai`).
- **Aturan Bisnis Mengikat**:
  - `dinilai`: Emiten aktif yang dinilai reguler (target utama EWS).
  - `sudah_ditandai`: Emiten yang sudah berstatus suspensi atau sudah berada di Papan Pemantauan Khusus (`already_flagged == 1`). Emiten ini dipisahkan agar peringkat utama EWS fokus memperingatkan emiten yang *baru mulai memburuk*.
  - `tidak_dapat_dinilai`: Emiten dengan data inti yang tidak lengkap (`data_complete == 0`).

#### 6. `indikator_dominan`
- **Tipe**: Teks nama indikator (misal: `utang_terhadap_aset`, `volatilitas_90d`).
- **Cara Perolehan**: Indikator dengan nilai bobot kontribusi positif terbesar terhadap kenaikan skor emiten tersebut.
- **Arti**: Menjawab pertanyaan pengguna *"faktor apa yang paling membahayakan dari saham ini?"*.

#### 7. `kontribusi`
- **Tipe**: Objek / Dictionary `{nama_indikator: nilai_kontribusi}`.
- **Cara Perolehan**: Hasil perkalian fitur terstandardisasi dengan koefisien regresi logistik terstandardisasi ($z_j \times \beta_j$). Mengisi diagram *waterfall / breakdown* risiko pada halaman Detail Emiten.

---

## 7. Variabel Evaluasi Performa Model (Internal Tim)

Variabel ini disimpan di dalam berkas `output/backtest.json` untuk mengukur efektivitas model secara objektif dan memvalidasi keandalan sistem sebelum dideploy.

| Nama Metrik | Nilai Capaian Model | Arti & Interpretasi |
|---|---|---|
| `auc` (ROC-AUC) | **0.8740** (Random Forest) / **0.8154** (LR Balanced) | Kemampuan model membedakan antara emiten yang akan mengalami suspensi vs emiten aman. Skor 0.87 menandakan daya diskriminasi yang sangat baik. |
| `precision` | **0.5124** (Random Forest) | Dari seluruh saham yang diprediksi berisiko oleh model, sekitar 51% terbukti benar-benar mengalami peristiwa intervensi suspensi. |
| `recall` / `recall_90h` | **0.6667** (LR Balanced) / **0.6167** (Random Forest) | Dari seluruh peristiwa suspensi yang benar-benar terjadi di pasar, model berhasil menangkap lebih dari 62%–67% di antaranya dalam jendela 90 hari sebelumnya. |
| `f1_score` | **0.4922** | Keseimbangan harmonik antara Presisi dan Recall pada kelas yang timpang. |
| `alarm_palsu` | 14 kejadian | Jumlah kasus di mana model memprediksi risiko tinggi, namun belum terjadi suspensi dalam jendela 90 hari. (Berguna untuk memonitor toleransi *false positive*). |
| `akurasi_internal_only`| 82.46% | Proporsi tebakan benar secara agregat. **Hanya dihitung untuk keperluan internal**, tidak dipublikasikan ke publik karena metrik akurasi dapat menyesatkan pada kelas yang timpang (*class imbalance*). |

---

## 8. Matriks Ringkasan Pemetaan Variabel

Sebagai rangkuman cepat, tabel di bawah memetakan setiap variabel ke sumber tabel dan modul kodenya:

| Nama Variabel | Kategori | Tabel Asal Supabase | Modul Kode Penghitung |
|---|---|---|---|
| `symbol`, `board`, `sector`, `sub_sector` | Identitas | `company_overview` | `sectors_fetcher/service.py` |
| `as_of_date`, `already_flagged`, `data_complete` | Kontrol | Input & Database | `sectors_fetcher/service.py` |
| `raw_revenue`, `raw_total_equity`, dll. | Mentah Finansial | `quarterly_financials` | `preprocessing/notebook/eda_and_feature_engineering.ipynb` |
| `raw_close`, `raw_volume`, `raw_market_cap` | Mentah Pasar | `daily_transaction` | `preprocessing/notebook/eda_and_feature_engineering.ipynb` |
| `raw_free_float` | Mentah Kepemilikan | `free_float_snapshot` | `sectors_fetcher/features/ownership.py` |
| `lapor_jarak_hari`, `lapor_terlambat` | Kepatuhan | `quarterly_financials` | `sectors_fetcher/features/compliance.py` |
| `tanpa_pendapatan`, `ekuitas_negatif`, `utang_terhadap_aset`, `ako_negatif_berturut` | Finansial | `quarterly_financials` | `sectors_fetcher/features/financial_health.py` |
| `hari_tanpa_transaksi_90d`, `rasio_volume_30_90`, `hari_di_batas_bawah_90d`, `turun_dari_puncak_90d`, `volatilitas_90d` | Likuiditas & Harga | `daily_transaction` | `sectors_fetcher/features/liquidity_price.py` |
| `free_float_rendah` | Kepemilikan | `free_float_snapshot` | `sectors_fetcher/features/ownership.py` |
| `is_event_90d`, `event_category` | Target Label | `stock_suspensions` | `preprocessing/notebook/eda_and_feature_engineering.ipynb` |
| `skor`, `persentil`, `kategori`, `arah_30h`, `status`, `indikator_dominan`, `kontribusi` | Hasil Model | Model ML (`.joblib`) | `sectors_fetcher/service.py` |

