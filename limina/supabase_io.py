"""
supabase_io.py -- Pengambil data dari Supabase (baca saja)
==============================================================

Modul ini HANYA membaca (download) data dari tabel yang sudah ada di
proyek Supabase Anda lewat Data API. Modul ini tidak pernah menjalankan
DDL, tidak membuat atau mengubah tabel, dan tidak menulis (insert/update/
upsert/delete) apa pun ke Supabase. Struktur database sepenuhnya milik
dan dikelola di luar proyek ini.

Kredensial dibaca HANYA dari limina.config (yang HANYA membaca dari
variabel lingkungan SUPABASE_URL/SUPABASE_KEY) -- tidak ada URL atau
kunci yang ditulis langsung di berkas ini. Ini sengaja: berkas ini akan
masuk repositori publik, dan menulis kredensial proyek nyata di kode
adalah risiko keamanan terlepas dari jenis kunci apa pun yang dipakai.

get_client() mengembalikan None (bukan melempar error) kalau kredensial
belum lengkap atau paket supabase-py belum terpasang, supaya pemanggil
bisa memeriksa None lebih dulu dan berhenti dengan pesan yang jelas
(lihat notebook 01), bukan traceback yang membingungkan.
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
    Menyesuaikan nama kolom tabel stock_suspensions MENTAH (apa adanya
    dari Supabase) ke konvensi internal proyek: "event_date" dan
    "reason". Sumber kebenaran nama kolom asli ada di satu tempat,
    limina/config.py (KOLOM_TANGGAL_SUSPENSI, KOLOM_ALASAN_SUSPENSI) --
    fungsi ini yang membacanya, supaya logikanya sendiri bisa diuji
    (lihat tests/test_supabase_io.py), bukan hanya hidup sebagai kode di
    dalam sel notebook yang gampang lolos dari pengujian.

    Melempar RuntimeError dengan pesan yang menyebut nama kolom yang
    sedang dicari kalau symbol/event_date/reason tetap tidak lengkap
    setelah penyesuaian -- supaya kesalahan nama kolom ketahuan di sini,
    bukan menyusul jadi KeyError yang membingungkan jauh di
    limina/labels.py saat notebook 02 dijalankan.
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


__all__ = ["get_client", "download_table", "normalisasi_tabel_suspensi", "UKURAN_HALAMAN"]
