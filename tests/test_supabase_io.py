"""
test_supabase_io.py -- Uji penyesuaian nama kolom tabel suspensi
====================================================================

Ditambahkan setelah satu insiden nyata: nilai bawaan
config.KOLOM_TANGGAL_SUSPENSI sempat salah diisi "event_date" (nama
internal), padahal kolom sungguhan di tabel stock_suspensions bernama
"suspension_date". Notebook 01 sempat berhenti dengan RuntimeError, dan
kalau lolos dari situ, limina/labels.py akan gagal dengan KeyError yang
jauh lebih membingungkan sumbernya. Uji pertama di bawah ini
langsung memeriksa NILAI BAWAAN config.py terhadap skema yang sudah
dikonfirmasi, supaya kesalahan sejenis ketahuan di sini, bukan menyusul
lagi lewat traceback pengguna.
"""

import pandas as pd
import pytest

from limina import config, supabase_io


def test_normalisasi_tabel_suspensi_cocok_dengan_nilai_bawaan_config():
    # Skema tabel stock_suspensions sungguhan yang sudah dikonfirmasi:
    # symbol, suspension_date, reason, pdf_url. Kolom kedua di sini
    # SENGAJA dibuat dari config.KOLOM_TANGGAL_SUSPENSI, bukan ditulis
    # literal "suspension_date" -- supaya kalau nilai bawaan itu berubah
    # (sengaja atau tidak sengaja) tanpa disesuaikan dengan skema asli,
    # uji ini tetap mengetes kombinasi yang benar-benar akan dipakai.
    df = pd.DataFrame({
        "symbol": ["AAAA", "BBBB"],
        config.KOLOM_TANGGAL_SUSPENSI: ["2024-01-01", "2024-06-01"],
        "reason": ["belum menyampaikan laporan keuangan auditan", "permintaan emiten"],
        "pdf_url": ["", ""],
    })
    hasil = supabase_io.normalisasi_tabel_suspensi(df)
    assert {"symbol", "event_date", "reason"}.issubset(hasil.columns)
    assert hasil["event_date"].tolist() == ["2024-01-01", "2024-06-01"]


def test_normalisasi_tabel_suspensi_menangani_skema_sungguhan_suspension_date():
    # Beda dari uji di atas: kolom di sini ditulis LITERAL "suspension_date",
    # bukan lewat config.KOLOM_TANGGAL_SUSPENSI. Ini penjaga regresi yang
    # sesungguhnya untuk insiden yang memicu berkas ini -- kalau nilai
    # bawaan config.py pernah salah diisi lagi (mis. balik ke "event_date"),
    # uji ini gagal, karena literal "suspension_date" di bawah tidak lagi
    # cocok dengan apa yang dicari fungsinya.
    df = pd.DataFrame({
        "symbol": ["AAAA"],
        "suspension_date": ["2024-01-01"],
        "reason": ["ketidakpastian atas kelangsungan usaha"],
        "pdf_url": [""],
    })
    hasil = supabase_io.normalisasi_tabel_suspensi(df)
    assert "event_date" in hasil.columns
    assert hasil["event_date"].tolist() == ["2024-01-01"]


def test_normalisasi_tabel_suspensi_sudah_sesuai_tidak_diubah():
    df = pd.DataFrame({"symbol": ["AAAA"], "event_date": ["2024-01-01"], "reason": ["x"]})
    hasil = supabase_io.normalisasi_tabel_suspensi(df)
    assert list(hasil.columns) == ["symbol", "event_date", "reason"]


def test_normalisasi_tabel_suspensi_melempar_error_jelas_kalau_kolom_hilang():
    df = pd.DataFrame({"symbol": ["AAAA"], "kolom_tak_dikenal": ["x"]})
    with pytest.raises(RuntimeError, match="tidak punya kolom"):
        supabase_io.normalisasi_tabel_suspensi(df)


def test_normalisasi_tabel_suspensi_tidak_mengubah_dataframe_asli():
    df_asli = pd.DataFrame({
        "symbol": ["AAAA"], config.KOLOM_TANGGAL_SUSPENSI: ["2024-01-01"], "reason": ["x"],
    })
    kolom_sebelum = list(df_asli.columns)
    supabase_io.normalisasi_tabel_suspensi(df_asli)
    assert list(df_asli.columns) == kolom_sebelum  # tidak diubah in-place


def test_validasi_kolom_tabel_lolos_untuk_skema_lengkap():
    df = pd.DataFrame(columns=[
        "symbol", "report_date", "revenue", "earnings", "total_equity",
        "total_liabilities", "total_assets", "operating_cash_flow", "fetched_at",
    ])
    supabase_io.validasi_kolom_tabel(df, "quarterly_financials")  # tidak melempar


def test_validasi_kolom_tabel_melempar_error_jelas_kalau_kolom_hilang():
    df = pd.DataFrame(columns=["symbol", "report_date"])  # revenue dkk sengaja dihilangkan
    with pytest.raises(RuntimeError, match="quarterly_financials.*tidak punya kolom"):
        supabase_io.validasi_kolom_tabel(df, "quarterly_financials")


def test_validasi_kolom_tabel_daily_full_universe_close_tidak_wajibkan_volume():
    # daily_full_universe_close di data sungguhan sering hanya punya close,
    # volume/market_cap kosong -- validasi ini TIDAK boleh mewajibkan keduanya.
    df = pd.DataFrame(columns=["symbol", "date", "close"])
    supabase_io.validasi_kolom_tabel(df, "daily_full_universe_close")  # tidak melempar


def test_validasi_kolom_tabel_nama_tabel_tak_dikenal_dilewati():
    df = pd.DataFrame(columns=["apa_saja"])
    supabase_io.validasi_kolom_tabel(df, "tabel_yang_tidak_ada_di_daftar")  # tidak melempar
