# AMBA: Struktur Model dan Algoritma Pelatihan

Dokumen ini menjelaskan bentuk model AMBA secara teknis: algoritma yang dipakai, urutan pelatihan, dan alasan tiap keputusan. Ditulis untuk dieksekusi langsung jadi kode, bukan sekadar konsep.

**Terkait:** AMBA-kamus-variabel.md untuk daftar lengkap variabel yang dipakai di sini, AMBA-peran-model-dan-evaluasi.md untuk kerangka evaluasi dan gerbang keputusan.

---

## 1. Bentuk Masalah

Sebelum bicara algoritma, tegaskan dulu jenis masalahnya, karena ini menentukan seluruh pilihan di bawah.

**Jenis masalah:** klasifikasi biner dengan kelas timpang (imbalanced binary classification).

**Yang diprediksi:** `is_event_90d`, yaitu apakah sebuah emiten pada `as_of_date` tertentu akan mengalami peristiwa suspensi kategori C dalam 90 hari ke depan.

**Bukan yang diprediksi:** kapan tepatnya suspensi terjadi, berapa lama durasinya, atau apa penyebab pastinya. Model hanya menjawab satu pertanyaan: seberapa mirip kondisi emiten ini dengan kondisi emiten lain sesaat sebelum mereka disuspensi.

**Karakteristik data yang membentuk seluruh keputusan algoritma di bawah:**

| Karakteristik | Kondisi AMBA | Konsekuensi terhadap pilihan algoritma |
|---|---|---|
| Jumlah sampel | Kemungkinan di bawah 100 sampel positif | Model dengan banyak parameter akan menghafal, bukan belajar |
| Rasio kelas | Sekitar 1 banding 3 di data latih, jauh lebih timpang di dunia nyata | Algoritma harus mendukung pembobotan kelas secara native |
| Kebutuhan penjelasan | Wajib menjelaskan kontribusi tiap indikator ke pengguna awam | Algoritma kotak hitam butuh alat tambahan yang menambah kerumitan tanpa manfaat sepadan |
| Jumlah fitur | Sekitar 9 sampai 11 indikator turunan | Ruang fitur kecil, tidak butuh algoritma yang dirancang untuk data berdimensi tinggi |

---

## 2. Struktur Model Secara Keseluruhan

Bukan satu model tunggal, melainkan empat kandidat yang dievaluasi sejajar. Pemenangnya ditentukan hasil, bukan ditentukan di awal.

```
                    Data panel (lihat AMBA-kamus-variabel.md bagian 3)
                              |
              +---------------+---------------+---------------+
              |               |               |               |
        Kandidat 1       Kandidat 2      Kandidat 3      Kandidat 4
        Regresi          Gradient        Aturan          Skor
        Logistik         Boosting        Tunggal         Rule-Based
        (utama)          (pembanding)    (pembanding)    (pembanding
                                                           sekaligus
                                                           cadangan)
              |               |               |               |
              +---------------+---------------+---------------+
                              |
                    Evaluasi pada enam potret uji
                    (Precision@20, Recall, AUC, Selisih waktu)
                              |
                    Gerbang keputusan 10 September
                              |
              +---------------+---------------+
              |                               |
        Kandidat terbaik jadi mesin utama    Kandidat lain tetap
        di produk                             ditampilkan di halaman
                                               metodologi sebagai
                                               pembanding
```

---

## 3. Kandidat 1: Regresi Logistik — Model Utama

### 3.1 Kenapa ini kandidat utama, bukan sekadar salah satu opsi

Tiga alasan, sesuai kendala di bagian 1:

1. **Jumlah parameter kecil dan tetap**, sama dengan jumlah indikator ditambah satu. Tidak tumbuh mengikuti kerumitan data, jadi risiko menghafal jauh lebih kecil dibanding model yang lebih fleksibel.
2. **Kontribusi tiap indikator didapat langsung dari struktur model**, tanpa alat interpretasi tambahan. Ini yang mengisi field `kontribusi` pada halaman Detail Emiten.
3. **Mendukung pembobotan kelas secara native**, cocok untuk rasio kelas yang timpang.

