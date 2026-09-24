"""
api/dependencies.py
=====================

Satu instance `AMBAScoringService` dibagi ke seluruh request lewat
`Depends(get_scoring_service)` -- supaya koneksi Supabase dan model
`.joblib` (lazy-loaded di dalam `AMBAScoringService`) tidak dibuat ulang
di tiap request.
"""

from functools import lru_cache

from sectors_fetcher.service import AMBAScoringService
from sectors_fetcher.storage.supabase_client import SupabaseStorage


@lru_cache
def get_scoring_service() -> AMBAScoringService:
    return AMBAScoringService(storage=SupabaseStorage())
