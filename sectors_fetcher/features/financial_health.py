"""
features/financial_health.py
==============================

Section 3.2 skema: Kelompok kesehatan finansial.

    tanpa_pendapatan     = 1 jika revenue nol/mendekati nol (kuartal terbaru)
    ekuitas_negatif      = 1 jika total_equity < 0 (kuartal terbaru)
    utang_terhadap_aset  = total_liabilities / total_assets (kuartal terbaru)
    ako_negatif_berturut = jumlah kuartal BERTURUT-TURUT (dari yang terbaru
                           mundur ke belakang) operating_cash_flow < 0

Input: DataFrame quarterly_financials untuk SATU symbol.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .. import config


def compute_financial_health_features(
    quarterly_financials: pd.DataFrame,
) -> dict[str, Any]:
    """
    Hitung indikator kesehatan finansial dari riwayat kuartalan satu emiten.

    Parameters
    ----------
    quarterly_financials : pd.DataFrame
        Baris quarterly_financials milik SATU symbol. Kolom yang dipakai:
        `report_date`, `revenue`, `total_equity`, `total_liabilities`,
        `total_assets`, `operating_cash_flow`.

    Returns
    -------
    dict
        {tanpa_pendapatan, ekuitas_negatif, utang_terhadap_aset,
         ako_negatif_berturut}. None kalau data tidak cukup untuk field itu.
    """
    empty_result = {
        "tanpa_pendapatan": None,
        "ekuitas_negatif": None,
        "utang_terhadap_aset": None,
        "ako_negatif_berturut": None,
    }
    if quarterly_financials.empty or "report_date" not in quarterly_financials:
        return empty_result

    df = quarterly_financials.copy()
    df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
    df = df.dropna(subset=["report_date"]).sort_values("report_date")
    if df.empty:
        return empty_result

    latest = df.iloc[-1]

    # tanpa_pendapatan
    revenue = latest.get("revenue")
    tanpa_pendapatan = (
        int(pd.notna(revenue) and revenue <= config.REVENUE_MENDEKATI_NOL)
        if pd.notna(revenue)
        else None
    )

    # ekuitas_negatif
    total_equity = latest.get("total_equity")
    ekuitas_negatif = int(total_equity < 0) if pd.notna(total_equity) else None

    # utang_terhadap_aset
    total_liabilities = latest.get("total_liabilities")
    total_assets = latest.get("total_assets")
    if pd.notna(total_liabilities) and pd.notna(total_assets) and total_assets != 0:
        utang_terhadap_aset = float(total_liabilities) / float(total_assets)
    else:
        utang_terhadap_aset = None

    # ako_negatif_berturut: hitung mundur dari kuartal terbaru
    ako_negatif_berturut = None
    if "operating_cash_flow" in df.columns:
        ocf_series = df["operating_cash_flow"].tolist()
        streak = 0
        for value in reversed(ocf_series):
            if pd.isna(value):
                break
            if value < 0:
                streak += 1
            else:
                break
        ako_negatif_berturut = streak

    return {
        "tanpa_pendapatan": tanpa_pendapatan,
        "ekuitas_negatif": ekuitas_negatif,
        "utang_terhadap_aset": utang_terhadap_aset,
        "ako_negatif_berturut": ako_negatif_berturut,
    }
