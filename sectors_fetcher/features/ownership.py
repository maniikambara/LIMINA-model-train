"""
features/ownership.py
=======================

Section 3.4 skema: Kelompok struktur kepemilikan, HANYA untuk skor terkini.

    free_float_rendah = 1 jika free_float di bawah ambang tertentu

PERINGATAN (diwariskan dari section 2.3 skema): free_float hanya tersedia
sebagai snapshot TERKINI. Field ini HANYA boleh dipakai saat menghitung
skor emiten hari ini (as_of_date == hari ini), TIDAK BOLEH dipakai untuk
melatih model dari sampel historis -- itu temporal leakage. Pipeline
pemanggil bertanggung jawab memastikan pembatasan ini (lihat
features/pipeline.py, parameter `sertakan_free_float`).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .. import config


def compute_ownership_features(free_float_row: pd.Series | None) -> dict[str, Any]:
    """
    Hitung free_float_rendah dari SATU baris snapshot free_float_snapshot.

    Parameters
    ----------
    free_float_row : pd.Series | None
        Baris free_float_snapshot untuk symbol yang bersangkutan (snapshot
        TERKINI, bukan historis), atau None kalau tidak ada datanya.

    Returns
    -------
    dict
        {free_float_rendah}. None kalau tidak ada data free_float.
    """
    if free_float_row is None or pd.isna(free_float_row.get("free_float")):
        return {"free_float_rendah": None}

    free_float = float(free_float_row["free_float"])
    # free_float dari API adalah pecahan 0-1 (0.045 = 4.5%); ambang di
    # config disimpan dalam persen (7.5) -- wajib dibagi 100 sebelum
    # dibandingkan, atau hasilnya akan selalu 1 (bug lama di modul ini).
    free_float_rendah = int(free_float < (config.FREE_FLOAT_RENDAH_AMBANG_PERSEN / 100.0))
    return {"free_float_rendah": free_float_rendah}
