"""Satu instance LiminaScoringService dibagi ke semua request."""

from functools import lru_cache

from sectors_fetcher.service import LiminaScoringService
from sectors_fetcher.storage.supabase_client import SupabaseStorage


@lru_cache
def get_scoring_service() -> LiminaScoringService:
    return LiminaScoringService(storage=SupabaseStorage())
