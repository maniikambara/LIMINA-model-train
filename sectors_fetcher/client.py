from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from . import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("sectors_fetcher")


class SectorsAPIError(RuntimeError):
    """Dilempar kalau Sectors API mengembalikan error yang tidak bisa di-retry."""


@dataclass
class SectorsClient:
    """Client tipis untuk memanggil Sectors API v2 dengan retry dan rate-limit sederhana."""

    api_key: str = field(default_factory=config.require_api_key)
    session: requests.Session | None = None

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError(
                "API key kosong. Set environment variable SECTORS_API_KEY "
                "(lihat config.py)."
            )
        self.session = self.session or requests.Session()
        self.session.headers.update({"Authorization": self.api_key})

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """GET request generik dengan retry. Dipakai oleh semua modul endpoint."""
        last_error: Exception | None = None

        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                resp = self.session.get(
                    url, params=params, timeout=config.REQUEST_TIMEOUT_SECONDS
                )
            except requests.RequestException as exc:
                last_error = exc
                logger.warning("Percobaan %d gagal (koneksi): %s", attempt, exc)
                time.sleep(config.BACKOFF_SECONDS * attempt)
                continue

            if resp.status_code == 200:
                time.sleep(config.REQUEST_DELAY_SECONDS)
                return resp.json()

            if resp.status_code == 404:
                logger.warning("404 Not Found: %s params=%s", url, params)
                return None

            if resp.status_code == 410:
                raise SectorsAPIError(
                    f"Endpoint {url} sudah dihentikan (410 Gone). "
                    "Cek migration guide, kemungkinan path v2 berubah."
                )

            if resp.status_code in (401, 403):
                raise SectorsAPIError(
                    f"Autentikasi ditolak ({resp.status_code}) untuk {url}. "
                    "Cek kembali SECTORS_API_KEY di config.py / .env."
                )

            if resp.status_code == 429:
                wait = config.BACKOFF_SECONDS * attempt * 3
                logger.warning("Kena rate limit (429). Menunggu %.1f detik...", wait)
                time.sleep(wait)
                last_error = SectorsAPIError("Rate limited")
                continue

            if resp.status_code >= 500:
                wait = config.BACKOFF_SECONDS * attempt
                logger.warning(
                    "Server error %d dari %s. Retry dalam %.1f detik...",
                    resp.status_code, url, wait,
                )
                time.sleep(wait)
                last_error = SectorsAPIError(f"Server error {resp.status_code}")
                continue

            # 400 dan error lain yang tidak masuk akal untuk di-retry
            raise SectorsAPIError(
                f"Request gagal ({resp.status_code}) untuk {url} "
                f"params={params}: {resp.text[:500]}"
            )

        raise SectorsAPIError(
            f"Gagal setelah {config.MAX_RETRIES} percobaan untuk {url}: {last_error}"
        )


def normalize_ticker(ticker: str) -> str:
    """Sectors API menerima ticker 4 huruf, opsional diakhiri '.jk'."""
    ticker = ticker.strip().upper()
    if not ticker.endswith(".JK"):
        ticker = f"{ticker}.JK"
    return ticker