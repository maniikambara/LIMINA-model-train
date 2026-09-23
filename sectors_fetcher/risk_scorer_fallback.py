"""
risk_scorer_fallback.py
========================

Skor risiko UNSUPERVISED (SkorAnomaliMahalanobis) dipakai sebagai fallback
sementara oleh modeling_and_evaluation.ipynb ketika kelas positif
`is_event_90d` pada cakupan data saat ini punya < 2 sampel, sehingga
CV/tuning supervised (Baseline LR, LR Balanced, Random Forest GridSearchCV)
tidak bisa dijalankan secara valid pada model apa pun -- bukan cuma
Random Forest.

Class ini SENGAJA ditaruh di modul terpisah (bukan didefinisikan langsung
di sel notebook) supaya model_random_forest.joblib yang memuatnya bisa
di-load ulang oleh proses lain (mis. sectors_fetcher/service.py) tanpa
error "Can't get attribute ... on module '__main__'" -- pickle/joblib
menyimpan kelas lewat referensi modul, jadi kelas harus benar-benar bisa
di-import dari modul ini di proses manapun yang memuat file .joblib-nya.

TIDAK memakai label is_event_90d sama sekali. Begitu cakupan data (lihat
diagnosa di eda_and_feature_engineering.ipynb) sudah punya >=2 sampel kelas
positif, jalankan ulang modeling_and_evaluation.ipynb -- SUPERVISED_MODE di
sana akan otomatis kembali ke jalur GridSearchCV asli dan fallback ini
tidak lagi dipakai.
"""

from __future__ import annotations

import numpy as np
from sklearn.covariance import LedoitWolf
from sklearn.preprocessing import StandardScaler


class SkorAnomaliMahalanobis:
    """
    Skor risiko berbasis jarak Mahalanobis (kovarians dengan shrinkage
    Ledoit-Wolf, tahan terhadap kolom nyaris konstan/singular pada dataset
    kecil) terhadap pusat massa populasi emiten yang dipantau.

    Asumsi: mayoritas baris snapshot mewakili kondisi "normal"; emiten yang
    menyimpang jauh dari pusat massa pada 11 indikator risiko (leverage
    tinggi, likuiditas kering, dst.) dianggap lebih berisiko.

    Interface fit/predict_proba/feature_importances_ disamakan dengan
    estimator sklearn supaya kode pemanggil (notebook, service.py) tidak
    perlu tahu model mana yang sedang aktif.
    """

    def __init__(self, feature_cols: list[str]):
        self.feature_cols = list(feature_cols)
        self.scaler = StandardScaler()
        self.cov = LedoitWolf()

    def fit(self, X, y=None):
        Xs = self.scaler.fit_transform(X[self.feature_cols])
        self.cov.fit(Xs)
        d2 = self.cov.mahalanobis(Xs)
        self._d2_median = float(np.median(d2))
        mad = float(np.median(np.abs(d2 - self._d2_median)))
        self._d2_scale = mad if mad > 1e-9 else float(d2.std() + 1e-9)
        contrib = self._kontribusi(Xs)
        abs_mean = np.abs(contrib).mean(axis=0)
        self.feature_importances_ = abs_mean / (abs_mean.sum() + 1e-12)
        return self

    def _kontribusi(self, Xs):
        # d^2 (jarak Mahalanobis kuadrat) per baris = Xs @ precision_ @ Xs^T.
        # Dekomposisi aditif per fitur di bawah menjumlah tepat ke d^2 baris
        # tsb. -- dipakai persis seperti (koefisien x nilai) LR di notebook.
        proj = Xs @ self.cov.precision_
        return Xs * proj

    def mahalanobis_kontribusi(self, X):
        Xs = self.scaler.transform(X[self.feature_cols])
        return self._kontribusi(Xs)

    def predict_proba(self, X):
        Xs = self.scaler.transform(X[self.feature_cols])
        d2 = self.cov.mahalanobis(Xs)
        z = (d2 - self._d2_median) / self._d2_scale
        p = 1.0 / (1.0 + np.exp(-z))
        return np.column_stack([1 - p, p])
