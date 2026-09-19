"""
snapshot.py -- Evaluasi potret realistis
===========================================

Menjalankan keempat kandidat pada satu potret uji, menghitung metrik
yang dilaporkan (AMBA-struktur-model-dan-algoritma.md 8, langkah 8-9).

Potret uji HANYA boleh dilihat satu kali sampai gerbang keputusan
(AMBANG-peran-model-dan-evaluasi.md 5.3). Modul ini tidak memaksakan itu
secara teknis, hanya menyediakan fungsi untuk dipanggil pada saat yang
tepat -- notebook 04 menjalankannya persis sekali per siklus latih.
"""

from __future__ import annotations

import pandas as pd

from . import baselines, models
from .metrics import hitung_auc, precision_at_k, recall_90h


def _kecualikan_data_tidak_lengkap(skor: pd.Series, snapshot: pd.DataFrame) -> pd.Series:
    """
    Turunkan skor emiten data_complete==0 ke bawah skor TERENDAH yang
    benar-benar terhitung pada potret ini, supaya tidak pernah masuk
    top-K -- emiten yang fiturnya tak terhitung tidak boleh diberi
    peringkat "biasa saja" hanya karena nilai kosongnya diisi median
    (AMBA-kamus-variabel.md 4). Baris ini TETAP ikut di y_true/recall
    sebagai peristiwa yang tidak mungkin tertangkap, bukan dihapus,
    supaya Precision@20/Recall@90h jujur mencerminkan cakupan yang bisa
    dinilai pada potret ini.

    Sentinel (skor_lengkap.min() - 1) sengaja bukan -inf: hitung_auc
    memakai sklearn roc_auc_score, yang menolak nilai tak berhingga.
    """
    if "data_complete" not in snapshot.columns:
        return skor
    mask_tidak_lengkap = snapshot["data_complete"] == 0
    if not mask_tidak_lengkap.any():
        return skor

    skor = skor.copy()
    skor_lengkap = skor[~mask_tidak_lengkap]
    sentinel = float(skor_lengkap.min() - 1.0) if len(skor_lengkap) else 0.0
    skor.loc[mask_tidak_lengkap] = sentinel
    return skor


def evaluasi_satu_kandidat(
    nama: str, y_true: pd.Series, skor: pd.Series, *, k: int = 20
) -> dict:
    return {
        "kandidat": nama,
        "precision_at_20": precision_at_k(y_true, skor, k=k),
        "recall_90h": recall_90h(y_true, skor, k=k),
        "auc": hitung_auc(y_true, skor),
    }


def evaluasi_semua_kandidat(
    snapshot: pd.DataFrame,
    model_lr,
    model_gb,
    scaler,
    median_latih: pd.Series,
    *,
    k: int = 20,
) -> pd.DataFrame:
    """
    Menghitung metrik keempat kandidat pada satu potret. Mengembalikan
    DataFrame satu baris per kandidat, siap digabung lintas potret untuk
    laporan Precision@20 lintas kuartal.

    Emiten dengan data_complete == 0 dikeluarkan dari pertimbangan top-K
    seluruh kandidat (lihat _kecualikan_data_tidak_lengkap) -- baseline
    rule-based dan aturan tunggal juga terkena ini, bukan hanya kedua
    model terlatih, supaya perbandingan antar kandidat tetap adil.
    """
    y_true = snapshot["is_event_90d"]

    skor_lr = models.skor_kandidat_1(model_lr, scaler, snapshot, median_latih)
    skor_gb = models.skor_kandidat_2(model_gb, snapshot, median_latih)
    skor_tunggal = baselines.skor_aturan_tunggal(snapshot)
    skor_rule = baselines.skor_rule_based(snapshot)
    skor_random = baselines.skor_acak(snapshot)

    skor_lr = _kecualikan_data_tidak_lengkap(skor_lr, snapshot)
    skor_gb = _kecualikan_data_tidak_lengkap(skor_gb, snapshot)
    skor_tunggal = _kecualikan_data_tidak_lengkap(skor_tunggal, snapshot)
    skor_rule = _kecualikan_data_tidak_lengkap(skor_rule, snapshot)
    skor_random = _kecualikan_data_tidak_lengkap(skor_random, snapshot)

    hasil = [
        evaluasi_satu_kandidat("regresi_logistik", y_true, skor_lr, k=k),
        evaluasi_satu_kandidat("gradient_boosting", y_true, skor_gb, k=k),
        evaluasi_satu_kandidat("aturan_tunggal", y_true, skor_tunggal, k=k),
        evaluasi_satu_kandidat("rule_based", y_true, skor_rule, k=k),
        evaluasi_satu_kandidat("acak", y_true, skor_random, k=k),
    ]
    return pd.DataFrame(hasil)