### 3.2 Rumus

Regresi logistik memodelkan probabilitas sebagai fungsi linear dari indikator, dilewatkan fungsi sigmoid supaya hasilnya berada di rentang 0 sampai 1:

```
z = b0 + b1*x1 + b2*x2 + ... + bn*xn

p = 1 / (1 + e^(-z))
```

Keterangan:
- `x1` sampai `xn` adalah indikator turunan setelah distandardisasi (lihat bagian 3.4)
- `b1` sampai `bn` adalah koefisien yang dipelajari dari data, satu untuk tiap indikator
- `b0` adalah konstanta (intercept)
- `p` adalah probabilitas mentah, yang nantinya diubah jadi `skor` dan `persentil`, bukan ditampilkan langsung sebagai persentase ke pengguna

### 3.3 Konfigurasi

```python
from sklearn.linear_model import LogisticRegression

model = LogisticRegression(
    class_weight='balanced',
    penalty='l2',
    C=1.0,
    solver='lbfgs',
    max_iter=1000,
    random_state=42
)
```

Penjelasan tiap parameter:

| Parameter | Nilai | Alasan |
|---|---|---|
| `class_weight` | `'balanced'` | Otomatis memberi bobot lebih besar ke kelas positif yang langka, tanpa perlu oversampling manual |
| `penalty` | `'l2'` | Mencegah koefisien membesar tak terkendali, menahan model tidak terlalu percaya diri pada sampel sedikit |
| `C` | `1.0` | Titik awal kekuatan regularisasi, disetel lebih lanjut lewat validasi (bagian 5) |
| `solver` | `'lbfgs'` | Solver standar untuk masalah berskala kecil seperti ini |
| `random_state` | `42` | Angka tetap supaya hasil bisa direproduksi ulang oleh siapa saja yang menjalankan kode |

### 3.4 Praproses wajib sebelum melatih

**Standardisasi fitur.** Wajib, tidak opsional, karena koefisien `b1` sampai `bn` hanya bisa dibandingkan secara adil satu sama lain kalau seluruh indikator berada di skala yang sama.

```python
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)
```

Scaler dilatih **hanya** pada data latih, lalu dipakai untuk mengubah data uji. Melatih scaler pada gabungan data latih dan uji akan membocorkan informasi statistik dari data uji ke proses pelatihan.

**Penanganan nilai kosong.** Indikator dengan nilai kosong (`data_complete = 0` untuk sebagian sumbernya) diberi nilai tengah (median) dari data latih, bukan dibuang barisnya, supaya emiten dengan data sebagian tetap bisa diberi skor sebagian.

### 3.5 Kontribusi indikator

```python
kontribusi = model.coef_[0] * X_scaled_single_row
```

Untuk satu emiten tertentu, kontribusi tiap indikator ke skornya adalah koefisien indikator itu dikali nilai terstandardisasi emiten tersebut pada indikator itu. Indikator dengan nilai kontribusi absolut terbesar menjadi `indikator_dominan` di halaman Detail Emiten.

Arah tandanya juga bermakna: kontribusi positif mendorong skor naik (lebih berisiko), kontribusi negatif mendorong skor turun (lebih aman).

---

## 4. Kandidat 2: Gradient Boosting Dangkal — Pembanding Non-Linear

### 4.1 Fungsi kandidat ini

Bukan untuk menggantikan Kandidat 1 secara default, tapi untuk menguji satu pertanyaan: **apakah ada pola non-linear atau interaksi antar indikator yang terlewat oleh model linear.**

Contoh pola yang bisa ditangkap gradient boosting tapi tidak oleh regresi logistik sederhana: "ekuitas negatif **dan** arus kas operasi negatif berturut-turut sekaligus jauh lebih berbahaya daripada dua kondisi itu terjadi sendiri-sendiri." Regresi logistik hanya menjumlahkan kontribusi tiap indikator secara terpisah, sementara gradient boosting bisa menangkap efek gabungan semacam ini secara otomatis.

