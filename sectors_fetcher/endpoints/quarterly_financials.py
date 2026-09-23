"""
endpoints/quarterly_financials.py
==================================

Section 2.1 skema: Company Quarterly Financials.

Sumber: endpoint Company Quarterly Financials (Sectors API v2).
Field mentah yang diharapkan per baris (tergantung respons API saat ini):
    revenue, earnings, total_equity, total_liabilities, total_assets,
    total_debt, operating_cash_flow, free_cash_flow, report_date
"""

from __future__ import annotations

from typing import Any

from .. import config
from ..client import SectorsClient, normalize_ticker


def fetch_quarterly_financials(
    client: SectorsClient,
    ticker: str,
    n_quarters: int | None = config.DEFAULT_N_QUARTERS,
) -> list[dict[str, Any]]:
    """
    Ambil data laporan keuangan kuartalan mentah untuk satu ticker.

    Parameters
    ----------
    client : SectorsClient
        Instance client yang sudah terautentikasi.
    ticker : str
        Kode emiten, misalnya "BBCA" (boleh dengan/tanpa suffix .jk).
    n_quarters : int | None
        Jumlah kuartal terakhir yang diambil. None = default API.

    Returns
    -------
    list[dict]
        Satu dict per kuartal, sudah ditambahi field "symbol".
    """
    ticker_norm = normalize_ticker(ticker)
    url = config.ENDPOINTS["quarterly_financials"].format(ticker=ticker_norm)

    params: dict[str, Any] = {}
    if n_quarters is not None:
        params["n_quarters"] = n_quarters

    data = client.get(url, params=params)
    if data is None:
        return []

    # Respons API adalah list langsung: [{symbol, date, revenue, ...}, ...]
    # (bukan dibungkus {"financials": [...]}). Tetap ditangani dict-wrapper
    # sebagai fallback jaga-jaga kalau API berubah format lagi.
    if isinstance(data, dict):
        records = data.get("financials") or data.get("results") or []
    else:
        records = data

    for rec in records:
        rec.setdefault("symbol", ticker_norm)
        # PENTING: field tanggal laporan di response API bernama "date",
        # BUKAN "report_date" (sempat jadi bug -- semua baris ke-skip saat
        # disimpan ke Supabase karena kolom report_date selalu kosong).
        # Normalisasi di sini supaya storage/quarterly_financials.py tetap
        # konsisten memakai nama "report_date".
        if "report_date" not in rec and "date" in rec:
            rec["report_date"] = rec["date"]
    return records


if __name__ == "__main__":
    # Contoh pemakaian langsung: python -m sectors_fetcher.endpoints.quarterly_financials
    from pprint import pprint

    c = SectorsClient()
    result = fetch_quarterly_financials(c, "BBCA")
    print(f"{len(result)} baris diterima. Contoh baris pertama:")
    pprint(result[0] if result else None)
