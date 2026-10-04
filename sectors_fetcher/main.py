"""
main.py
=======

Entry point contoh: fetch dari Sectors API (endpoints/) lalu simpan ke
Supabase (storage/). Jalankan dari luar folder `sectors_fetcher/`:

    export SECTORS_API_KEY="isi-api-key-anda"
    export SUPABASE_URL="https://xxxxx.supabase.co"
    export SUPABASE_KEY="isi-service-role-key-anda"
    python -m sectors_fetcher.main

Pastikan sql/schema.sql sudah dijalankan di Supabase SQL Editor sebelum
menjalankan script ini.
"""

from __future__ import annotations

import logging

from . import config
from .client import SectorsClient
from .endpoints.company_overview import fetch_company_overview_bulk
from .endpoints.daily_transaction import fetch_daily_transaction
from .endpoints.free_float import fetch_free_float
from .endpoints.full_universe_close import fetch_full_universe_close
from .endpoints.quarterly_financials import fetch_quarterly_financials
from .endpoints.suspensions import fetch_suspensions
from .storage.company_overview import save_company_overview
from .storage.daily_transaction import save_daily_transaction
from .storage.free_float import save_free_float
from .storage.full_universe_close import save_full_universe_close
from .storage.quarterly_financials import save_quarterly_financials
from .storage.suspensions import save_suspensions
from .storage.supabase_client import SupabaseStorage

logger = logging.getLogger("sectors_fetcher")


def main() -> None:
    api_client = SectorsClient()      # validasi SECTORS_API_KEY
    db = SupabaseStorage()             # validasi SUPABASE_URL / SUPABASE_KEY

    for ticker in config.DEFAULT_TICKERS:
        logger.info("=== %s ===", ticker)

        # 2.1 Quarterly financials
        financials = fetch_quarterly_financials(api_client, ticker)
        n = save_quarterly_financials(db, financials)
        logger.info("  quarterly_financials: %d baris disimpan", n)

        # 2.2 Daily transaction (per ticker)
        daily = fetch_daily_transaction(
            api_client, ticker, config.DEFAULT_START_DATE, config.DEFAULT_END_DATE
        )
        n = save_daily_transaction(db, daily)
        logger.info("  daily_transaction: %d baris disimpan", n)

    # Free float (satu kali saja, snapshot seluruh emiten, bukan per ticker)
    free_float = fetch_free_float(api_client)
    n = save_free_float(db, free_float)
    logger.info("free_float_snapshot: %d baris disimpan", n)

    # Full-universe close pada tanggal bursa terakhir yang tersedia
    universe = fetch_full_universe_close(api_client, as_of=None)
    n = save_full_universe_close(db, universe)
    logger.info("daily_full_universe_close: %d baris disimpan", n)

    # Stock suspensions -- sumber label is_event_90d (peran Data dan Label
    # yang menghitung is_event_90d/event_category dari data mentah ini)
    suspensions = fetch_suspensions(api_client)
    n = save_suspensions(db, suspensions)
    logger.info("stock_suspensions: %d baris disimpan", n)

    # Company overview -- sector, sub_sector, board
    overview = fetch_company_overview_bulk(api_client, config.DEFAULT_TICKERS)
    n = save_company_overview(db, overview)
    logger.info("company_overview: %d baris disimpan", n)

    logger.info("Selesai. Semua data mentah tersimpan di Supabase.")


if __name__ == "__main__":
    main()