### 4.2 Konfigurasi

```python
from sklearn.ensemble import GradientBoostingClassifier

model_gb = GradientBoostingClassifier(
    n_estimators=75,
    max_depth=2,
    learning_rate=0.05,
    subsample=0.8,
    random_state=42
)
```

Penjelasan parameter yang paling menentukan untuk kasus sampel sedikit:

| Parameter | Nilai | Alasan |
|---|---|---|
| `max_depth` | `2` | Dibatasi dangkal secara sengaja. Pohon yang dalam pada sampel sedikit akan menghafal data latih, bukan menangkap pola umum |
| `n_estimators` | `75` | Jumlah pohon dibatasi rendah untuk alasan yang sama, ditambah mempercepat pelatihan ulang saat menyetel |
| `learning_rate` | `0.05` | Nilai kecil supaya tiap pohon menyumbang sedikit, mencegah model terlalu cepat menyesuaikan diri dengan sampel latih yang sedikit |
| `subsample` | `0.8` | Tiap pohon hanya melihat 80 persen sampel, menambah keberagaman dan mengurangi risiko menghafal |

Catatan: `GradientBoostingClassifier` bawaan scikit-learn tidak punya parameter `class_weight` langsung. Penanganan kelas timpang dilakukan lewat `sample_weight` saat memanggil `fit()`:

```python
from sklearn.utils.class_weight import compute_sample_weight

weights = compute_sample_weight(class_weight='balanced', y=y_train)
model_gb.fit(X_train, y_train, sample_weight=weights)
```

### 4.3 Kontribusi indikator untuk kandidat ini

```python
importances = model_gb.feature_importances_
```

Dipakai sebagai pendukung, bukan sumber utama penjelasan ke pengguna, karena `feature_importances_` hanya menunjukkan seberapa sering dan seberapa besar indikator itu dipakai memisahkan data, tanpa memberi tahu arah pengaruhnya (menaikkan atau menurunkan risiko). Kalau kandidat ini yang terpilih jadi model utama di gerbang keputusan, penjelasan ke pengguna wajib disusun ulang dengan hati-hati, atau dipertimbangkan kembali apakah kejelasan penjelasannya sepadan dengan kenaikan performa yang didapat.

---

## 5. Kandidat 3: Aturan Tunggal — Pembanding Kesederhanaan

Bukan model dalam arti dilatih, melainkan pengurutan langsung berdasarkan satu indikator saja.

```python
def skor_aturan_tunggal(df):
    return df['lapor_jarak_hari'].rank(ascending=False, pct=True) * 100
```

**Fungsi kandidat ini bukan formalitas.** Kalau kandidat ini saja sudah hampir sekuat Kandidat 1 dan 2, itu temuan penting yang layak dilaporkan apa adanya: bahwa keterlambatan pelaporan sendirian sudah membawa sebagian besar sinyal, dan gabungan indikator lain hanya menambah sedikit.

---

## 6. Kandidat 4: Skor Rule-Based Tertimbang — Pembanding Sekaligus Cadangan

### 6.1 Rumus

Bobot ditetapkan tim berdasarkan penilaian domain, mengikuti bobot kriteria Notasi Khusus BEI sebagai rujukan, bukan hasil pembelajaran dari data.

```python
def skor_rule_based(row):
    skor = 0
    skor += 3 * row['lapor_terlambat']
    skor += 3 * row['tanpa_pendapatan']
    skor += 2 * row['ekuitas_negatif']
    skor += 2 * (row['ako_negatif_berturut'] >= 2)
    skor += 1 * (row['hari_tanpa_transaksi_90d'] > 20)
    skor += 1 * (row['utang_terhadap_aset'] > 0.8)
    return skor
```

