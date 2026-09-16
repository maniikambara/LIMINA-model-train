"""
config.py -- Konfigurasi terpusat proyek LIMINA
===================================================

Satu tempat untuk seluruh nilai yang mungkin perlu diganti pengguna:
kredensial Supabase, nama tabel/kolom sumber, dan parameter jendela
latih/evaluasi bergulir. Notebook 01-05 semuanya mengimpor dari sini,
supaya mengganti nama tabel atau jadwal evaluasi tidak berarti mengubah
banyak berkas sekaligus.

Kredensial Supabase HANYA dibaca dari variabel lingkungan (SUPABASE_URL,
SUPABASE_KEY), tidak pernah ditulis langsung di kode. Cara mengisinya:
salin `.env.example` menjadi `.env` lalu isi nilai Anda, atau ekspor
kedua variabel itu langsung di shell/scheduler yang menjalankan
notebook. Lihat README bagian "Isi Kredensial Supabase".

`python-dotenv` dipakai kalau terpasang dan berkas `.env` ada di root
proyek -- opsional, murni kenyamanan lokal. Di GitHub Actions atau
scheduler lain, isi lewat mekanisme secrets/environment variables
platform tersebut; `.env` tidak wajib ada sama sekali.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # python-dotenv belum terpasang -- tetap aman, lihat docstring
    pass

# ---------------------------------------------------------------------------
# Kredensial Supabase -- HANYA dari variabel lingkungan, tidak ada default
# tertulis di kode. Isi lewat .env (lokal) atau secrets platform (terjadwal).
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


def kredensial_lengkap() -> bool:
    """True kalau SUPABASE_URL dan SUPABASE_KEY berdua sudah terisi."""
    return bool(SUPABASE_URL) and bool(SUPABASE_KEY)


# ---------------------------------------------------------------------------
# Root proyek dan lokasi berkas. Diturunkan dari lokasi berkas ini
# (limina/config.py), bukan cwd, supaya notebook tetap benar dijalankan
# dari folder mana pun.
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
LABELS_DIR = DATA_DIR / "labels"
PATH_TAKSONOMI = LABELS_DIR / "taksonomi_alasan_suspensi.json"

PATH_PANEL = DATA_DIR / "panel.csv"
PATH_RIWAYAT_SKOR = ARTIFACTS_DIR / "riwayat_skor.csv"
PATH_JENDELA = DATA_DIR / "jendela_latih.json"


def path_snapshot(tanggal: str) -> Path:
    return DATA_DIR / f"snapshot_{tanggal}.csv"


# ---------------------------------------------------------------------------
# Nama tabel dan kolom Supabase. Enam tabel, lima yang pertama berisi data
# mentah (keuangan, harga, free float, identitas emiten), yang keenam
# (stock_suspensions) satu-satunya sumber label. Kalau nama tabel/kolom
# Anda berbeda, ganti di sini saja -- modul lain tidak perlu diubah.
# ---------------------------------------------------------------------------
TABEL_QUARTERLY_FINANCIALS = "quarterly_financials"
TABEL_DAILY_TRANSACTION = "daily_transaction"
TABEL_DAILY_FULL_UNIVERSE_CLOSE = "daily_full_universe_close"
TABEL_FREE_FLOAT_SNAPSHOT = "free_float_snapshot"
TABEL_COMPANY_OVERVIEW = "company_overview"  # opsional tapi disarankan
TABEL_SUSPENSI = "stock_suspensions"

# Nama kolom tanggal suspensi di tabel stock_suspensions Anda. Nilai
# bawaan "suspension_date" adalah nama kolom sungguhan pada tabel yang
# sudah dikonfirmasi -- KALAU tabel Anda memakai nama lain, ganti string
# ini saja. Internal proyek (labels.py, raw_ingest.py, panel.csv) selalu
# memakai nama "event_date"; notebook 01 yang mengganti nama kolom sumber
# menjadi "event_date" tepat setelah diunduh, sekali di satu tempat,
# supaya modul lain tidak perlu tahu nama kolom sumber aslinya.
KOLOM_TANGGAL_SUSPENSI = "suspension_date"
KOLOM_ALASAN_SUSPENSI = "reason"

# ---------------------------------------------------------------------------
# Jendela latih/evaluasi BERGULIR, relatif ke tanggal saat notebook
# dijalankan (lihat limina/splits.py). SATU-SATUNYA tempat jendela
# label/horizon peringatan diatur -- labels.bentuk_label_is_event_90d
# (jendela_hari, seberapa jauh ke depan suspensi dicari dari as_of_date)
# dan raw_ingest.OFFSET_AS_OF_DARI_EVENT_HARI (titik tengahnya) sama-sama
# membaca nilai ini, BUKAN hardcode 90 sendiri-sendiri seperti sebelumnya.
# Itu sengaja: splits.batas_label_matang() menahan as_of_date supaya tidak
# lebih baru dari (hari_ini - JENDELA_LABEL_HARI) SUPAYA is_event_90d-nya
# sudah "matang" -- kalau nilai ini diubah tapi jendela pencarian
# ke-depan di labels.py tetap beda sendiri, sebagian baris akan diberi
# label negatif padahal jendela pengamatannya belum genap lewat (label
# tersensor, bukan sekadar tidak presisi). Ganti nilainya DI SINI SAJA;
# nilai wajar ada di rentang 30 (peringatan jangka pendek, lebih cepat
# matang tapi histori harga yang tersedia harus lebih baru) sampai 90
# hari (horizon awal proyek, lihat
# docs/rancangan/AMBANG-peran-model-dan-evaluasi.md bagian 2, Permintaan
# 2) -- di luar rentang itu, tinjau ulang OFFSET_AS_OF_DARI_EVENT_HARI dan
# taksonomi/precision@K yang diasumsikan mengikutinya. Enam potret
# berjarak 30 hari (JARAK_POTRET_HARI) meniru rancangan awal proyek dan
# TIDAK ikut berubah kalau JENDELA_LABEL_HARI diganti.
# ---------------------------------------------------------------------------
JENDELA_LABEL_HARI = 30
JUMLAH_POTRET_EVALUASI = 6
JARAK_POTRET_HARI = 30

# Precision@K -- 20 sesuai rancangan awal (halaman Peringkat menampilkan
# 20 emiten teratas). Turunkan kalau cakupan emiten Anda jauh lebih kecil
# dari ~900.
K_TOP = 20

# Riwayat skor mingguan yang direkonstruksi untuk menghitung selisih waktu
# deteksi (lihat notebook 04).
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
