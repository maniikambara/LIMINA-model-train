"""
sectors_fetcher/storage/supabase_client.py
============================================

Wrapper BACA-SAJA di atas supabase-py, dipakai LiminaScoringService.
"""

from __future__ import annotations

from supabase import Client, create_client

from .. import config


class SupabaseStorage:
    """Baca tabel Supabase dengan paginasi otomatis."""

    def __init__(self, url: str | None = None, key: str | None = None):
        resolved_url = url or config.SUPABASE_URL
        resolved_key = key or config.SUPABASE_KEY
        if not resolved_url or not resolved_key:
            raise RuntimeError(
                "SUPABASE_URL/SUPABASE_KEY belum diset.\n"
                'Jalankan:\n'
                '  export SUPABASE_URL="https://xxxxx.supabase.co"\n'
                '  export SUPABASE_KEY="isi-key-anda"\n'
                "atau tambahkan ke file .env di folder sectors_fetcher/."
            )
        self.client: Client = create_client(resolved_url, resolved_key)

    def select_all(self, table: str, page_size: int = 1000) -> list[dict]:
        """Ambil seluruh baris satu tabel, dipaginasi otomatis lewat
        `.range()` supaya tidak kena batas baris default PostgREST."""
        rows: list[dict] = []
        start = 0
        while True:
            resp = (
                self.client.table(table)
                .select("*")
                .range(start, start + page_size - 1)
                .execute()
            )
            batch = resp.data or []
            rows.extend(batch)
            if len(batch) < page_size:
                break
            start += page_size
        return rows
