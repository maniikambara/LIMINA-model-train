"""
endpoints/daily_transaction.py
===============================

Section 2.2 skema: Daily Transaction Data (per ticker).

Sumber: endpoint Daily Transaction Data (Sectors API v2).
Field mentah yang diharapkan per baris: close, volume, market_cap.

Catatan: API membatasi rentang maksimum 90 hari per panggilan
(lihat config.MAX_DAILY_RANGE_DAYS). Fungsi di sini otomatis memecah
rentang tanggal yang lebih panjang menjadi beberapa panggilan berurutan.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable

from .. import config
from ..client import SectorsClient, normalize_ticker


def _chunk_date_range(
    start: date, end: date, max_days: int
) -> Iterable[tuple[date, date]]:
    """Pecah rentang tanggal panjang menjadi potongan <= max_days."""
    current_start = start
    one_day = timedelta(days=1)
    max_span = timedelta(days=max_days)

    while current_start <= end:
        current_end = min(current_start + max_span - one_day, end)
        yield current_start, current_end
        current_start = current_end + one_day


def fetch_daily_transaction(
    client: SectorsClient,
    ticker: str,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    """
    Ambil close, volume, market_cap harian untuk satu ticker.

    Rentang tanggal yang lebih panjang dari MAX_DAILY_RANGE_DAYS akan
    otomatis dipecah menjadi beberapa panggilan API dan digabung.

    Parameters
    ----------
    client : SectorsClient
    ticker : str
        Kode emiten, misalnya "BBCA".
    start_date, end_date : date

    Returns
    -------
    list[dict]
        Satu dict per hari transaksi, sudah ditambahi field "symbol".
    """
    ticker_norm = normalize_ticker(ticker)
    url = config.ENDPOINTS["daily_transaction"].format(ticker=ticker_norm)

    all_records: list[dict[str, Any]] = []
    for chunk_start, chunk_end in _chunk_date_range(
        start_date, end_date, config.MAX_DAILY_RANGE_DAYS
    ):
        params = {
            "start": chunk_start.isoformat(),
            "end": chunk_end.isoformat(),
        }
        data = client.get(url, params=params)
        if data is None:
            continue

        if isinstance(data, dict):
            records = data.get("results") or data.get("data") or []
        else:
            records = data

        for rec in records:
            rec.setdefault("symbol", ticker_norm)
        all_records.extend(records)

    return all_records


if __name__ == "__main__":
    # Contoh pemakaian langsung: python -m sectors_fetcher.endpoints.daily_transaction
    from pprint import pprint

    c = SectorsClient()
    result = fetch_daily_transaction(
        c, "BBCA", config.DEFAULT_START_DATE, config.DEFAULT_END_DATE
    )
    print(f"{len(result)} baris diterima. Contoh baris pertama:")
    pprint(result[0] if result else None)