Skor maksimal pada rumus ini adalah 12. Diubah jadi persentil dengan cara yang sama seperti kandidat lain, dengan mengurutkan seluruh emiten pada satu potret dan menghitung posisi relatifnya.

### 6.2 Kenapa bobotnya seperti ini

| Indikator | Bobot | Alasan bobot |
|---|---|---|
| `lapor_terlambat` | 3 | Sinyal paling murah didapat dan sejalan langsung dengan kewajiban pelaporan resmi |
| `tanpa_pendapatan` | 3 | Sejalan langsung dengan kriteria notasi S BEI |
| `ekuitas_negatif` | 2 | Indikator distress baku, tapi bisa terjadi karena alasan sementara yang tidak selalu berujung suspensi |
| `ako_negatif_berturut` | 2 | Perlu berturut-turut minimal dua kuartal supaya tidak menangkap penurunan sesaat |
| `hari_tanpa_transaksi_90d` | 1 | Sinyal likuiditas, tapi bisa juga terjadi pada emiten kecil yang sehat namun kurang diminati |
| `utang_terhadap_aset` | 1 | Relevan tapi ambang batas sehat bervariasi antar sektor, jadi diberi bobot lebih ringan |

Bobot ini didokumentasikan secara terbuka di halaman metodologi produk, termasuk pernyataan bahwa ini keputusan tim, bukan hasil optimisasi statistik.

### 6.3 Kapan kandidat ini menjadi mesin utama produk

Sesuai gerbang keputusan pada AMBA-peran-model-dan-evaluasi.md bagian 7: jika Kandidat 1 dan 2 tidak mengalahkan kandidat ini pada Precision@20 di mayoritas dari enam potret uji, kandidat ini yang dipakai sebagai mesin utama produk, dengan Kandidat 1 dan 2 tetap ditampilkan sebagai pembanding di halaman metodologi.

---

## 7. Pemisahan Data

Bukan bagian dari algoritma itu sendiri, tapi menentukan validitas seluruh proses pelatihan di atas.

```python
cutoff_train = '2025-01-01'

train_mask = df['event_date'] < cutoff_train
train_data = df[train_mask]

# Enam potret uji, masing-masing dievaluasi terpisah
snapshot_dates = [
    '2025-01-15', '2025-04-15', '2025-07-15',
    '2025-10-15', '2026-01-15', '2026-04-15'
]
```

**Wajib temporal, tidak pernah acak.** Validasi silang acak (`KFold` dengan `shuffle=True`) akan mencampur peristiwa dari masa depan ke dalam data latih, menghasilkan performa yang terlihat bagus di percobaan tapi tidak berlaku di dunia nyata.

Detail lengkap definisi potret uji dan cara menghitung Precision@20 di enam potret ada di AMBA-peran-model-dan-evaluasi.md bagian 4.

---

## 8. Alur Pelatihan Lengkap

Urutan yang dijalankan dari awal sampai model siap dievaluasi.

```python
# 1. Muat data panel, sudah lolos pemeriksaan kebocoran
df = load_panel('data/panel.parquet')

# 2. Pisahkan data latih dan enam potret uji
train_data = df[df['event_date'] < '2025-01-01']
X_train = train_data[FITUR_KOLOM]
y_train = train_data['is_event_90d']

# 3. Tangani nilai kosong
X_train = X_train.fillna(X_train.median())

# 4. Standardisasi, dilatih hanya pada data latih
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)

# 5. Latih Kandidat 1
model_lr = LogisticRegression(class_weight='balanced', penalty='l2',
                                C=1.0, solver='lbfgs', max_iter=1000,
                                random_state=42)
model_lr.fit(X_train_scaled, y_train)

# 6. Latih Kandidat 2
weights = compute_sample_weight(class_weight='balanced', y=y_train)
model_gb = GradientBoostingClassifier(n_estimators=75, max_depth=2,
                                        learning_rate=0.05, subsample=0.8,
                                        random_state=42)
model_gb.fit(X_train, y_train, sample_weight=weights)  # tanpa scaling

# 7. Kandidat 3 dan 4 tidak perlu dilatih, langsung dihitung dari rumus

# 8. Evaluasi keempat kandidat pada enam potret uji
for snapshot_date in snapshot_dates:
    snapshot = load_snapshot(snapshot_date)
    hasil = evaluasi_semua_kandidat(snapshot, model_lr, model_gb, scaler)
    simpan_hasil(hasil)

# 9. Bandingkan hasil, eksekusi gerbang keputusan
keputusan = gerbang_10_september(hasil_semua_potret)
```

