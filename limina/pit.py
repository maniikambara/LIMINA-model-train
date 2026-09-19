"""
pit.py -- Pemeriksa point-in-time
====================================

Aturan yang menentukan sah tidaknya seluruh hasil (AMBANG-konsep-dan-
rancangan.md 7.5): untuk sampel bertanggal peristiwa T, tidak boleh ada
indikator yang memakai data yang baru tersedia setelah T-30 hari.

Dipakai di sisi PENGAMBILAN data (pilih report_date/rentang tanggal yang
benar SEBELUM dipakai) -- beda dari leakage.py yang memeriksa dataset
yang sudah jadi. Dua lapis ini sengaja tumpang tindih.
"""

from __future__ import annotations

import pandas as pd


def titik_potong(tanggal_peristiwa: str | pd.Timestamp, mundur_hari: int = 30) -> pd.Timestamp:
    """T dikurangi mundur_hari: batas atas data yang boleh dipakai."""
    return pd.Timestamp(tanggal_peristiwa) - pd.Timedelta(days=mundur_hari)


def pilih_report_date_valid(
    tanggal_laporan_tersedia: list[str | pd.Timestamp], titik_potong_tanggal: pd.Timestamp
) -> pd.Timestamp | None:
    """
    Laporan kuartalan PALING BARU yang masih <= titik potong -- mencegah
    "laporan terbaru" tanpa syarat memakai data dari masa depan relatif
    peristiwa yang dianalisis. None berarti belum ada laporan valid
    (wajib data_complete=0, bukan diisi kosong diam-diam).
    """
    kandidat = [pd.Timestamp(t) for t in tanggal_laporan_tersedia if pd.Timestamp(t) <= titik_potong_tanggal]
    if not kandidat:
        return None
    return max(kandidat)


def rentang_harga_valid(
    titik_potong_tanggal: pd.Timestamp, jendela_hari: int = 90
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Rentang [start, end] tabel harga yang boleh dipakai pada satu titik potong."""
    end = titik_potong_tanggal
    start = end - pd.Timedelta(days=jendela_hari)
    return start, end


def periksa_baris(
    as_of_date: str | pd.Timestamp,
    feature_max_source_date: str | pd.Timestamp,
) -> bool:
    """
    Pemeriksaan inti: tanggal ketersediaan sumber data <= as_of_date.
    Sama dengan Pemeriksaan 1 di leakage.py, disediakan di sini juga
    supaya sisi pengambilan data bisa memanggilnya SEBELUM baris ditulis.
    """
    return pd.Timestamp(feature_max_source_date) <= pd.Timestamp(as_of_date)


def periksa_dataframe(df, kolom_as_of: str = "as_of_date", kolom_sumber: str = "feature_max_source_date"):
    """Versi vektor dari periksa_baris untuk satu DataFrame sekaligus."""
    as_of = pd.to_datetime(df[kolom_as_of])
    sumber = pd.to_datetime(df[kolom_sumber])
    return sumber <= as_of


__all__ = [
    "titik_potong",
    "pilih_report_date_valid",
    "rentang_harga_valid",
    "periksa_baris",
    "periksa_dataframe",
]
