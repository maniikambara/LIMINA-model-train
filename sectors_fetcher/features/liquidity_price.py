"""
features/liquidity_price.py
=============================

Section 3.3 skema: Kelompok likuiditas dan perilaku harga.

    hari_tanpa_transaksi_90d = jumlah hari volume=0 dalam 90 hari terakhir
    rasio_volume_30_90       = rata2 volume 30 hari / rata2 volume 90 hari
    hari_di_batas_bawah_90d  = jumlah hari close=Rp50 dalam 90 hari terakhir
    turun_dari_puncak_90d    = (close_tertinggi_90h - close_hari_ini) / close_tertinggi_90h
    volatilitas_90d          = simpangan baku imbal hasil harian, 90 hari

Input: DataFrame daily_transaction untuk SATU symbol, kolom minimal:
`date`, `close`, `volume`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from .. import config


def compute_liquidity_price_features(
    daily_transaction: pd.DataFrame,
    as_of_date: date,
) -> dict[str, Any]:
    """
    Hitung indikator likuiditas dan perilaku harga dari riwayat harian
    satu emiten, dalam window `config.WINDOW_HARI_LIKUIDITAS` hari
    terakhir relatif ke `as_of_date`.

    Parameters
    ----------
    daily_transaction : pd.DataFrame
        Baris daily_transaction milik SATU symbol. Kolom wajib: `date`,
        `close`, `volume`.
    as_of_date : date

    Returns
    -------
    dict
        {hari_tanpa_transaksi_90d, rasio_volume_30_90,
         hari_di_batas_bawah_90d, turun_dari_puncak_90d, volatilitas_90d}
        None kalau data tidak cukup untuk field itu.
    """
    empty_result = {
        "hari_tanpa_transaksi_90d": None,
        "rasio_volume_30_90": None,
        "hari_di_batas_bawah_90d": None,
        "turun_dari_puncak_90d": None,
        "volatilitas_90d": None,
    }
    required_cols = {"date", "close", "volume"}
    if daily_transaction.empty or not required_cols.issubset(daily_transaction.columns):
        return empty_result

    df = daily_transaction.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")

    window_start = as_of_date - timedelta(days=config.WINDOW_HARI_LIKUIDITAS)
    window_30_start = as_of_date - timedelta(days=config.WINDOW_HARI_VOLUME_PENDEK)

    df_90 = df[(df["date"].dt.date > window_start) & (df["date"].dt.date <= as_of_date)]
    df_30 = df[(df["date"].dt.date > window_30_start) & (df["date"].dt.date <= as_of_date)]

    if df_90.empty:
        return empty_result

    # hari_tanpa_transaksi_90d
    hari_tanpa_transaksi_90d = int((df_90["volume"].fillna(0) == 0).sum())

    # rasio_volume_30_90
    avg_vol_90 = df_90["volume"].mean()
    avg_vol_30 = df_30["volume"].mean() if not df_30.empty else None
    rasio_volume_30_90 = (
        float(avg_vol_30) / float(avg_vol_90)
        if avg_vol_30 is not None and avg_vol_90 not in (None, 0) and pd.notna(avg_vol_90)
        else None
    )

    # hari_di_batas_bawah_90d
    hari_di_batas_bawah_90d = int((df_90["close"] == config.HARGA_BATAS_BAWAH).sum())

    # turun_dari_puncak_90d
    close_tertinggi = df_90["close"].max()
    close_hari_ini = df_90["close"].iloc[-1] if not df_90.empty else None
    if pd.notna(close_tertinggi) and close_tertinggi != 0 and pd.notna(close_hari_ini):
        turun_dari_puncak_90d = float(
            (close_tertinggi - close_hari_ini) / close_tertinggi
        )
    else:
        turun_dari_puncak_90d = None

    # volatilitas_90d: simpangan baku imbal hasil harian (pct_change)
    returns = df_90["close"].pct_change().dropna()
    volatilitas_90d = float(returns.std()) if len(returns) >= 2 else None

    return {
        "hari_tanpa_transaksi_90d": hari_tanpa_transaksi_90d,
        "rasio_volume_30_90": rasio_volume_30_90,
        "hari_di_batas_bawah_90d": hari_di_batas_bawah_90d,
        "turun_dari_puncak_90d": turun_dari_puncak_90d,
        "volatilitas_90d": volatilitas_90d,
    }