Catatan penting pada langkah 6: **Kandidat 2 dilatih pada `X_train` yang tidak distandardisasi**, karena model berbasis pohon seperti gradient boosting tidak membutuhkan penskalaan fitur. Hanya Kandidat 1 yang butuh `X_train_scaled`.

---

## 9. Penyetelan Hyperparameter

Dilakukan hanya pada data latih, tidak pernah menyentuh enam potret uji sampai evaluasi akhir.

```python
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV

tscv = TimeSeriesSplit(n_splits=3)

param_grid_lr = {'C': [0.1, 0.5, 1.0, 2.0, 5.0]}

grid_lr = GridSearchCV(
    LogisticRegression(class_weight='balanced', penalty='l2',
                        solver='lbfgs', max_iter=1000, random_state=42),
    param_grid_lr,
    cv=tscv,
    scoring='average_precision'
)
grid_lr.fit(X_train_scaled, y_train)
```

**Kenapa `TimeSeriesSplit`, bukan `KFold` biasa.** `TimeSeriesSplit` membagi data latih menjadi beberapa lipatan yang urutannya tetap mengikuti waktu, jadi validasi internal ini juga tidak bocor, konsisten dengan aturan pemisahan temporal pada bagian 7.

**Kenapa `scoring='average_precision'`, bukan `'accuracy'`.** Sejalan dengan larangan pelaporan akurasi pada AMBA-peran-model-dan-evaluasi.md bagian 4.3. Menyetel model supaya akurasinya tinggi akan mendorong model menebak seluruh emiten aman, karena itu strategi termudah mencapai akurasi tinggi pada kelas yang timpang.

Rentang pencarian untuk Kandidat 2, kalau waktunya cukup setelah Kandidat 1 selesai disetel:

```python
param_grid_gb = {
    'n_estimators': [50, 75, 100],
    'max_depth': [2, 3],
    'learning_rate': [0.03, 0.05, 0.1]
}
```

Batasi pencarian ini kalau waktu terbatas. Kandidat 2 hanya pembanding, bukan model utama, jadi penyetelan yang terlalu lama di sini mengorbankan waktu untuk hal yang tidak menentukan produk akhir.

---

## 10. Pemeriksaan Sebelum Model Dipercaya

Empat pemeriksaan dari AMBA-peran-model-dan-evaluasi.md bagian 6 dijalankan sebelum hasil model dipakai untuk kesimpulan apapun.

```python
# Pemeriksaan pengacakan label
y_train_shuffled = y_train.sample(frac=1, random_state=1).reset_index(drop=True)
model_check = LogisticRegression(class_weight='balanced', random_state=42)
model_check.fit(X_train_scaled, y_train_shuffled)
auc_shuffled = roc_auc_score(y_train_shuffled, model_check.predict_proba(X_train_scaled)[:, 1])
assert 0.40 <= auc_shuffled <= 0.60, "AUC pada label acak seharusnya sekitar 0.50"

# Pemeriksaan fitur kendali
X_train_dengan_acak = X_train.copy()
X_train_dengan_acak['fitur_acak'] = np.random.randn(len(X_train))
model_kendali = LogisticRegression(class_weight='balanced', random_state=42)
model_kendali.fit(scaler.fit_transform(X_train_dengan_acak), y_train)
koefisien_acak = abs(model_kendali.coef_[0][-1])
assert koefisien_acak < np.percentile(abs(model_kendali.coef_[0][:-1]), 50), \
    "Fitur acak seharusnya tidak berpengaruh besar"
```

