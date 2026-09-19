"""
metrics.py -- Precision@k, recall, AUC, selisih waktu
========================================================

Akurasi TIDAK PERNAH dihitung sebagai metrik yang dilaporkan di sini.
Boleh dihitung untuk rasa ingin tahu internal lewat fungsi terpisah yang
ditandai jelas, tapi tidak ada satu fungsi pun bernama sesuatu yang bisa
tertukar dengan metrik utama (docs/rancangan/AMBANG-peran-model-dan-evaluasi.md
bagian 4.3).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


def precision_at_k(y_true, skor, k: int = 20) -> float:
    """
    Dari k emiten berskor tertinggi pada satu potret, berapa proporsi yang
    benar-benar mengalami peristiwa dalam 90 hari.
    """
    y_true = np.asarray(y_true)
    skor = np.asarray(skor)
    if len(y_true) == 0:
        return float("nan")
    urutan = np.argsort(-skor)[: min(k, len(skor))]
    return float(y_true[urutan].mean())


def recall_90h(y_true, skor, k: int = 20) -> float:
    """
    Dari seluruh peristiwa yang terjadi dalam 90 hari pada potret ini,
    berapa proporsi yang berhasil masuk k besar.
    """
    y_true = np.asarray(y_true)
    skor = np.asarray(skor)
    total_positif = y_true.sum()
    if total_positif == 0:
        return float("nan")
    urutan = np.argsort(-skor)[: min(k, len(skor))]
    tertangkap = y_true[urutan].sum()
    return float(tertangkap / total_positif)


def hitung_auc(y_true, skor) -> float:
    """
    Area di bawah kurva ROC. Dilaporkan sebagai pelengkap, bukan klaim
    utama (docs/rancangan/AMBA-kamus-variabel.md bagian 5).
    """
    y_true = np.asarray(y_true)
    if len(set(y_true.tolist())) < 2:
        return float("nan")
    return float(roc_auc_score(y_true, skor))


def akurasi_internal_saja(y_true, y_pred) -> float:
    """
    Dihitung untuk keperluan internal SAJA. Tidak pernah dilaporkan ke
    README, dashboard, maupun halaman metodologi
    (docs/rancangan/AMBA-kamus-variabel.md bagian 5,
    docs/rancangan/AMBANG-peran-model-dan-evaluasi.md bagian 13 poin 1).
    Nama fungsi sengaja panjang dan eksplisit supaya tidak sengaja dipakai
    di jalur pelaporan publik.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    return float((y_true == y_pred).mean())


def kalibrasi_ambang(skor_latih: np.ndarray, jumlah_top: int = 20, total_cakupan: int | None = None) -> float:
    """
    Ambang skor pada data latih setara posisi top-K dari seluruh cakupan
    (AMBANG-peran-model-dan-evaluasi.md 4.4 langkah 1). jumlah_top
    di-min-kan dengan n: kalau cakupan lebih kecil dari yang diminta,
    tanpa batas ini np.percentile menerima persentil negatif dan melempar
    ValueError, bukan ambang yang masuk akal.
    """
    n = total_cakupan or len(skor_latih)
    jumlah_top = min(jumlah_top, n) if n else jumlah_top
    persentil_ambang = 100 * (1 - jumlah_top / n)
    return float(np.percentile(skor_latih, persentil_ambang))


def hitung_selisih_waktu(
    riwayat_skor: pd.DataFrame,
    ambang: float,
    tanggal_peristiwa: pd.Timestamp,
    *,
    kolom_tanggal: str = "tanggal",
    kolom_skor: str = "skor",
) -> dict:
    """
    Implementasi langkah 2-5 AMBANG-peran-model-dan-evaluasi.md 4.4.
    riwayat_skor: panel satu emiten, terurut naik, sampai tanggal
    peristiwa. Tandai tanggal PERTAMA skor melewati ambang DAN bertahan
    dua titik berturut-turut (lonjakan sesaat tidak dihitung).

    Balikan: terdeteksi (bool), tanggal_terdeteksi (Timestamp|None),
    selisih_hari (int|None). Tidak pernah melewati ambang -> terdeteksi=False
    (kejadian terlewat).
    """
    riwayat = riwayat_skor.sort_values(kolom_tanggal).reset_index(drop=True)
    melewati = riwayat[kolom_skor] >= ambang

    for i in range(len(melewati) - 1):
        if melewati.iloc[i] and melewati.iloc[i + 1]:
            tanggal_terdeteksi = riwayat.loc[i, kolom_tanggal]
            selisih = (pd.Timestamp(tanggal_peristiwa) - pd.Timestamp(tanggal_terdeteksi)).days
            return {
                "terdeteksi": True,
                "tanggal_terdeteksi": tanggal_terdeteksi,
                "selisih_hari": int(selisih),
            }

    return {"terdeteksi": False, "tanggal_terdeteksi": None, "selisih_hari": None}


def ringkas_selisih_waktu(daftar_hasil: list[dict]) -> dict:
    """Ringkas hitung_selisih_waktu (median/p25/p75 + kejadian terlewat).
    Median tidak dihitung dari kasus terlewat -- melaporkan rata-rata
    tanpa jumlah terlewat itu menyesatkan (AMBANG-... 4.4)."""
    terdeteksi = [h["selisih_hari"] for h in daftar_hasil if h["terdeteksi"]]
    kejadian_terlewat = sum(1 for h in daftar_hasil if not h["terdeteksi"])

    if not terdeteksi:
        return {
            "median_hari": None,
            "p25_hari": None,
            "p75_hari": None,
            "kejadian_terlewat": kejadian_terlewat,
            "jumlah_terdeteksi": 0,
        }

    arr = np.array(terdeteksi)
    return {
        "median_hari": float(np.median(arr)),
        "p25_hari": float(np.percentile(arr, 25)),
        "p75_hari": float(np.percentile(arr, 75)),
        "kejadian_terlewat": kejadian_terlewat,
        "jumlah_terdeteksi": len(terdeteksi),
    }


__all__ = [
    "precision_at_k",
    "recall_90h",
    "hitung_auc",
    "akurasi_internal_saja",
    "kalibrasi_ambang",
    "hitung_selisih_waktu",
    "ringkas_selisih_waktu",
]
