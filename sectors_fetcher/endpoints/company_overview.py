"""
endpoints/company_overview.py
===============================

Section 1 skema (Identitas dan Label): sumber untuk `sector`, `sub_sector`,
`board`.

Sumber: Sectors API v2 GET /v2/company/report/{symbol}/?sections=overview
Kita HANYA minta section "overview" (bukan semua 8 section) supaya cuma
kena 1 kredit API per panggilan, bukan 8.

Field mentah yang dipakai dari response.overview:
    listing_board  -> dipetakan ke `board`
    sector          -> `sector`
    sub_sector      -> `sub_sector`

(Section overview juga membawa banyak field lain -- market_cap, ESG, tags,
dst -- yang TIDAK kita ambil di sini karena di luar cakupan section 1
skema. Kalau nanti dibutuhkan, tambahkan sendiri di FIELD dict di bawah.)
"""

from __future__ import annotations

from typing import Any

from .. import config
from ..client import SectorsClient, normalize_ticker


def fetch_company_overview(client: SectorsClient, ticker: str) -> dict[str, Any] | None:
    """
    Ambil identitas emiten (sector, sub_sector, board) dari section overview
    Company Report.

    Parameters
    ----------
    client : SectorsClient
    ticker : str
        Kode emiten, misalnya "BBCA".

    Returns
    -------
    dict | None
        {symbol, company_name, sector, sub_sector, board} atau None kalau
        emiten tidak ditemukan (404).
    """
    ticker_norm = normalize_ticker(ticker)
    # path param API tidak butuh suffix .jk, tapi normalize_ticker menambahkannya
    # untuk konsistensi penyimpanan; kirim tanpa suffix di path URL.
    symbol_path = ticker_norm.replace(".JK", "")
    url = config.ENDPOINTS["company_overview"].format(ticker=symbol_path)

    data = client.get(url, params={"sections": "overview"})
    if data is None:
        return None

    overview = data.get("overview", {}) if isinstance(data, dict) else {}
    return {
        "symbol": data.get("symbol", ticker_norm),
        "company_name": data.get("company_name"),
        "sector": overview.get("sector"),
        "sub_sector": overview.get("sub_sector"),
        "board": overview.get("listing_board"),
    }


def fetch_company_overview_bulk(
    client: SectorsClient, tickers: list[str]
) -> list[dict[str, Any]]:
    """Helper: panggil fetch_company_overview untuk banyak ticker sekaligus."""
    results = []
    for ticker in tickers:
        row = fetch_company_overview(client, ticker)
        if row is not None:
            results.append(row)
    return results


if __name__ == "__main__":
    # Contoh pemakaian langsung: python -m sectors_fetcher.endpoints.company_overview
    from pprint import pprint

    c = SectorsClient()
    result = fetch_company_overview(c, "BBCA")
    pprint(result)
