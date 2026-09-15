"""
leakage.py -- Empat pemeriksaan kebocoran
============================================

Kebocoran temporal adalah satu-satunya kesalahan yang membuat seluruh
hasil tidak sah tanpa memunculkan pesan galat apa pun
(docs/rancangan/AMBANG-peran-model-dan-evaluasi.md bagian 6).

Refleks yang wajib ditanam: hasil yang terlalu bagus adalah gejala,
bukan kabar baik.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


class PemeriksaanKebocoranGagal(Exception):
    """Dilempar ketika satu atau lebih pemeriksaan kebocoran gagal."""


def cek_tanggal_sumber(df: pd.DataFrame) -> list[str]:
    """
    Pemeriksaan 1: feature_max_source_date tidak boleh melewati as_of_date.
    Gagal berarti dataset dikembalikan ke peran data, tidak diperbaiki sendiri.
    """
    as_of = pd.to_datetime(df["as_of_date"])
    sumber = pd.to_datetime(df["feature_max_source_date"])
    bocor = df[sumber > as_of]
    if len(bocor) == 0:
        return []
    contoh = bocor["symbol"].head(5).tolist() if "symbol" in bocor.columns else []
    return [
        f"Pemeriksaan 1 gagal: {len(bocor)} baris punya "
        f"feature_max_source_date > as_of_date. Contoh symbol: {contoh}"
    ]


def cek_pengacakan_label(
    model_class,
    X_train_scaled: np.ndarray,
    y_train: pd.Series,
    *,
    seed: int = 1,
    batas_bawah: float = 0.40,
    batas_atas: float = 0.60,
) -> tuple[list[str], float]:
    """
    Pemeriksaan 2: acak seluruh label, latih ulang, hitung AUC. Hasil yang
    benar berada di sekitar 0,50. Jika masih jauh di atas itu, ada
    kesalahan pada alur pemrosesan, bukan pada data.

    Mengembalikan (daftar_masalah, auc_teracak).
    """
    y_acak = y_train.sample(frac=1, random_state=seed).reset_index(drop=True)
    model = model_class(class_weight="balanced", random_state=42)
    model.fit(X_train_scaled, y_acak)
    proba = model.predict_proba(X_train_scaled)[:, 1]
    auc = float(roc_auc_score(y_acak, proba))

    if batas_bawah <= auc <= batas_atas:
        return [], auc
    return [
        f"Pemeriksaan 2 gagal: AUC pada label acak = {auc:.3f}, "
        f"seharusnya sekitar 0.50 (rentang wajar {batas_bawah}-{batas_atas})"
    ], auc


def cek_fitur_kendali(
    model_class,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    scaler_class,
    *,
    seed: int = 42,
) -> tuple[list[str], float]:
    """
    Pemeriksaan 3: sisipkan satu kolom bilangan acak. Jika kolom tersebut
    muncul sebagai indikator berpengaruh, ada kesalahan pada perhitungan
    kepentingan fitur.

    Mengembalikan (daftar_masalah, koefisien_absolut_fitur_acak).
    """
    rng = np.random.default_rng(seed)
    X_dengan_acak = X_train.copy()
    X_dengan_acak["fitur_acak"] = rng.standard_normal(len(X_train))

    scaler = scaler_class()
    X_scaled = scaler.fit_transform(X_dengan_acak)

    model = model_class(class_weight="balanced", random_state=42)
    model.fit(X_scaled, y_train)

    koef_acak = abs(model.coef_[0][-1])
    koef_lain = np.abs(model.coef_[0][:-1])
    ambang = np.percentile(koef_lain, 50)

    if koef_acak < ambang:
        return [], float(koef_acak)
    return [
        f"Pemeriksaan 3 gagal: koefisien fitur acak ({koef_acak:.4f}) "
        f"tidak lebih kecil dari median koefisien indikator asli ({ambang:.4f})"
    ], float(koef_acak)


def cek_batas_kewajaran(auc_uji: float, *, batas_atas: float = 0.90) -> list[str]:
    """
    Pemeriksaan 4: AUC di atas 0,90 pada percobaan pertama diperlakukan
    sebagai gejala kebocoran, bukan keberhasilan. Hentikan, telusuri,
    laporkan ke tim.
    """
    if np.isnan(auc_uji):
        return []
    if auc_uji <= batas_atas:
        return []
    return [
        f"Pemeriksaan 4 gagal: AUC uji = {auc_uji:.3f}, di atas ambang wajar "
        f"{batas_atas}. Ini gejala kebocoran, bukan keberhasilan. "
        f"Telusuri ulang aturan point-in-time sebelum lanjut ke gerbang keputusan."
    ]


def jalankan_semua_pemeriksaan(
    *,
    df_panel: pd.DataFrame,
    model_class,
    scaler_class,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_train_scaled: np.ndarray,
    auc_uji: float | None = None,
    lempar_error: bool = True,
) -> dict:
    """
    Menjalankan keempat pemeriksaan berurutan dan mengumpulkan hasilnya.
    Dipanggil sebagai gerbang masuk sebelum data dipakai melatih model
    sungguhan (bukan sekadar sekali di akhir).
    """
    semua_masalah: list[str] = []

    semua_masalah += cek_tanggal_sumber(df_panel)

    masalah_2, auc_acak = cek_pengacakan_label(model_class, X_train_scaled, y_train)
    semua_masalah += masalah_2

    masalah_3, koef_acak = cek_fitur_kendali(model_class, X_train, y_train, scaler_class)
    semua_masalah += masalah_3

    if auc_uji is not None:
        semua_masalah += cek_batas_kewajaran(auc_uji)

    hasil = {
        "lolos": len(semua_masalah) == 0,
        "masalah": semua_masalah,
        "auc_pengacakan_label": auc_acak,
        "koefisien_fitur_acak": koef_acak,
    }

    if lempar_error and semua_masalah:
        raise PemeriksaanKebocoranGagal("\n- ".join([""] + semua_masalah))

    return hasil


__all__ = [
    "PemeriksaanKebocoranGagal",
    "cek_tanggal_sumber",
    "cek_pengacakan_label",
    "cek_fitur_kendali",
    "cek_batas_kewajaran",
    "jalankan_semua_pemeriksaan",
]
