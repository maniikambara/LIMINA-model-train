"""
supabase_io.py -- Pengambil data dari Supabase (baca saja)
==============================================================

HANYA membaca (download) tabel yang sudah ada di proyek Supabase Anda
lewat Data API -- tidak pernah DDL, tidak membuat/mengubah tabel, tidak
menulis (insert/update/upsert/delete) apa pun. Struktur database
sepenuhnya milik dan dikelola di luar proyek ini.

Kredensial dibaca HANYA dari limina.config (yang HANYA membaca dari
SUPABASE_URL/SUPABASE_KEY) -- tidak ada kredensial tertulis di berkas
ini, karena berkas ini bisa masuk repositori publik.

get_client() mengembalikan None (bukan melempar error) kalau kredensial
belum lengkap atau paket supabase-py belum terpasang, supaya pemanggil
bisa memeriksa None dan berhenti dengan pesan jelas (notebook 01),
bukan traceback membingungkan.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

try:
    from supabase import Client, create_client
except ImportError:  # supabase-py belum terpasang
    Client = None  # type: ignore[assignment,misc]
    create_client = None  # type: ignore[assignment]

from . import config

UKURAN_HALAMAN = 1000  # batas baris per respons Data API secara bawaan


def get_client(url: str | None = None, key: str | None = None) -> "Client | None":
    """
    Membuat klien Supabase dari url/key yang diberikan, atau dari
    limina.config.SUPABASE_URL/SUPABASE_KEY (hasil baca variabel
    lingkungan) kalau keduanya tidak diisi eksplisit.

    Mengembalikan None -- bukan melempar error -- kalau kredensial tetap
    tidak lengkap atau paket supabase-py belum terpasang.
    """
    if create_client is None:
        return None
    url = url or config.SUPABASE_URL
    key = key or config.SUPABASE_KEY
    if not url or not key:
        return None
    return create_client(url, key)


def download_table(
    client: "Client",
    nama_tabel: str,
    *,
    kolom: str = "*",
    filter_eq: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """
    Mengunduh SELURUH baris satu tabel Supabase, dipaginasi lewat range()
    supaya tidak berhenti di batas 1000 baris bawaan. Ini murni operasi
    baca: select() ... execute(), tidak ada insert/update/upsert/delete.

    client        hasil get_client(), wajib sudah bukan None
    nama_tabel    nama tabel di Supabase, apa adanya
    kolom         daftar kolom seperti dipakai .select(), default semua
    filter_eq     opsional, dict {nama_kolom: nilai} untuk .eq() berantai,
                  contoh {"sector": "banks"}

    Mengembalikan DataFrame kosong (tanpa error) kalau tabelnya memang
    tidak punya baris.
    """
    seluruh_baris: list[dict] = []
    awal = 0
    while True:
        kueri = client.table(nama_tabel).select(kolom)
        if filter_eq:
            for k, v in filter_eq.items():
                kueri = kueri.eq(k, v)
        respons = kueri.range(awal, awal + UKURAN_HALAMAN - 1).execute()
        baris = respons.data or []
        seluruh_baris.extend(baris)
        if len(baris) < UKURAN_HALAMAN:
            break
        awal += UKURAN_HALAMAN
    return pd.DataFrame(seluruh_baris)


def normalisasi_tabel_suspensi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sesuaikan nama kolom tabel stock_suspensions MENTAH ke konvensi
    internal: "event_date", "reason". Sumber kebenaran nama kolom asli:
    limina/config.py (KOLOM_TANGGAL_SUSPENSI, KOLOM_ALASAN_SUSPENSI) --
    fungsi ini membacanya supaya logikanya sendiri teruji
    (tests/test_supabase_io.py), bukan hidup dalam sel notebook.

    Melempar RuntimeError menyebut nama kolom yang dicari kalau
    symbol/event_date/reason tetap tidak lengkap setelah penyesuaian --
    supaya kesalahan nama kolom ketahuan di sini, bukan menyusul jadi
    KeyError membingungkan di limina/labels.py saat notebook 02 jalan.
    """
    df = df.copy()
    if config.KOLOM_TANGGAL_SUSPENSI != "event_date" and config.KOLOM_TANGGAL_SUSPENSI in df.columns:
        df = df.rename(columns={config.KOLOM_TANGGAL_SUSPENSI: "event_date"})
    if config.KOLOM_ALASAN_SUSPENSI != "reason" and config.KOLOM_ALASAN_SUSPENSI in df.columns:
        df = df.rename(columns={config.KOLOM_ALASAN_SUSPENSI: "reason"})

    kolom_wajib = {"symbol", "event_date", "reason"}
    hilang = kolom_wajib - set(df.columns)
    if hilang:
        raise RuntimeError(
            f"Tabel {config.TABEL_SUSPENSI} tidak punya kolom {hilang} setelah "
            f"penyesuaian nama (KOLOM_TANGGAL_SUSPENSI='{config.KOLOM_TANGGAL_SUSPENSI}', "
            f"KOLOM_ALASAN_SUSPENSI='{config.KOLOM_ALASAN_SUSPENSI}'). Cocokkan kedua "
            f"nilai itu di limina/config.py dengan nama kolom sungguhan di "
            f"tabel Supabase Anda, lalu jalankan ulang notebook 01."
        )
    return df


KOLOM_WAJIB_TABEL = {
    "quarterly_financials": {
        "symbol", "report_date", "revenue", "earnings", "total_equity",
        "total_liabilities", "total_assets", "operating_cash_flow",
    },
    "daily_transaction": {"symbol", "date", "close", "volume", "market_cap"},
    # daily_full_universe_close, per docs/rancangan/AMBANG-panduan-api-sectors.md,
    # HANYA menyediakan close -- volume/market_cap sering kosong di sini, jangan
    # diwajibkan (lihat catatan batasan limina/raw_ingest.py).
    "daily_full_universe_close": {"symbol", "date", "close"},
    "free_float_snapshot": {"symbol", "snapshot_date", "free_float"},
    "company_overview": {"symbol"},
}


def validasi_kolom_tabel(df: pd.DataFrame, nama_tabel: str) -> None:
    """
    Cek apakah satu tabel mentah punya kolom minimal yang dibutuhkan
    modul lain (KOLOM_WAJIB_TABEL). Dipanggil notebook 02 untuk kelima
    tabel selain stock_suspensions (yang punya jalur sendiri,
    normalisasi_tabel_suspensi, karena nama kolomnya bisa disesuaikan
    lewat limina/config.py).

    Melempar RuntimeError menyebut nama tabel dan kolom yang hilang --
    supaya kesalahan skema ketahuan segera, bukan menyusul jadi KeyError
    tidak jelas di limina/raw_ingest.py. Nama tabel tak dikenal dilewati,
    bukan dianggap salah.
    """
    kolom_wajib = KOLOM_WAJIB_TABEL.get(nama_tabel)
    if kolom_wajib is None:
        return
    hilang = kolom_wajib - set(df.columns)
    if hilang:
        raise RuntimeError(
            f"Tabel {nama_tabel} tidak punya kolom {sorted(hilang)}. Kolom yang "
            f"ada: {list(df.columns)}. Periksa nama kolom di Supabase Anda -- "
            f"kalau memang berbeda dari yang diharapkan, sesuaikan "
            f"KOLOM_WAJIB_TABEL di limina/supabase_io.py."
        )


__all__ = [
    "get_client",
    "download_table",
    "normalisasi_tabel_suspensi",
    "KOLOM_WAJIB_TABEL",
    "validasi_kolom_tabel",
    "UKURAN_HALAMAN",
]