def evaluasi_lintas_potret(
    snapshot_dict: dict[str, pd.DataFrame],
    model_lr,
    model_gb,
    scaler,
    median_latih: pd.Series,
    *,
    k: int = 20,
) -> pd.DataFrame:
    """
    Menjalankan evaluasi_semua_kandidat untuk tiap potret dan menggabungkan
    hasilnya, dengan kolom 'tanggal_potret' ditambahkan. Ini yang mengisi
    tabel Precision@20 lintas potret pada halaman Bukti.
    """
    semua = []
    for tanggal, snap in snapshot_dict.items():
        hasil = evaluasi_semua_kandidat(snap, model_lr, model_gb, scaler, median_latih, k=k)
        hasil["tanggal_potret"] = tanggal
        hasil["jumlah_emiten"] = len(snap)
        hasil["jumlah_peristiwa"] = int(snap["is_event_90d"].sum())
        semua.append(hasil)
    return pd.concat(semua, ignore_index=True)


def keputusan_data_tidak_cukup(alasan: str) -> dict:
    """rule_based_penuh langsung, tanpa evaluasi lintas potret, dipakai
    saat notebook 03 gagal melatih model apa pun (data terlalu sedikit)."""
    return {"keputusan": "rule_based_penuh", "alasan": alasan}


def keputusan_anomali_saja(alasan: str) -> dict:
    """anomali_tanpa_label: Kandidat 5 berhasil dilatih (cukup baris
    lengkap) tapi Kandidat 1/2 tidak (positif < 2)."""
    return {"keputusan": "anomali_tanpa_label", "alasan": alasan}


def gerbang_keputusan(hasil_lintas_potret: pd.DataFrame) -> dict:
    """
    Gerbang keputusan (AMBANG-peran-model-dan-evaluasi.md 7,
    AMBA-struktur-model-dan-algoritma.md 2). Awalnya untuk tanggal tetap
    (10 Sep 2026, hackathon); sekarang dijalankan ulang tiap siklus latih
    di notebook 04, jadi perannya jadi pemeriksaan kesehatan berkelanjutan.

    Aturan: AUC median regresi_logistik < 0.60 -> rule_based penuh.
    regresi_logistik tidak mengalahkan rule_based pada Precision@20 di
    mayoritas potret -> rule_based mesin utama. Selain itu -> jalur ML.
    """
    auc_lr = hasil_lintas_potret.loc[
        hasil_lintas_potret["kandidat"] == "regresi_logistik", "auc"
    ]
    if auc_lr.median() < 0.60:
        return {
            "keputusan": "rule_based_penuh",
            "alasan": f"AUC median regresi logistik {auc_lr.median():.3f} di bawah 0.60",
        }

    pivot = hasil_lintas_potret.pivot(
        index="tanggal_potret", columns="kandidat", values="precision_at_20"
    )
    menang = (pivot["regresi_logistik"] > pivot["rule_based"]).sum()
    total_potret = len(pivot)

    if menang > total_potret / 2:
        return {
            "keputusan": "jalur_machine_learning",
            "alasan": (
                f"Regresi logistik mengalahkan rule-based pada {menang} dari "
                f"{total_potret} potret"
            ),
        }

    return {
        "keputusan": "rule_based_mesin_utama",
        "alasan": (
            f"Regresi logistik hanya menang pada {menang} dari {total_potret} "
            f"potret, tidak mayoritas. Rule-based menjadi mesin utama, model "
            f"tetap ditampilkan sebagai pembanding di halaman metodologi."
        ),
    }


__all__ = [
    "evaluasi_satu_kandidat",
    "evaluasi_semua_kandidat",
    "evaluasi_lintas_potret",
    "gerbang_keputusan",
    "keputusan_data_tidak_cukup",
    "keputusan_anomali_saja",
]