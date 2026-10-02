"""
ensemble.py
============

BlendedClassifier -- rata-rata predict_proba dari beberapa estimator/
pipeline sklearn (dipakai modeling_and_evaluation.ipynb Bagian 6.2 untuk
menggabungkan LR + RF). Ditaruh di modul terpisah (bukan di sel notebook)
supaya model_produksi.joblib bisa dimuat ulang di proses lain.
"""

from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone


class BlendedClassifier(ClassifierMixin, BaseEstimator):
    # Urutan mixin (ClassifierMixin dulu) wajib -- kalau kebalik,
    # __sklearn_tags__() tidak men-set estimator_type="classifier" dan
    # scorer roc_auc/average_precision gagal diam-diam.
    """Rata-rata predict_proba beberapa estimator/pipeline sklearn.

    fit(X, y) meng-clone lalu me-refit tiap anggota dari nol, jadi class
    ini bisa dipakai langsung di dalam cross_validate/GridSearchCV.

    Parameters
    ----------
    estimators : list[tuple[str, estimator]]
    """

    def __init__(self, estimators: list[tuple[str, object]]):
        # Simpan apa adanya (bukan list(estimators)) -- sklearn.base.clone()
        # membandingkan objek ini secara identitas, bukan kesetaraan.
        self.estimators = estimators

    def fit(self, X, y):
        self.classes_ = np.unique(y)
        self.fitted_ = [(name, clone(est).fit(X, y)) for name, est in self.estimators]
        return self

    def predict_proba(self, X):
        return np.mean([est.predict_proba(X) for _, est in self.fitted_], axis=0)

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)

    @property
    def feature_importances_(self):
        """Rata-rata |kontribusi| tiap anggota (feature_importances_ atau
        coef_, langsung atau lewat Pipeline named_steps["clf"]), dinormalisasi
        supaya berjumlah 1."""
        bobot = []
        for _, est in self.fitted_:
            inti = est.named_steps["clf"] if hasattr(est, "named_steps") and "clf" in est.named_steps else est
            if hasattr(inti, "feature_importances_"):
                bobot.append(np.abs(inti.feature_importances_))
            elif hasattr(inti, "coef_"):
                bobot.append(np.abs(inti.coef_[0]))
        if not bobot:
            raise AttributeError("Tidak ada anggota yang punya feature_importances_ atau coef_.")
        rata = np.mean(bobot, axis=0)
        return rata / (rata.sum() + 1e-12)