**Refleks yang wajib ditanam:** jika AUC pada data uji sungguhan berada di atas 0,90 pada percobaan pertama, itu diperlakukan sebagai gejala kebocoran, bukan keberhasilan. Hentikan, telusuri ulang aturan point-in-time pada data panel, jangan lanjut ke gerbang keputusan sebelum penyebabnya ditemukan.

---

## 11. Ringkasan Perbandingan Struktur

| Aspek | Kandidat 1 Regresi Logistik | Kandidat 2 Gradient Boosting | Kandidat 3 Aturan Tunggal | Kandidat 4 Rule-Based |
|---|---|---|---|---|
| Perlu dilatih dari data | Ya | Ya | Tidak | Tidak |
| Perlu standardisasi fitur | Ya | Tidak | Tidak | Tidak |
| Menangkap interaksi antar indikator | Tidak | Ya | Tidak | Tidak, kecuali ditulis manual |
| Sumber kontribusi indikator | Koefisien x nilai | `feature_importances_` | Tidak relevan, satu indikator saja | Bobot tetap yang ditulis manual |
| Risiko menghafal pada sampel sedikit | Rendah | Sedang, ditahan lewat `max_depth` dan `subsample` | Tidak ada risiko, tidak dilatih | Tidak ada risiko, tidak dilatih |
| Kemudahan dijelaskan ke pengguna awam | Tinggi | Sedang | Tinggi | Tinggi |

---

## 12. Yang Tidak Dipakai dan Alasannya

| Algoritma | Alasan tidak dipakai |
|---|---|
| Random Forest | Tidak menambah kemampuan dibanding gradient boosting dangkal untuk kasus ini, sementara interpretasinya sedikit lebih rumit karena dirata-rata dari banyak pohon |
| SVM | Butuh penyetelan kernel yang menghabiskan waktu, dan tidak menghasilkan kontribusi indikator yang gampang dijelaskan |
| Naive Bayes | Mengasumsikan indikator saling bebas, sementara indikator AMBA jelas berkorelasi, misalnya ekuitas negatif dan arus kas negatif sering muncul bersamaan |
| Neural network dalam bentuk apapun | Butuh ratusan sampel minimal untuk tidak menghafal, sementara sampel positif AMBA kemungkinan besar di bawah 100 |
| XGBoost, LightGBM | Secara teknis mirip gradient boosting scikit-learn, menambah satu dependensi eksternal tanpa manfaat nyata pada dataset sekecil ini |
| Validasi silang acak (`KFold` dengan `shuffle=True`) | Membocorkan data dari masa depan ke data latih, melanggar aturan point-in-time |

---

## 13. Struktur Berkas Kode

```
src/eval/models.py
    - definisi konfigurasi keempat kandidat
    - fungsi latih_kandidat_1(X_train, y_train) -> model, scaler
    - fungsi latih_kandidat_2(X_train, y_train) -> model
    - fungsi skor_kandidat_3(df) -> Series
    - fungsi skor_kandidat_4(df) -> Series
    - fungsi kontribusi_indikator(model, scaler, row) -> dict

src/eval/tuning.py
    - grid pencarian hyperparameter untuk Kandidat 1 dan 2
    - fungsi setel_kandidat_1(X_train, y_train) -> model_terbaik

src/eval/leakage.py
    - pemeriksaan pengacakan label
    - pemeriksaan fitur kendali
    - pemeriksaan batas kewajaran AUC

tests/test_models.py
    - uji bahwa Kandidat 1 memakai data terstandardisasi
    - uji bahwa Kandidat 2 tidak memakai data terstandardisasi
    - uji bahwa kontribusi indikator menjumlah ke skor akhir dikurangi intercept
```
