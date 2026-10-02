"""
sectors_fetcher/storage/
=========================

Lapisan penyimpanan Supabase. SupabaseStorage di sini baru menyediakan
jalur BACA (select_all), cukup untuk LiminaScoringService dan
01_ambil_data.ipynb. Jalur TULIS (upsert_*, untuk sectors_fetcher/main.py
dan fetch-sectors-to-supabase.yml) belum diimplementasikan.
"""

from .supabase_client import SupabaseStorage

__all__ = ["SupabaseStorage"]
