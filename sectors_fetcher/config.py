"""
config.py
=========

Satu-satunya tempat untuk menaruh pengaturan Sectors API:
- API key (WAJIB lewat environment variable, jangan hardcode)
- base URL
- path tiap endpoint
- parameter default (ticker list, rentang tanggal, dsb.)

Cara isi API key
----------------
Jangan tulis API key langsung di file ini. Set lewat environment variable:

    export SECTORS_API_KEY="isi-api-key-anda"

lalu jalankan script seperti biasa. Kalau mau simpan di file (misalnya untuk
development lokal), buat file `.env` di folder ini:

    SECTORS_API_KEY=isi-api-key-anda

dan pastikan `.env` masuk `.gitignore` supaya tidak ke-commit.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

# ----------------------------------------------------------------------
# 1. API KEY
# ----------------------------------------------------------------------
# Opsional: load file .env kalau ada, tanpa perlu install python-dotenv.
_ENV_FILE = Path(__file__).parent / ".env"
if _ENV_FILE.exists():
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

SECTORS_API_KEY = os.environ.get("SECTORS_API_KEY", "")


def require_api_key() -> str:
    """Panggil ini di tiap entry point script supaya gagal cepat & jelas kalau key belum diset."""
    if not SECTORS_API_KEY:
        raise RuntimeError(
            "SECTORS_API_KEY belum diset.\n"
            "Jalankan:  export SECTORS_API_KEY=\"isi-api-key-anda\"\n"
            "atau buat file .env di folder sectors_fetcher/ berisi:\n"
            "  SECTORS_API_KEY=isi-api-key-anda"
        )
    return SECTORS_API_KEY


# ----------------------------------------------------------------------
# 1b. SUPABASE (untuk penyimpanan hasil fetch)
# ----------------------------------------------------------------------
# Ambil dari Supabase Dashboard -> Project Settings -> API.
#   SUPABASE_URL      : https://xxxxx.supabase.co
#   SUPABASE_KEY       : gunakan SERVICE ROLE key untuk script backend/batch
#                         (bukan anon key), supaya insert/upsert tidak
#                         diblokir Row Level Security. JANGAN taruh
#                         service role key di kode frontend/publik.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


def require_supabase_credentials() -> tuple[str, str]:
    """Panggil ini sebelum membuat SupabaseStorage supaya gagal cepat & jelas."""
    missing = [
        name
        for name, value in (("SUPABASE_URL", SUPABASE_URL), ("SUPABASE_KEY", SUPABASE_KEY))
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"{', '.join(missing)} belum diset.\n"
            "Jalankan:\n"
            '  export SUPABASE_URL="https://xxxxx.supabase.co"\n'
            '  export SUPABASE_KEY="isi-service-role-key-anda"\n'
            "atau tambahkan ke file .env di folder sectors_fetcher/."
        )
    return SUPABASE_URL, SUPABASE_KEY


# ----------------------------------------------------------------------
# 2. BASE URL & ENDPOINT PATHS
# ----------------------------------------------------------------------
# Catatan: Sectors API v1 sudah dihentikan total sejak 2026-05-12
# (semua /v1/* mengembalikan HTTP 410 Gone). Gunakan v2.
BASE_URL = "https://api.sectors.app/v2"

ENDPOINTS = {
    # 2.1 Company Quarterly Financials
    # -> revenue, earnings, total_equity, total_liabilities, total_assets,
    #    total_debt, operating_cash_flow, free_cash_flow, report_date
    "quarterly_financials": BASE_URL + "/financials/quarterly/{ticker}/",

    # 2.2 Daily Transaction Data (per ticker)
    # -> close, volume, market_cap
    "daily_transaction": BASE_URL + "/daily/{ticker}/",

    # Daily Full-Universe Close (semua ticker IDX, satu tanggal, paginated)
    "daily_full_universe_close": BASE_URL + "/close/",

    # 2.3 Free Float Market Analysis (HANYA nilai terkini, bukan historis)
    "free_float": BASE_URL + "/free-float/",

    # Stock Suspensions -- sumber event_date/reason untuk label is_event_90d
    # (section 1 skema, dimiliki peran Data dan Label)
    "suspensions": BASE_URL + "/suspensions/",

    # Company Overview (section=overview dari Company Report) -- sumber
    # sector, sub_sector, board (section 1 skema)
    "company_overview": BASE_URL + "/company/report/{ticker}/",
}

# Batas rentang tanggal API untuk daily transaction per satu panggilan.
MAX_DAILY_RANGE_DAYS = 90

# ----------------------------------------------------------------------
# 3. PARAMETER DEFAULT (silakan ubah sesuai kebutuhan)
# ----------------------------------------------------------------------
DEFAULT_TICKERS = [
    "UDNG.JK",
    "PACK.JK", "MDIA.JK", "LUCY.JK", "MLPT.JK", "INET.JK", "MINA.JK"
    # # Emiten awal (jangan dihapus)
    # "BBCA", "TLKM", "ASII",
    # # Top Market Gainers on IDX, 7 Days
    # "AMMN", "IMPC", "AADI", "MGLV", "SOHO",
    # # Top Market Losers on IDX, 7 Days (BBCA sudah ada di atas, tidak diulang)
    # "BELI", "SRAJ", "BRPT", "TPIA",
]
DEFAULT_END_DATE = date.today()
DEFAULT_START_DATE = DEFAULT_END_DATE - timedelta(days=90)
DEFAULT_N_QUARTERS = 4

# ----------------------------------------------------------------------
# 4. HTTP CLIENT BEHAVIOUR
# ----------------------------------------------------------------------
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 6
BACKOFF_SECONDS = 2.0
REQUEST_DELAY_SECONDS = 0.5  # jeda antar-request, sopan ke rate limit

# Jeda tambahan khusus untuk endpoint paginated berat (mis. full-universe
# close, ~32 halaman berurutan) supaya tidak kena rate limit 429.
PAGINATION_DELAY_SECONDS = 1.2

# ----------------------------------------------------------------------
# 5. NAMA TABEL SUPABASE (harus cocok dengan sql/schema.sql)
# ----------------------------------------------------------------------
SUPABASE_TABLES = {
    "quarterly_financials": "quarterly_financials",
    "daily_transaction": "daily_transaction",
    "daily_full_universe_close": "daily_full_universe_close",
    "free_float": "free_float_snapshot",
    "suspensions": "stock_suspensions",
    "company_overview": "company_overview",
}

# Ukuran batch untuk upsert (Supabase/PostgREST punya batas payload per request)
SUPABASE_UPSERT_BATCH_SIZE = 500

# ----------------------------------------------------------------------
# 6. PARAMETER PERHITUNGAN INDIKATOR TURUNAN (section 3 skema)
# ----------------------------------------------------------------------
# Ambang-ambang ini adalah ASUMSI AWAL yang bisa/harus disesuaikan bersama
# peran Data dan Model sesuai kebijakan resmi BEI atau hasil kalibrasi.

# Tenggat wajib lapor kuartalan (hari sejak akhir kuartal). BEI mewajibkan
# laporan keuangan interim disampaikan paling lambat ~30 hari (belum
# diaudit) atau ~60 hari (kalau diaudit) setelah periode berakhir; nilai di
# bawah dipakai sebagai ambang tunggal yang disederhanakan.
LAPOR_TENGGAT_HARI = 45

# Batas harga terendah yang diizinkan BEI ("harga Rp50")
HARGA_BATAS_BAWAH = 50

# Ambang revenue dianggap "tanpa pendapatan" (mendekati nol)
REVENUE_MENDEKATI_NOL = 0

# Ambang free_float dianggap rendah (persen)
FREE_FLOAT_RENDAH_AMBANG_PERSEN = 7.5

# Jumlah hari untuk window indikator likuiditas/harga (section 3.3)
WINDOW_HARI_LIKUIDITAS = 90
WINDOW_HARI_VOLUME_PENDEK = 30

# Path output CSV untuk hasil variabel turunan
FEATURES_OUTPUT_CSV = "output/features.csv"