"""
endpoints/full_universe_close.py
==================================

Bagian dari section 2.2 skema (sumber alternatif untuk close/market_cap):
Daily Full-Universe Close -- mengambil harga close SEMUA ticker IDX pada
satu tanggal sekaligus, bukan per ticker. Berguna kalau butuh cross-section
lengkap pasar pada satu `as_of_date`, bukan riwayat satu emiten.

PENTING (dikonfirmasi dari dokumentasi resmi): endpoint ini HANYA
mengembalikan {symbol, date, close} -- TIDAK ADA volume atau market_cap
sama sekali. Kalau butuh volume/market_cap per hari, itu hanya tersedia
lewat endpoint Daily Transaction Data (per-ticker, lihat
endpoints/daily_transaction.py), bukan dari endpoint ini.

Endpoint ini paginated, jadi fungsi ini otomatis melahap semua halaman.
Defaultnya tanggal PALING BARU yang punya data (bukan hari kalender ini) --
kalau hari ini belum ada data closing (misal market belum tutup atau bukan
hari bursa), kirim `date` secara eksplisit ke tanggal bursa terakhir.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any

from .. import config
from ..client import SectorsClient

DEFAULT_PAGE_SIZE = 30  # batas maksimum API untuk endpoint ini


def fetch_full_universe_close(
    client: SectorsClient,
    as_of: date | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> list[dict[str, Any]]:
    """
    Ambil close semua ticker IDX pada satu tanggal.

    Parameters
    ----------
    client : SectorsClient
    as_of : date | None
        Tanggal cross-section yang ingin diambil. None = tanggal bursa
        terakhir yang punya data (default API), BUKAN hari kalender ini --
        aman dipakai kapan saja, termasuk sebelum market tutup atau di
        akhir pekan.
    page_size : int
        Ukuran halaman untuk paginasi (maks 30, sesuai batas API).

    Returns
    -------
    list[dict]
        Satu dict per emiten: {symbol, date, close}. TIDAK ada volume/market_cap.
    """
    url = config.ENDPOINTS["daily_full_universe_close"]
    page_size = min(page_size, DEFAULT_PAGE_SIZE)
    all_records: list[dict[str, Any]] = []
    offset = 0

    while True:
        params: dict[str, Any] = {"limit": page_size, "offset": offset}
        if as_of is not None:
            params["date"] = as_of.isoformat()

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
        offset = pagination.get("next_offset", offset + page_size)

        # Endpoint ini butuh ~32 halaman berurutan untuk universe penuh --
        # beri jeda ekstra antar-halaman supaya tidak kena rate limit 429.
        time.sleep(config.PAGINATION_DELAY_SECONDS)

    return all_records


if __name__ == "__main__":
    # Contoh pemakaian langsung: python -m sectors_fetcher.endpoints.full_universe_close
    from pprint import pprint

    c = SectorsClient()
    # as_of=None -> otomatis pakai tanggal bursa terakhir yang tersedia
    result = fetch_full_universe_close(c, as_of=None)
    print(f"{len(result)} emiten diterima. Contoh baris pertama:")
    pprint(result[0] if result else None)