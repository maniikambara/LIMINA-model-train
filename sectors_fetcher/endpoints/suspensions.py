"""
endpoints/suspensions.py
=========================

Section 1 skema (Identitas dan Label): sumber untuk `event_date`,
`event_category`, dan bahan dasar penentuan `is_event_90d`.

Sumber: Sectors API v2 GET /v2/suspensions/
Field mentah yang dikembalikan API (per baris):
    symbol, event_date, reason, pdf_url

PENTING soal kepemilikan (lihat AMBA Kamus Variabel bagian 9):
    Modul ini HANYA menarik data mentah suspensi (symbol, event_date,
    reason, pdf_url) apa adanya dari API. Modul ini TIDAK melakukan
    klasifikasi taksonomi A/B/C, dan TIDAK menghitung `is_event_90d`.
    Kedua hal itu logika bisnis milik peran Data dan Label, dibangun di atas
    output modul ini (field `reason` mentah), bukan di dalam modul fetch ini.

Endpoint ini paginated (maks `limit=30` per halaman) -- fungsi di bawah
otomatis melahap semua halaman.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .. import config
from ..client import SectorsClient

MAX_PAGE_LIMIT = 30  # batas API untuk endpoint ini


def fetch_suspensions(
    client: SectorsClient,
    symbol: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[dict[str, Any]]:
    """
    Ambil riwayat suspensi saham IDX (historis dan terkini).

    Parameters
    ----------
    client : SectorsClient
    symbol : str | None
        Filter opsional ke satu emiten, misalnya "BBCA". None = semua emiten.
    start, end : date | None
        Filter opsional rentang tanggal `event_date`. `end` tidak boleh
        di masa depan (API mengembalikan 400 kalau dilanggar).

    Returns
    -------
    list[dict]
        Satu dict per kejadian suspensi:
        {symbol, event_date, reason, pdf_url}
    """
    url = config.ENDPOINTS["suspensions"]
    base_params: dict[str, Any] = {}
    if symbol:
        base_params["symbol"] = symbol.strip().upper().replace(".JK", "")
    if start:
        base_params["start"] = start.isoformat()
    if end:
        base_params["end"] = end.isoformat()

    all_records: list[dict[str, Any]] = []
    offset = 0

    while True:
        params = {**base_params, "limit": MAX_PAGE_LIMIT, "offset": offset}
        data = client.get(url, params=params)
        if not data:
            break

        results = data.get("results", []) if isinstance(data, dict) else data
        if not results:
            break

        all_records.extend(results)

        pagination = data.get("pagination") if isinstance(data, dict) else None
        if not pagination or not pagination.get("has_next", False):
            break
        offset = pagination.get("next_offset", offset + MAX_PAGE_LIMIT)

    return all_records


if __name__ == "__main__":
    # Contoh pemakaian langsung: python -m sectors_fetcher.endpoints.suspensions
    from pprint import pprint

    c = SectorsClient()
    result = fetch_suspensions(c)
    print(f"{len(result)} kejadian suspensi diterima. Contoh baris pertama:")
    pprint(result[0] if result else None)
