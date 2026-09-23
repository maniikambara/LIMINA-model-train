"""
features/pipeline.py
======================

Entry point untuk menghitung SEMUA variabel turunan (section 3 skema) per
emiten pada satu `as_of_date`, lalu menyimpan hasilnya ke CSV (bukan ke
Supabase -- sesuai permintaan, output variabel turunan disimpan ke file
CSV dulu).

Alur:
    1. Baca data mentah yang SUDAH tersimpan di Supabase (quarterly_financials,
       daily_transaction, free_float_snapshot, company_overview) lewat
       storage/supabase_client.py -- TIDAK memanggil Sectors API lagi.
    2. Untuk tiap symbol, panggil compute_* dari tiap modul features/*.py.
    3. Gabungkan jadi satu baris per symbol: identitas + indikator turunan.
    4. Tulis ke CSV dengan pandas.

Jalankan:
    export SUPABASE_URL="https://xxxxx.supabase.co"
    export SUPABASE_KEY="isi-service-role-key-anda"
    python -m sectors_fetcher.features.pipeline
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from .. import config
from ..storage.supabase_client import SupabaseStorage
from .compliance import compute_compliance_features
from .financial_health import compute_financial_health_features
from .liquidity_price import compute_liquidity_price_features
from .ownership import compute_ownership_features

logger = logging.getLogger("sectors_fetcher")


def _load_table_as_df(storage: SupabaseStorage, table: str) -> pd.DataFrame:
    rows = storage.select_all(table)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def build_features_for_symbol(
    symbol: str,
    as_of_date: date,
    quarterly_financials_all: pd.DataFrame,
    daily_transaction_all: pd.DataFrame,
    free_float_all: pd.DataFrame,
    company_overview_all: pd.DataFrame,
    sertakan_free_float: bool = True,
) -> dict[str, Any]:
    """
    Bangun satu baris lengkap (identitas + variabel turunan) untuk satu
    symbol pada satu as_of_date.

    Parameters
    ----------
    sertakan_free_float : bool
        Set False kalau sedang membangun sampel HISTORIS untuk training --
        free_float TIDAK BOLEH dipakai untuk data lama (lihat
        features/ownership.py dan section 2.3 skema). Default True karena
        pipeline ini defaultnya menghitung skor HARI INI.
    """
    qf = quarterly_financials_all[quarterly_financials_all["symbol"] == symbol]
    dt = daily_transaction_all[daily_transaction_all["symbol"] == symbol]
    ff = free_float_all[free_float_all["symbol"] == symbol]
    ov = company_overview_all[company_overview_all["symbol"] == symbol]

    row: dict[str, Any] = {
        "symbol": symbol,
        "as_of_date": as_of_date.isoformat(),
        "sector": ov["sector"].iloc[0] if not ov.empty else None,
        "sub_sector": ov["sub_sector"].iloc[0] if not ov.empty else None,
        "board": ov["board"].iloc[0] if not ov.empty else None,
    }

    row.update(compute_compliance_features(qf, as_of_date))
    row.update(compute_financial_health_features(qf))
    row.update(compute_liquidity_price_features(dt, as_of_date))

    if sertakan_free_float and not ff.empty:
        # ambil snapshot free_float TERBARU untuk symbol ini
        ff_sorted = ff.sort_values("snapshot_date")
        row.update(compute_ownership_features(ff_sorted.iloc[-1]))
    else:
        row.update({"free_float_rendah": None})

    # data_complete: 1 kalau semua indikator inti berhasil dihitung (tidak None)
    inti = [
        "lapor_jarak_hari", "utang_terhadap_aset",
        "hari_tanpa_transaksi_90d", "volatilitas_90d",
    ]
    row["data_complete"] = int(all(row.get(k) is not None for k in inti))

    return row


def run_pipeline(
    tickers: list[str] | None = None,
    as_of_date: date | None = None,
    output_csv: str | None = None,
) -> pd.DataFrame:
    """
    Jalankan pipeline penuh: baca dari Supabase, hitung indikator, tulis CSV.

    Parameters
    ----------
    tickers : list[str] | None
        Default config.DEFAULT_TICKERS.
    as_of_date : date | None
        Default hari ini.
    output_csv : str | None
        Path file output. Default config.FEATURES_OUTPUT_CSV.

    Returns
    -------
    pd.DataFrame
        DataFrame hasil (juga sudah ditulis ke CSV).
    """
    tickers = tickers or config.DEFAULT_TICKERS
    as_of_date = as_of_date or date.today()
    output_csv = output_csv or config.FEATURES_OUTPUT_CSV

    storage = SupabaseStorage()

    logger.info("Membaca data mentah dari Supabase...")
    quarterly_financials_all = _load_table_as_df(
        storage, config.SUPABASE_TABLES["quarterly_financials"]
    )
    daily_transaction_all = _load_table_as_df(
        storage, config.SUPABASE_TABLES["daily_transaction"]
    )
    free_float_all = _load_table_as_df(storage, config.SUPABASE_TABLES["free_float"])
    company_overview_all = _load_table_as_df(
        storage, config.SUPABASE_TABLES["company_overview"]
    )

    # Ticker disimpan dengan suffix .JK di tabel -- samakan format sebelum filter
    tickers_norm = [
        t.strip().upper() if t.strip().upper().endswith(".JK") else f"{t.strip().upper()}.JK"
        for t in tickers
    ]

    rows = []
    for symbol in tickers_norm:
        logger.info("Menghitung indikator untuk %s...", symbol)
        row = build_features_for_symbol(
            symbol,
            as_of_date,
            quarterly_financials_all,
            daily_transaction_all,
            free_float_all,
            company_overview_all,
        )
        rows.append(row)

    df = pd.DataFrame(rows)

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info("Selesai. %d baris ditulis ke %s", len(df), output_path)

    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    result_df = run_pipeline()
    print(result_df.to_string(index=False))
