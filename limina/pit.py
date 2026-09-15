"""
pit.py -- Pemeriksa point-in-time
====================================

Satu aturan yang menentukan sah atau tidaknya seluruh hasil
(docs/rancangan/AMBANG-konsep-dan-rancangan.md bagian 7.5):

    Untuk sampel dengan tanggal peristiwa T, tidak boleh ada satu pun
    indikator yang memakai data yang baru tersedia setelah T dikurangi
    30 hari.

Ditulis sebelum indikator pertama dibuat. Dipakai di sisi PENGAMBILAN
data (memilih report_date dan rentang tanggal yang benar sebelum
dipakai), berbeda dari limina/leakage.py yang memeriksa dataset yang
SUDAH jadi setelah diambil. Dua lapis pemeriksaan ini sengaja tumpang
tindih.
"""

from __future__ import annotations

import pandas as pd


def titik_potong(tanggal_peristiwa: str | pd.Timestamp, mundur_hari: int = 30) -> pd.Timestamp:
    """
    Titik potong T dikurangi mundur_hari, dipakai sebagai batas atas untuk
    seluruh data yang boleh dipakai menghitung indikator sampel ini.
    """
    return pd.Timestamp(tanggal_peristiwa) - pd.Timedelta(days=mundur_hari)


def pilih_report_date_valid(
    tanggal_laporan_tersedia: list[str | pd.Timestamp], titik_potong_tanggal: pd.Timestamp
) -> pd.Timestamp | None:
    """
    Dari daftar tanggal laporan kuartalan yang valid untuk satu emiten,
    pilih yang PALING BARU tapi masih sebelum atau sama dengan titik
    potong. Ini mencegah pelanggaran point-in-time: memakai laporan
    "terbaru" tanpa syarat bisa mengembalikan laporan dari masa depan
    relatif terhadap peristiwa yang sedang dianalisis.

    Mengembalikan None jika tidak ada laporan yang valid -- kasus ini
    berarti emiten belum punya laporan cukup lama sebelum titik potong,
    dan wajib ditandai data_complete = 0, bukan diberi nilai kosong diam-diam.
    """
    kandidat = [pd.Timestamp(t) for t in tanggal_laporan_tersedia if pd.Timestamp(t) <= titik_potong_tanggal]
    if not kandidat:
        return None
    return max(kandidat)


def rentang_harga_valid(
    titik_potong_tanggal: pd.Timestamp, jendela_hari: int = 90
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    Rentang [start, end] yang boleh dipakai dari tabel harga untuk
    menghitung indikator likuiditas dan harga pada satu titik potong,
    tanpa menyentuh data setelah titik potong.
    """
    end = titik_potong_tanggal
    start = end - pd.Timedelta(days=jendela_hari)
    return start, end


def periksa_baris(
    as_of_date: str | pd.Timestamp,
    feature_max_source_date: str | pd.Timestamp,
) -> bool:
    """
    Pemeriksaan paling sederhana dan paling penting: apakah tanggal
    ketersediaan sumber data untuk satu baris masih sebelum atau sama
    dengan as_of_date baris itu. Sama persis dengan Pemeriksaan 1 di
    limina/leakage.py, disediakan di sini juga supaya sisi pengambilan
    data bisa memanggilnya SEBELUM baris ditulis ke panel, bukan sesudahnya.
    """
    return pd.Timestamp(feature_max_source_date) <= pd.Timestamp(as_of_date)


def periksa_dataframe(df, kolom_as_of: str = "as_of_date", kolom_sumber: str = "feature_max_source_date"):
    """Versi vektor dari periksa_baris untuk seluruh DataFrame sekaligus."""
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
