"""
sectors_fetcher/storage/
=========================

Lapisan penyimpanan Supabase. Ditambahkan supaya
`AMBAScoringService._default_storage()` (di `sectors_fetcher/service.py`)
dan `sectors_fetcher/main.py` bisa jalan -- keduanya sebelumnya mengimpor
`.storage.supabase_client.SupabaseStorage`, yang belum ada di checkout
proyek ini (lihat `docs/README-pipeline-random-forest.md`, bagian
Keterbatasan).

`SupabaseStorage` di sini baru menyediakan jalur BACA (`select_all`),
yang cukup untuk `AMBAScoringService` (dipakai FastAPI, lihat
`docs/PANDUAN-FASTAPI.md`) dan `preprocessing/notebook/01_ambil_data.ipynb`.
Jalur TULIS (`upsert_*`, dipanggil `sectors_fetcher/main.py` untuk
`fetch-sectors-to-supabase.yml`) BELUM diimplementasikan di sini --
tambahkan method `upsert_batch()`/sejenisnya kalau workflow itu mau
diaktifkan.
"""

from .supabase_client import SupabaseStorage

__all__ = ["SupabaseStorage"]
