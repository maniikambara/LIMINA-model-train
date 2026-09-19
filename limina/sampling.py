"""
sampling.py -- Pembentukan sampel pembanding
================================================

Aturan (AMBANG-konsep-dan-rancangan.md 7.6): tiap sampel positif
dipasangkan 3 sampel negatif dari jendela waktu sama (kondisi pasar
setara), papan pencatatan sebanding, dan tidak mengalami peristiwa
kategori C dalam 180 hari setelah titik potongnya. Negatif TIDAK BOLEH
diambil hanya dari emiten yang masih tercatat hari ini (survivorship bias).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RASIO_NEGATIF_PER_POSITIF = 3
JENDELA_WAKTU_SETARA_HARI = 30
JENDELA_AMAN_HARI = 180


def cari_kandidat_negatif(
    df_cakupan: pd.DataFrame,
    df_suspensi_c: pd.DataFrame,
    baris_positif: pd.Series,
    *,
    jendela_waktu_hari: int = JENDELA_WAKTU_SETARA_HARI,
    jendela_aman_hari: int = JENDELA_AMAN_HARI,
) -> pd.DataFrame:
    """
    Kandidat sampel negatif untuk satu baris positif.

    df_cakupan: seluruh (symbol, as_of_date), TERMASUK emiten delisting
        (hindari survivorship bias). df_suspensi_c: seluruh peristiwa
        kategori C, untuk memastikan kandidat benar aman. baris_positif:
        acuan jendela waktu dan papan pencatatan.
    """
    as_of = pd.Timestamp(baris_positif["as_of_date"])
    board = baris_positif["board"]

    batas_bawah = as_of - pd.Timedelta(days=jendela_waktu_hari)
    batas_atas = as_of + pd.Timedelta(days=jendela_waktu_hari)

    kandidat = df_cakupan[
        (df_cakupan["board"] == board)
        & (pd.to_datetime(df_cakupan["as_of_date"]) >= batas_bawah)
        & (pd.to_datetime(df_cakupan["as_of_date"]) <= batas_atas)
        & (df_cakupan["symbol"] != baris_positif["symbol"])
    ].copy()

    if len(kandidat) == 0:
        return kandidat

    symbol_bermasalah = set()
    for _, event in df_suspensi_c.iterrows():
        event_date = pd.Timestamp(event["event_date"])
        mask_dekat_waktu = (
            kandidat["symbol"] == event["symbol"]
        ) & (
            (pd.to_datetime(kandidat["as_of_date"]) - event_date).abs()
            <= pd.Timedelta(days=jendela_aman_hari)
        )
        if mask_dekat_waktu.any():
            symbol_bermasalah.add(event["symbol"])

    kandidat = kandidat[~kandidat["symbol"].isin(symbol_bermasalah)]
    return kandidat


def bentuk_sampel_pembanding(
    df_positif: pd.DataFrame,
    df_cakupan: pd.DataFrame,
    df_suspensi_c: pd.DataFrame,
    *,
    rasio: int = RASIO_NEGATIF_PER_POSITIF,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Untuk tiap baris df_positif, cari `rasio` sampel negatif yang
    memenuhi syarat, gabungkan jadi sampel latih berimbang (1:`rasio`).
    Baris yang gagal dapat cukup kandidat dicatat dan dilaporkan, tidak
    dipaksakan dengan kandidat yang tidak memenuhi syarat.
    """
    rng = np.random.default_rng(seed)
    semua_negatif = []
    symbol_positif_kurang_kandidat = []

    for _, baris in df_positif.iterrows():
        kandidat = cari_kandidat_negatif(df_cakupan, df_suspensi_c, baris)
        if len(kandidat) < rasio:
            symbol_positif_kurang_kandidat.append(baris["symbol"])
        n_ambil = min(rasio, len(kandidat))
        if n_ambil > 0:
            terpilih = kandidat.sample(n=n_ambil, random_state=rng.integers(0, 1_000_000))
            semua_negatif.append(terpilih)

    if symbol_positif_kurang_kandidat:
        print(
            f"PERINGATAN: {len(symbol_positif_kurang_kandidat)} sampel positif "
            f"tidak mendapat cukup kandidat negatif (kurang dari rasio {rasio}): "
            f"{symbol_positif_kurang_kandidat}"
        )

    df_negatif = pd.concat(semua_negatif, ignore_index=True) if semua_negatif else df_cakupan.iloc[0:0]
    df_negatif = df_negatif.copy()
    df_negatif["is_event_90d"] = 0
    df_negatif["event_date"] = pd.NaT
    df_negatif["event_category"] = ""

    return pd.concat([df_positif, df_negatif], ignore_index=True)


__all__ = [
    "RASIO_NEGATIF_PER_POSITIF",
    "JENDELA_WAKTU_SETARA_HARI",
    "JENDELA_AMAN_HARI",
    "cari_kandidat_negatif",
    "bentuk_sampel_pembanding",
]
