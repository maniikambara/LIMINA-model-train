"""
baselines.py -- Tiga pembanding dasar
========================================

Dibangun sebelum model apa pun -- tanpa pembanding, angka model tidak
punya arti (AMBANG-peran-model-dan-evaluasi.md 4.5).

  1. Acak            -- lantai dasar mutlak
  2. Aturan tunggal   -- menguji apakah satu indikator saja sudah cukup
  3. Rule-based       -- pembanding sebenarnya, sekaligus jalur cadangan

Kandidat 3 dan 4 pada AMBA-struktur-model-dan-algoritma.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Bobot rule-based, ditetapkan tim berdasarkan penilaian domain, mengikuti
# kriteria Notasi Khusus BEI sebagai rujukan, bukan hasil pembelajaran dari
# data (AMBA-struktur-model-dan-algoritma.md bagian 6.1-6.2). Didokumentasikan
# terbuka di halaman metodologi produk.
BOBOT_RULE_BASED = {
    "lapor_terlambat": 3,
    "tanpa_pendapatan": 3,
    "ekuitas_negatif": 2,
    "ako_negatif_berturut_ge2": 2,
    "hari_tanpa_transaksi_90d_gt20": 1,
    "utang_terhadap_aset_gt08": 1,
}
SKOR_RULE_BASED_MAKS = sum(BOBOT_RULE_BASED.values())  # 12


def skor_acak(df: pd.DataFrame, seed: int = 42) -> pd.Series:
    """Ambil urutan acak sebagai lantai dasar mutlak."""
    rng = np.random.default_rng(seed)
    return pd.Series(rng.random(len(df)), index=df.index)


def skor_aturan_tunggal(df: pd.DataFrame) -> pd.Series:
    """
    Kandidat 3. Bukan model yang dilatih, hanya pengurutan berdasarkan satu
    indikator: jarak lapor. Makin besar lapor_jarak_hari (makin telat
    lapor), makin tinggi skor risikonya -- rank ascending (bukan
    descending) supaya nilai TERBESAR dapat persentil TERTINGGI, konsisten
    dengan konvensi skor lain (metrics.precision_at_k mengambil skor
    tertinggi sebagai top-K risiko).
    """
    return df["lapor_jarak_hari"].rank(pct=True) * 100


def skor_rule_based_mentah(row: pd.Series) -> float:
    """
    Skor mentah 0-12 untuk satu baris. Indikator yang NaN (data_complete=0
    sebagian) TIDAK diikutkan, bukan mem-NaN-kan seluruh skor -- baris
    dengan data sebagian tetap dapat skor parsial dari indikator yang ada.
    """
    def _kontribusi(nilai, bobot) -> float:
        return 0.0 if pd.isna(nilai) else bobot * bool(nilai)

    return (
        _kontribusi(row["lapor_terlambat"], BOBOT_RULE_BASED["lapor_terlambat"])
        + _kontribusi(row["tanpa_pendapatan"], BOBOT_RULE_BASED["tanpa_pendapatan"])
        + _kontribusi(row["ekuitas_negatif"], BOBOT_RULE_BASED["ekuitas_negatif"])
        + _kontribusi(
            None if pd.isna(row["ako_negatif_berturut"]) else row["ako_negatif_berturut"] >= 2,
            BOBOT_RULE_BASED["ako_negatif_berturut_ge2"],
        )
        + _kontribusi(
            None if pd.isna(row["hari_tanpa_transaksi_90d"]) else row["hari_tanpa_transaksi_90d"] > 20,
            BOBOT_RULE_BASED["hari_tanpa_transaksi_90d_gt20"],
        )
        + _kontribusi(
            None if pd.isna(row["utang_terhadap_aset"]) else row["utang_terhadap_aset"] > 0.8,
            BOBOT_RULE_BASED["utang_terhadap_aset_gt08"],
        )
    )


def skor_rule_based(df: pd.DataFrame) -> pd.Series:
    """
    Kandidat 4. Skor tertimbang dari kriteria Notasi Khusus, diubah jadi
    persentil terhadap seluruh emiten pada potret yang sama, dengan cara
    yang sama seperti kandidat lain.
    """
    skor_mentah = df.apply(skor_rule_based_mentah, axis=1)
    return skor_mentah.rank(pct=True) * 100


__all__ = [
    "BOBOT_RULE_BASED",
    "SKOR_RULE_BASED_MAKS",
    "skor_acak",
    "skor_aturan_tunggal",
    "skor_rule_based_mentah",
    "skor_rule_based",
]
