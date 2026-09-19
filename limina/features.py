"""
features.py -- Perhitungan indikator
=======================================

Tiap fungsi menghitung SATU indikator turunan dari variabel mentah,
rumus persis di AMBA-kamus-variabel.md bagian 3. Data mentah yang masuk
harus sudah dipotong di titik point-in-time yang benar (lihat pit.py) --
modul ini tidak memotong tanggal sendiri.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BATAS_HARGA_BAWAH = 50  # Rp50, batas harga terendah yang diizinkan BEI
AMBANG_FREE_FLOAT_RENDAH = 0.10  # 10 persen, ambang awal, lihat README bagian keterbatasan


# ---------------------------------------------------------------------------
# Kelompok kepatuhan pelaporan (kamus variabel bagian 3.1)
# ---------------------------------------------------------------------------

def hitung_lapor_jarak_hari(as_of_date: pd.Timestamp, report_date_terakhir: pd.Timestamp) -> int:
    """as_of_date dikurangi report_date terakhir, dalam hari."""
    return (pd.Timestamp(as_of_date) - pd.Timestamp(report_date_terakhir)).days


def hitung_lapor_terlambat(lapor_jarak_hari: int, tenggat_hari: int = 90) -> int:
    """1 jika lapor_jarak_hari melampaui tenggat_hari (default 90 hari/satu
    kuartal, wajib diverifikasi terhadap aturan resmi BEI)."""
    return int(lapor_jarak_hari > tenggat_hari)


# ---------------------------------------------------------------------------
# Kelompok kesehatan finansial (kamus variabel bagian 3.2)
# ---------------------------------------------------------------------------

def hitung_tanpa_pendapatan(revenue: float, ambang_relatif: float = 1e-6) -> int:
    """1 jika revenue nol atau mendekati nol."""
    return int(abs(revenue) <= ambang_relatif)


def hitung_ekuitas_negatif(total_equity: float) -> int:
    """1 jika total_equity di bawah nol."""
    return int(total_equity < 0)


def hitung_utang_terhadap_aset(total_liabilities: float, total_assets: float) -> float:
    """total_liabilities dibagi total_assets."""
    if total_assets == 0:
        return float("nan")
    return total_liabilities / total_assets


def hitung_ako_negatif_berturut(operating_cash_flow_berurutan: list[float]) -> int:
    """Jumlah kuartal berturut-turut OCF < 0, mundur dari kuartal
    terakhir di operating_cash_flow_berurutan (urutan lama->baru)."""
    hitung = 0
    for ocf in reversed(operating_cash_flow_berurutan):
        if ocf < 0:
            hitung += 1
        else:
            break
    return hitung


# ---------------------------------------------------------------------------
# Kelompok likuiditas dan perilaku harga (kamus variabel bagian 3.3)
# ---------------------------------------------------------------------------

def hitung_hari_tanpa_transaksi_90d(volume_90_hari: pd.Series) -> int:
    """Jumlah hari volume bernilai nol dalam 90 hari terakhir."""
    return int((volume_90_hari == 0).sum())


def hitung_rasio_volume_30_90(volume_90_hari: pd.Series) -> float:
    """Rata-rata volume 30 hari terakhir dibagi rata-rata volume 90 hari."""
    volume_90_hari = volume_90_hari.sort_index()
    rata_90 = volume_90_hari.mean()
    rata_30 = volume_90_hari.tail(30).mean()
    if rata_90 == 0 or np.isnan(rata_90):
        return float("nan")
    return float(rata_30 / rata_90)


def hitung_hari_di_batas_bawah_90d(close_90_hari: pd.Series) -> int:
    """Jumlah hari close bernilai Rp50 (batas harga terendah BEI)."""
    return int((close_90_hari == BATAS_HARGA_BAWAH).sum())


def hitung_turun_dari_puncak_90d(close_90_hari: pd.Series) -> float:
    """Selisih relatif close hari ini terhadap close tertinggi 90 hari."""
    close_90_hari = close_90_hari.sort_index()
    puncak = close_90_hari.max()
    close_terakhir = close_90_hari.iloc[-1]
    if puncak == 0 or np.isnan(puncak):
        return float("nan")
    return float((close_terakhir - puncak) / puncak)


def hitung_volatilitas_90d(close_90_hari: pd.Series) -> float:
    """Simpangan baku imbal hasil harian selama 90 hari."""
    close_90_hari = close_90_hari.sort_index()
    imbal_hasil = close_90_hari.pct_change().dropna()
    if len(imbal_hasil) == 0:
        return float("nan")
    return float(imbal_hasil.std())


# ---------------------------------------------------------------------------
# Kelompok struktur kepemilikan, hanya untuk skor terkini (kamus variabel 3.4)
# ---------------------------------------------------------------------------

def hitung_free_float_rendah(free_float_persen: float, ambang: float = AMBANG_FREE_FLOAT_RENDAH) -> int:
    """1 jika free_float < ambang. HANYA untuk scoring live (notebook 05),
    tidak untuk melatih -- free_float_snapshot biasanya cuma simpan nilai
    terkini, bukan riwayat historis penuh."""
    return int(free_float_persen < ambang)


def hitung_seluruh_indikator_dari_baris_mentah(baris_mentah: dict) -> dict:
    """Orkestrasi: satu dict variabel mentah (symbol, as_of_date) ->
    seluruh indikator turunan. Kunci wajib: as_of_date,
    report_date_terakhir, revenue, total_equity, total_liabilities,
    total_assets, operating_cash_flow_berurutan, volume_90_hari
    (pd.Series terindeks tanggal), close_90_hari (idem)."""
    lapor_jarak = hitung_lapor_jarak_hari(
        baris_mentah["as_of_date"], baris_mentah["report_date_terakhir"]
    )
    return {
        "lapor_jarak_hari": lapor_jarak,
        "lapor_terlambat": hitung_lapor_terlambat(lapor_jarak),
        "tanpa_pendapatan": hitung_tanpa_pendapatan(baris_mentah["revenue"]),
        "ekuitas_negatif": hitung_ekuitas_negatif(baris_mentah["total_equity"]),
        "utang_terhadap_aset": hitung_utang_terhadap_aset(
            baris_mentah["total_liabilities"], baris_mentah["total_assets"]
        ),
        "ako_negatif_berturut": hitung_ako_negatif_berturut(
            baris_mentah["operating_cash_flow_berurutan"]
        ),
        "hari_tanpa_transaksi_90d": hitung_hari_tanpa_transaksi_90d(baris_mentah["volume_90_hari"]),
        "rasio_volume_30_90": hitung_rasio_volume_30_90(baris_mentah["volume_90_hari"]),
        "hari_di_batas_bawah_90d": hitung_hari_di_batas_bawah_90d(baris_mentah["close_90_hari"]),
        "turun_dari_puncak_90d": hitung_turun_dari_puncak_90d(baris_mentah["close_90_hari"]),
        "volatilitas_90d": hitung_volatilitas_90d(baris_mentah["close_90_hari"]),
    }


__all__ = [
    "BATAS_HARGA_BAWAH",
    "AMBANG_FREE_FLOAT_RENDAH",
    "hitung_lapor_jarak_hari",
    "hitung_lapor_terlambat",
    "hitung_tanpa_pendapatan",
    "hitung_ekuitas_negatif",
    "hitung_utang_terhadap_aset",
    "hitung_ako_negatif_berturut",
    "hitung_hari_tanpa_transaksi_90d",
    "hitung_rasio_volume_30_90",
    "hitung_hari_di_batas_bawah_90d",
    "hitung_turun_dari_puncak_90d",
    "hitung_volatilitas_90d",
    "hitung_free_float_rendah",
    "hitung_seluruh_indikator_dari_baris_mentah",
]
