"""
contracts.py -- Skema dataset dan validator
=============================================

Mendefinisikan kontrak kolom untuk dua bentuk data (lihat
docs/rancangan/AMBANG-peran-model-dan-evaluasi.md bagian 3):

  - data/panel.csv               satu baris per (emiten, as_of_date)
  - data/snapshot_<tanggal>.csv    skema sama, seluruh emiten pada satu tanggal

Tidak ada satu pun fungsi di sini yang mengambil data dari Supabase.
Modul ini murni mendefinisikan bentuk data dan memeriksanya sebelum
dipakai modul lain.
"""

from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# Kolom indikator turunan (docs/rancangan/AMBA-kamus-variabel.md bagian
# 3.1-3.3). Ini kolom fitur yang benar-benar masuk ke model. Urutannya
# dijaga tetap supaya index koefisien model selalu bisa dipetakan balik
# ke nama indikator.
# ---------------------------------------------------------------------------
KOLOM_FITUR = [
    "lapor_jarak_hari",
    "lapor_terlambat",
    "tanpa_pendapatan",
    "ekuitas_negatif",
    "utang_terhadap_aset",
    "ako_negatif_berturut",
    "hari_tanpa_transaksi_90d",
    "rasio_volume_30_90",
    "hari_di_batas_bawah_90d",
    "turun_dari_puncak_90d",
    "volatilitas_90d",
]

# free_float_rendah sengaja dipisah dari KOLOM_FITUR: hanya boleh dipakai
# saat scoring live (notebook 05), tidak boleh dipakai saat melatih model.
KOLOM_FITUR_LIVE_ONLY = ["free_float_rendah"]

# Kolom identitas dan label, wajib ada di setiap baris panel/potret
KOLOM_IDENTITAS = [
    "symbol",
    "as_of_date",
    "sector",
    "board",
    "is_event_90d",
    "event_date",
    "event_category",
    "already_flagged",
    "data_complete",
    "feature_max_source_date",
]

KOLOM_WAJIB_PANEL = KOLOM_IDENTITAS + KOLOM_FITUR

# Kolom keluaran yang tampil ke pengguna (kamus variabel bagian 4)
KOLOM_KELUARAN = [
    "skor",
    "persentil",
    "kategori",
    "arah_30h",
    "status",
    "indikator_dominan",
]

# Kolom evaluasi internal, tidak pernah dilihat pengguna (kamus variabel bagian 5)
KOLOM_EVALUASI = [
    "precision_at_20",
    "recall_90h",
    "auc",
    "akurasi",
    "selisih_hari",
    "kejadian_terlewat",
    "alarm_palsu",
]

KATEGORI_EVENT_POSITIF = "C"


class KontrakError(Exception):
    """Dilempar ketika dataset yang masuk melanggar kontrak skema."""


def validate_panel(df: pd.DataFrame, *, ketat: bool = True) -> list[str]:
    """
    Memeriksa apakah df memenuhi kontrak panel/potret.

    Mengembalikan daftar pesan masalah (kosong berarti lolos). Jika
    ketat=True, melempar KontrakError begitu ada masalah, sesuai prinsip
    "data yang gagal dikembalikan ke pemiliknya, bukan diperbaiki diam-diam".
    """
    masalah: list[str] = []

    kolom_hilang = [k for k in KOLOM_WAJIB_PANEL if k not in df.columns]
    if kolom_hilang:
        masalah.append(f"Kolom wajib hilang: {kolom_hilang}")

    if "is_event_90d" in df.columns:
        nilai_tak_dikenal = set(df["is_event_90d"].dropna().unique()) - {0, 1}
        if nilai_tak_dikenal:
            masalah.append(f"is_event_90d punya nilai selain 0/1: {nilai_tak_dikenal}")

    if "event_category" in df.columns:
        kategori_dikenal = {"A", "B", "C", None, ""}
        aneh = set(df["event_category"].dropna().unique()) - kategori_dikenal
        if aneh:
            masalah.append(f"event_category punya nilai di luar A/B/C: {aneh}")

    if {"as_of_date", "feature_max_source_date"}.issubset(df.columns):
        as_of = pd.to_datetime(df["as_of_date"])
        sumber = pd.to_datetime(df["feature_max_source_date"])
        bocor = df[sumber > as_of]
        if len(bocor) > 0:
            masalah.append(
                f"{len(bocor)} baris melanggar aturan point-in-time "
                f"(feature_max_source_date > as_of_date), contoh symbol: "
                f"{bocor['symbol'].head(5).tolist() if 'symbol' in bocor.columns else '?'}"
            )

    if "data_complete" in df.columns:
        nilai_tak_dikenal = set(df["data_complete"].dropna().unique()) - {0, 1}
        if nilai_tak_dikenal:
            masalah.append(f"data_complete punya nilai selain 0/1: {nilai_tak_dikenal}")

    if ketat and masalah:
        raise KontrakError(
            "Dataset melanggar kontrak, dikembalikan ke sumbernya, "
            "tidak diperbaiki di sini:\n- " + "\n- ".join(masalah)
        )

    return masalah


def is_snapshot_lengkap(df: pd.DataFrame) -> bool:
    """
    Potret uji wajib memuat seluruh emiten cakupan, bukan sampel berimbang.
    Ini pemeriksaan kasar: proporsi positif pada potret harus mendekati
    kondisi pasar nyata (di bawah ~10 persen), bukan rasio 1:3 hasil sampling.
    """
    if "is_event_90d" not in df.columns or len(df) == 0:
        return False
    proporsi_positif = df["is_event_90d"].mean()
    return proporsi_positif < 0.10


__all__ = [
    "KOLOM_FITUR",
    "KOLOM_FITUR_LIVE_ONLY",
    "KOLOM_IDENTITAS",
    "KOLOM_WAJIB_PANEL",
    "KOLOM_KELUARAN",
    "KOLOM_EVALUASI",
    "KATEGORI_EVENT_POSITIF",
    "KontrakError",
    "validate_panel",
    "is_snapshot_lengkap",
]
