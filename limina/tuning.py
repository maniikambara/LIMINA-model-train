"""
tuning.py -- grid pencarian hyperparameter untuk Kandidat 1 dan 2
====================================================================

Dilakukan hanya pada data latih, tidak pernah menyentuh potret uji
sampai evaluasi akhir (docs/rancangan/AMBA-struktur-model-dan-algoritma.md
bagian 9). Opsional: notebook 03 bisa memanggil ini alih-alih
models.latih_kandidat_1/2 langsung kalau ingin mencari hyperparameter,
tapi jalur default tetap konfigurasi tetap di models.py.

TimeSeriesSplit dipakai, bukan KFold biasa, supaya validasi internal ini
juga tidak bocor, konsisten dengan aturan pemisahan temporal.

scoring='average_precision' dipakai, bukan 'accuracy', sejalan dengan
larangan pelaporan akurasi (AMBANG-peran-model-dan-evaluasi.md bagian 4.3).
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

from .contracts import KOLOM_FITUR

PARAM_GRID_KANDIDAT_1 = {"C": [0.1, 0.5, 1.0, 2.0, 5.0]}

PARAM_GRID_KANDIDAT_2 = {
    "n_estimators": [50, 75, 100],
    "max_depth": [2, 3],
    "learning_rate": [0.03, 0.05, 0.1],
}


def setel_kandidat_1(
    X_train: pd.DataFrame, y_train: pd.Series, *, n_splits: int = 3
) -> tuple[LogisticRegression, StandardScaler]:
    """
    Mencari nilai C terbaik untuk Kandidat 1 lewat TimeSeriesSplit,
    dievaluasi dengan average_precision. Mengembalikan (model_terbaik, scaler).
    """
    X = X_train[KOLOM_FITUR].fillna(X_train[KOLOM_FITUR].median())
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    tscv = TimeSeriesSplit(n_splits=n_splits)
    grid = GridSearchCV(
        # penalty tidak dicantumkan eksplisit, lihat catatan di models.py
        # KONFIG_KANDIDAT_1 mengenai FutureWarning penalty='l2'
        LogisticRegression(
            class_weight="balanced", solver="lbfgs", max_iter=1000, random_state=42
        ),
        PARAM_GRID_KANDIDAT_1,
        cv=tscv,
        scoring="average_precision",
    )
    grid.fit(X_scaled, y_train)
    return grid.best_estimator_, scaler


def setel_kandidat_2(
    X_train: pd.DataFrame, y_train: pd.Series, *, n_splits: int = 3, batasi_pencarian: bool = True
) -> GradientBoostingClassifier:
    """
    Mencari kombinasi hyperparameter terbaik untuk Kandidat 2. Kandidat ini
    hanya pembanding, bukan model utama, jadi jika batasi_pencarian=True
    (default), pencarian dibatasi ke satu titik tengah grid supaya tidak
    menghabiskan waktu untuk hal yang tidak menentukan produk akhir
    (bagian 9, catatan penutup).
    """
    X = X_train[KOLOM_FITUR].fillna(X_train[KOLOM_FITUR].median())
    # GradientBoostingClassifier tidak punya parameter class_weight langsung,
    # jadi kelas timpang ditangani lewat sample_weight, sama seperti di
    # models.py::latih_kandidat_2 (bagian 4.2).
    weights = compute_sample_weight(class_weight="balanced", y=y_train)

    if batasi_pencarian:
        model = GradientBoostingClassifier(
            n_estimators=75, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=42
        )
        model.fit(X, y_train, sample_weight=weights)
        return model

    tscv = TimeSeriesSplit(n_splits=n_splits)
    grid = GridSearchCV(
        GradientBoostingClassifier(subsample=0.8, random_state=42),
        PARAM_GRID_KANDIDAT_2,
        cv=tscv,
        scoring="average_precision",
    )
    grid.fit(X, y_train, sample_weight=weights)
    return grid.best_estimator_


__all__ = [
    "PARAM_GRID_KANDIDAT_1",
    "PARAM_GRID_KANDIDAT_2",
    "setel_kandidat_1",
    "setel_kandidat_2",
]
