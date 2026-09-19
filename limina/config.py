"""
config.py -- Konfigurasi terpusat proyek LIMINA
===================================================

Satu tempat untuk kredensial Supabase, nama tabel/kolom sumber, dan
parameter jendela latih/evaluasi. Notebook 01-05 mengimpor dari sini,
jadi mengganti nama tabel atau jadwal evaluasi cukup di satu berkas.

Kredensial HANYA dari variabel lingkungan (SUPABASE_URL, SUPABASE_KEY),
tidak pernah ditulis di kode. Isi lewat `.env` (salin dari
`.env.example`) atau ekspor langsung di shell/scheduler -- lihat README
bagian "Isi Kredensial Supabase". `python-dotenv` opsional, hanya
kenyamanan lokal; di GitHub Actions isi lewat secrets platform, `.env`
tidak wajib ada.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # python-dotenv belum terpasang -- tetap aman, lihat docstring
    pass

# Kredensial Supabase -- hanya dari environment, tanpa default di kode.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


def kredensial_lengkap() -> bool:
    """True kalau SUPABASE_URL dan SUPABASE_KEY berdua sudah terisi."""
    return bool(SUPABASE_URL) and bool(SUPABASE_KEY)


# Root proyek dan lokasi berkas, diturunkan dari lokasi berkas ini (bukan
# cwd) supaya notebook benar dijalankan dari folder mana pun.
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
LABELS_DIR = DATA_DIR / "labels"
PATH_TAKSONOMI = LABELS_DIR / "taksonomi_alasan_suspensi.json"

PATH_PANEL = DATA_DIR / "panel.csv"
PATH_RIWAYAT_SKOR = ARTIFACTS_DIR / "riwayat_skor.csv"
PATH_JENDELA = DATA_DIR / "jendela_latih.json"
PATH_KEPUTUSAN = ARTIFACTS_DIR / "keputusan.json"


def path_snapshot(tanggal: str) -> Path:
    return DATA_DIR / f"snapshot_{tanggal}.csv"


# Enam tabel Supabase: lima data mentah, stock_suspensions satu-satunya
# sumber label. Nama beda di Supabase Anda? Ganti di sini saja.
TABEL_QUARTERLY_FINANCIALS = "quarterly_financials"
TABEL_DAILY_TRANSACTION = "daily_transaction"
TABEL_DAILY_FULL_UNIVERSE_CLOSE = "daily_full_universe_close"
TABEL_FREE_FLOAT_SNAPSHOT = "free_float_snapshot"
TABEL_COMPANY_OVERVIEW = "company_overview"  # opsional tapi disarankan
TABEL_SUSPENSI = "stock_suspensions"

# Nama kolom tanggal/alasan suspensi sungguhan di Supabase Anda. Kode
# internal selalu memakai "event_date"/"reason"; notebook 01 mengganti
# nama kolom sumber ke situ sekali, tepat setelah diunduh.
KOLOM_TANGGAL_SUSPENSI = "suspension_date"
KOLOM_ALASAN_SUSPENSI = "reason"

# Jendela latih/evaluasi bergulir, dihitung ulang tiap run (splits.py).
# JENDELA_LABEL_HARI: satu sumber untuk horizon label -- labels.py dan
# raw_ingest.OFFSET_AS_OF_DARI_EVENT_HARI membacanya, jangan hardcode
# ulang di tempat lain (desinkron = label tersensor jadi salah). Rentang
# wajar 30-90 hari (AMBANG-peran-model-dan-evaluasi.md bagian 2).
JENDELA_LABEL_HARI = 30
JUMLAH_POTRET_EVALUASI = 6
JARAK_POTRET_HARI = 30

# Precision@K = 20 (rancangan awal: halaman Peringkat tampilkan 20 teratas).
# Turunkan kalau cakupan emiten Anda jauh lebih kecil dari ~900.
K_TOP = 20

# Riwayat skor mingguan untuk menghitung selisih waktu deteksi (notebook 04).
RIWAYAT_SKOR_HARI_SEBELUM_EVENT = 365
RIWAYAT_SKOR_FREKUENSI_HARI = 7


__all__ = [
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "kredensial_lengkap",
    "ROOT_DIR",
    "DATA_DIR",
    "RAW_DIR",
    "ARTIFACTS_DIR",
    "LABELS_DIR",
    "PATH_TAKSONOMI",
    "PATH_PANEL",
    "PATH_RIWAYAT_SKOR",
    "PATH_JENDELA",
    "PATH_KEPUTUSAN",
    "path_snapshot",
    "TABEL_QUARTERLY_FINANCIALS",
    "TABEL_DAILY_TRANSACTION",
    "TABEL_DAILY_FULL_UNIVERSE_CLOSE",
    "TABEL_FREE_FLOAT_SNAPSHOT",
    "TABEL_COMPANY_OVERVIEW",
    "TABEL_SUSPENSI",
    "KOLOM_TANGGAL_SUSPENSI",
    "KOLOM_ALASAN_SUSPENSI",
    "JENDELA_LABEL_HARI",
    "JUMLAH_POTRET_EVALUASI",
    "JARAK_POTRET_HARI",
    "K_TOP",
    "RIWAYAT_SKOR_HARI_SEBELUM_EVENT",
    "RIWAYAT_SKOR_FREKUENSI_HARI",
]
