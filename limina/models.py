"""
models.py -- Regresi logistik dan gradient boosting
======================================================

Definisi konfigurasi keempat kandidat
(docs/rancangan/AMBA-struktur-model-dan-algoritma.md bagian 2-6, 13):

  Kandidat 1  Regresi Logistik     model utama
  Kandidat 2  Gradient Boosting    pembanding non-linear
  Kandidat 3  Aturan Tunggal       pembanding kesederhanaan (baselines.py)
  Kandidat 4  Rule-Based           pembanding sekaligus jalur cadangan (baselines.py)

Kandidat 3 dan 4 tidak dilatih, hidup di baselines.py. Modul ini hanya
memuat kandidat yang benar-benar dilatih dari data (Kandidat 1 dan 2),
plus fungsi kontribusi indikator untuk Kandidat 1.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

from .contracts import KOLOM_FITUR

RANDOM_SEED = 42

# Konfigurasi Kandidat 1 (AMBA-struktur-model-dan-algoritma.md bagian 3.3).
# `penalty` sengaja TIDAK dicantumkan eksplisit: L2 adalah default
# LogisticRegression di scikit-learn, dan mencantumkannya sebagai 'l2'
# memicu FutureWarning sejak scikit-learn 1.8 (parameter ini dijadwalkan
# dihapus, diganti C dan l1_ratio). Perilaku regularisasi L2 yang
# diminta dokumen tetap tercapai tanpa parameter ini.
KONFIG_KANDIDAT_1 = dict(
    class_weight="balanced",
    C=1.0,
    solver="lbfgs",
    max_iter=1000,
    random_state=RANDOM_SEED,
)

# Konfigurasi Kandidat 2, persis bagian 4.2
KONFIG_KANDIDAT_2 = dict(
    n_estimators=75,
    max_depth=2,
    learning_rate=0.05,
    subsample=0.8,
    random_state=RANDOM_SEED,
)

# Kandidat 5: anomali TANPA label (Isolation Forest). Dipakai saat
# data_complete=1 ada tapi positifnya < 2 (Kandidat 1/2 tidak bisa
# dilatih) -- lihat splits.saring_data_lengkap.
KONFIG_KANDIDAT_5 = dict(
    n_estimators=100,
    max_samples="auto",
    contamination="auto",
    random_state=RANDOM_SEED,
)


def latih_kandidat_1(
    X_train: pd.DataFrame, y_train: pd.Series
) -> tuple[LogisticRegression, StandardScaler]:
    """
    Kandidat 1, model utama. Standardisasi WAJIB dilakukan di sini dan
    scaler dikembalikan bersama model karena data uji harus memakai scaler
    yang sama, dilatih hanya pada data latih (bagian 3.4).

    Nilai kosong pada X_train diisi median data latih sebelum standardisasi
    (bagian 3.4: "diberi nilai median dari data latih, bukan dibuang barisnya").
    """
    X = X_train[KOLOM_FITUR].fillna(X_train[KOLOM_FITUR].median())
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LogisticRegression(**KONFIG_KANDIDAT_1)
    model.fit(X_scaled, y_train)
    return model, scaler


def latih_kandidat_2(X_train: pd.DataFrame, y_train: pd.Series) -> GradientBoostingClassifier:
    """
    Kandidat 2, pembanding non-linear. TIDAK distandardisasi karena model
    berbasis pohon tidak membutuhkan penskalaan fitur. Pembobotan kelas
    lewat sample_weight, karena GradientBoostingClassifier bawaan
    scikit-learn tidak punya parameter class_weight langsung (bagian 4.2).
    """
    X = X_train[KOLOM_FITUR].fillna(X_train[KOLOM_FITUR].median())
    weights = compute_sample_weight(class_weight="balanced", y=y_train)

    model = GradientBoostingClassifier(**KONFIG_KANDIDAT_2)
    model.fit(X, y_train, sample_weight=weights)
    return model


def skor_kandidat_1(
    model: LogisticRegression, scaler: StandardScaler, df: pd.DataFrame, median_latih: pd.Series
) -> pd.Series:
    """Skor mentah (decision_function, sebelum sigmoid) untuk Kandidat 1."""
    X = df[KOLOM_FITUR].fillna(median_latih)
    X_scaled = scaler.transform(X)
    return pd.Series(model.decision_function(X_scaled), index=df.index)


def skor_kandidat_2(model: GradientBoostingClassifier, df: pd.DataFrame, median_latih: pd.Series) -> pd.Series:
    """Skor mentah (probabilitas kelas positif) untuk Kandidat 2, TANPA scaling."""
    X = df[KOLOM_FITUR].fillna(median_latih)
    return pd.Series(model.predict_proba(X)[:, 1], index=df.index)


def kontribusi_indikator(
    model: LogisticRegression, scaler: StandardScaler, row: pd.Series
) -> dict:
    """
    Untuk satu emiten, kontribusi tiap indikator ke skornya adalah
    koefisien indikator itu dikali nilai terstandardisasi emiten tersebut
    pada indikator itu (bagian 3.5). Arah tanda bermakna: positif menaikkan
    risiko, negatif menurunkan.

    Mengembalikan dict {nama_indikator: kontribusi}, plus kunci
    '_indikator_dominan' berisi nama indikator dengan nilai absolut
    kontribusi terbesar.
    """
    X_row = row[KOLOM_FITUR].to_frame().T
    X_scaled = scaler.transform(X_row)[0]
    kontribusi = model.coef_[0] * X_scaled

    hasil = {nama: float(nilai) for nama, nilai in zip(KOLOM_FITUR, kontribusi)}
    hasil["_indikator_dominan"] = max(hasil, key=lambda k: abs(hasil[k]))
    hasil["_intercept"] = float(model.intercept_[0])
    return hasil


def kontribusi_indikator_kandidat_2(model: GradientBoostingClassifier) -> dict:
    """
    feature_importances_ untuk Kandidat 2. Dipakai sebagai pendukung, BUKAN
    sumber utama penjelasan ke pengguna, karena tidak memberi tahu arah
    pengaruhnya (bagian 4.3). Jika Kandidat 2 terpilih jadi model utama,
    penjelasan ke pengguna wajib disusun ulang.
    """
    return dict(zip(KOLOM_FITUR, (float(v) for v in model.feature_importances_)))


def latih_kandidat_5(X_train: pd.DataFrame) -> IsolationForest:
    """
    Kandidat 5, anomali tanpa label. TIDAK butuh is_event_90d sama
    sekali -- mengukur seberapa jauh kondisi emiten dari mayoritas
    peer-nya, bukan belajar pola suspensi sungguhan (data suspensi tetap
    tidak dipakai). Selalu sebut ke pengguna sebagai skor keanehan
    relatif terhadap peer, bukan prediksi risiko suspensi.
    """
    X = X_train[KOLOM_FITUR].fillna(X_train[KOLOM_FITUR].median())
    model = IsolationForest(**KONFIG_KANDIDAT_5)
    model.fit(X)
    return model


def skor_kandidat_5(model: IsolationForest, df: pd.DataFrame, median_latih: pd.Series) -> pd.Series:
    """Skor mentah Kandidat 5: makin besar makin anomali (kebalikan decision_function)."""
    X = df[KOLOM_FITUR].fillna(median_latih)
    return pd.Series(-model.decision_function(X), index=df.index)


def kontribusi_kandidat_5(df_acuan: pd.DataFrame, row: pd.Series) -> dict:
    """
    Kandidat 5 tak punya koefisien seperti Kandidat 1. Penjelasannya:
    z-score tiap indikator row terhadap median/std df_acuan (data latih
    lengkap yang dipakai melatih Kandidat 5).
    """
    median = df_acuan[KOLOM_FITUR].median()
    std = df_acuan[KOLOM_FITUR].std().replace(0, 1).fillna(1)
    z = (row[KOLOM_FITUR].astype(float) - median) / std
    hasil = {nama: float(v) for nama, v in z.items()}
    hasil["_indikator_dominan"] = max(hasil, key=lambda k: abs(hasil[k]))
    return hasil


__all__ = [
    "KONFIG_KANDIDAT_1",
    "KONFIG_KANDIDAT_2",
    "KONFIG_KANDIDAT_5",
    "latih_kandidat_1",
    "latih_kandidat_2",
    "latih_kandidat_5",
    "skor_kandidat_1",
    "skor_kandidat_2",
    "skor_kandidat_5",
    "kontribusi_indikator",
    "kontribusi_indikator_kandidat_2",
    "kontribusi_kandidat_5",
]
