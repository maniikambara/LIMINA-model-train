"""
features/compliance.py
========================

Section 3.1 skema: Kelompok kepatuhan pelaporan.

    lapor_jarak_hari  = as_of_date - report_date terakhir, dalam hari
    lapor_terlambat   = 1 jika lapor_jarak_hari melampaui tenggat wajib

Input: DataFrame quarterly_financials untuk SATU symbol (kolom minimal:
`report_date`), diurutkan bebas -- fungsi ini yang mengurutkan.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from .. import config


def compute_compliance_features(
    quarterly_financials: pd.DataFrame,
    as_of_date: date,
) -> dict[str, Any]:
    """
    Hitung lapor_jarak_hari dan lapor_terlambat untuk satu emiten.

    Parameters
    ----------
    quarterly_financials : pd.DataFrame
        Baris quarterly_financials milik SATU symbol, kolom wajib:
        `report_date` (bisa string atau datetime.date).
    as_of_date : date
        Titik potong perhitungan.

    Returns
    -------
    dict
        {lapor_jarak_hari, lapor_terlambat}. Nilai None kalau tidak ada
        data report_date sama sekali (data_complete akan ditandai 0 oleh
        pipeline pemanggil).
    """
    if quarterly_financials.empty or "report_date" not in quarterly_financials:
        return {"lapor_jarak_hari": None, "lapor_terlambat": None}

    dates = pd.to_datetime(quarterly_financials["report_date"], errors="coerce").dropna()
    dates = dates[dates.dt.date <= as_of_date]  # jangan pakai laporan dari masa depan
    if dates.empty:
        return {"lapor_jarak_hari": None, "lapor_terlambat": None}

    last_report_date = dates.max().date()
    lapor_jarak_hari = (as_of_date - last_report_date).days
    lapor_terlambat = int(lapor_jarak_hari > config.LAPOR_TENGGAT_HARI)

    return {
        "lapor_jarak_hari": lapor_jarak_hari,
        "lapor_terlambat": lapor_terlambat,
    }
