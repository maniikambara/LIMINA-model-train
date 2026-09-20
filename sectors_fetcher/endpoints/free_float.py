"""
endpoints/free_float.py
=========================

Section 2.3 skema: Free Float Market Analysis.

Sumber: endpoint Free Float Market Analysis (Sectors API v2).
Field mentah yang diharapkan: free_float (persentase saham publik).

PERINGATAN PEMAKAIAN (langsung dari skema)
-------------------------------------------
`free_float` kemungkinan besar hanya tersedia sebagai nilai TERKINI, bukan
riwayat historis. Karena itu:
  - BOLEH dipakai saat menghitung skor emiten HARI INI.
  - TIDAK BOLEH dipakai saat melatih model dari sampel historis --
    memakainya untuk data lama akan membocorkan informasi masa depan
    ke dalam data masa lalu (temporal leakage).

Fungsi di file ini sengaja TIDAK menerima parameter tanggal historis,
supaya kesalahan pemakaian di atas lebih sulit terjadi secara tidak sengaja.
"""

from __future__ import annotations

from typing import Any

from .. import config
from ..client import SectorsClient


def fetch_free_float(
    client: SectorsClient,
    sub_sector: str | None = None,
) -> list[dict[str, Any]]:
    """
    Ambil free_float TERKINI per emiten (opsional difilter per sub-sektor).

    Parameters
    ----------
    client : SectorsClient
    sub_sector : str | None
        Filter opsional berdasarkan sub-sektor.

    Returns
    -------
    list[dict]
        Snapshot free float hari ini. JANGAN dipakai sebagai fitur historis.
    """
    url = config.ENDPOINTS["free_float"]
    params: dict[str, Any] = {}
    if sub_sector:
        params["sub_sector"] = sub_sector

    data = client.get(url, params=params)
    if data is None:
        return []
    return data.get("results", []) if isinstance(data, dict) else data


def get_free_float_for_ticker(
    client: SectorsClient,
    ticker: str,
    sub_sector: str | None = None,
) -> dict[str, Any] | None:
    """Helper: ambil satu baris free_float terkini untuk ticker tertentu."""
    ticker_upper = ticker.strip().upper()
    for row in fetch_free_float(client, sub_sector=sub_sector):
        symbol = str(row.get("symbol", "")).upper()
        if symbol.startswith(ticker_upper):
            return row
    return None


if __name__ == "__main__":
    # Contoh pemakaian langsung: python -m sectors_fetcher.endpoints.free_float
    from pprint import pprint

    c = SectorsClient()
    result = fetch_free_float(c)
    print(f"{len(result)} emiten diterima. Contoh baris pertama:")
    pprint(result[0] if result else None)
