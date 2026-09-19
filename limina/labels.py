"""
labels.py -- Pengelompokan alasan suspensi, pembentukan label
=================================================================

Definisi (AMBANG-konsep-dan-rancangan.md 7.3): A = sukarela/aksi
korporasi (dibuang), B = teknis jangka pendek (dibuang dari label utama,
disimpan sebagai pembanding), C = kepatuhan/distress (label positif).
Hanya C jadi is_event_90d=1. Pemetaan alasan->kategori ada di
data/labels/taksonomi_alasan_suspensi.json, bukan dict tersembunyi di kode.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import config

PATH_TAKSONOMI_DEFAULT = config.PATH_TAKSONOMI

# Divalidasi terhadap 588 baris riwayat suspensi sungguhan (per
# 2026-09-11) -- bukan tebakan, tapi bukan daftar final. Baris seperti
# "Suspend more than 6 month" sengaja TIDAK diklasifikasi (itu STATUS
# lanjutan, bukan alasan awal) -- notebook 02 mencetaknya tiap run untuk
# ditinjau manual. Perbarui data/labels/taksonomi_alasan_suspensi.json
# begitu ada redaksi baru yang belum tercakup.
TAKSONOMI_CONTOH = {
    "A": [
        "permintaan emiten",
        "menunggu keterbukaan informasi",
        "penggabungan usaha",
        "perusahaan tertutup",
        "go private",
        "pembelian kembali saham",
        "buyback",
        "voluntary delisting",
    ],
    "B": [
        "harga kumulatif",  # mencakup "peningkatan" maupun "penurunan harga kumulatif"
        "cooling down",
        "aktivitas pasar tidak wajar",
        "unusual market activity",
    ],
    "C": [
        "laporan keuangan",  # "belum menyampaikan laporan keuangan auditan/interim ..."
        "kelangsungan usaha",  # padanan Indonesia untuk "going concern"
        "keterlambatan pembayaran biaya pencatatan",
        "papan pemantauan khusus",
        "menunda pembayaran",
        "obligasi",
        "belum memenuhi ketentuan",  # pelanggaran ketentuan pencatatan (mis. peraturan I-A V.1.1/V.1.2)
        "sanksi",
        "denda",
    ],
}

KATEGORI_LABEL_POSITIF = "C"


def muat_taksonomi(path: str | Path = PATH_TAKSONOMI_DEFAULT) -> dict[str, list[str]]:
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(TAKSONOMI_CONTOH, indent=2, ensure_ascii=False), encoding="utf-8")
        return TAKSONOMI_CONTOH
    return json.loads(path.read_text(encoding="utf-8"))


def klasifikasi_alasan(alasan_resmi: str, taksonomi: dict[str, list[str]]) -> str | None:
    """Cocokkan alasan resmi ke kategori A/B/C lewat kata kunci. None
    jika tidak cocok manapun -- wajib ditinjau manual, jangan ditebak."""
    if not alasan_resmi:
        return None
    teks = str(alasan_resmi).lower()
    for kategori, kata_kunci_list in taksonomi.items():
        if any(kk.lower() in teks for kk in kata_kunci_list):
            return kategori
    return None


def bentuk_label_is_event_90d(
    df_suspensi: pd.DataFrame,
    df_cakupan: pd.DataFrame,
    *,
    taksonomi: dict[str, list[str]] | None = None,
    kolom_alasan: str = "reason",
    jendela_hari: int = config.JENDELA_LABEL_HARI,
) -> pd.DataFrame:
    """
    Tandai is_event_90d=1 tiap baris df_cakupan (symbol x as_of_date) yang
    punya suspensi kategori C pada symbol sama dalam jendela_hari setelah
    as_of_date. jendela_hari bawaan = config.JENDELA_LABEL_HARI, sumber
    yang sama dipakai splits.batas_label_matang() -- jangan override
    tanpa mengganti keduanya, atau sebagian baris berlabel negatif
    padahal jendelanya belum lewat.

    df_suspensi: kolom symbol, event_date, kolom_alasan.
    df_cakupan: kolom symbol, as_of_date.
    Balikan: df_cakupan + is_event_90d, event_date, event_category.
    """
    taksonomi = taksonomi or muat_taksonomi()

    df_suspensi = df_suspensi.copy()
    df_suspensi["event_category"] = df_suspensi[kolom_alasan].apply(
        lambda a: klasifikasi_alasan(a, taksonomi)
    )
    tak_terklasifikasi = df_suspensi[df_suspensi["event_category"].isna()]
    if len(tak_terklasifikasi) > 0:
        print(
            f"PERINGATAN: {len(tak_terklasifikasi)} alasan suspensi tidak cocok "
            f"kata kunci manapun, wajib ditinjau manual sebelum lanjut."
        )

    df_suspensi["event_date"] = pd.to_datetime(df_suspensi["event_date"])
    hasil = df_cakupan.copy()
    hasil["as_of_date"] = pd.to_datetime(hasil["as_of_date"])
    hasil["is_event_90d"] = 0
    hasil["event_date"] = pd.NaT
    hasil["event_category"] = ""

    for symbol, grup in df_suspensi.groupby("symbol"):
        grup_c = grup[grup["event_category"] == KATEGORI_LABEL_POSITIF]
        if len(grup_c) == 0:
            continue
        mask_symbol = hasil["symbol"] == symbol
        for _, event in grup_c.iterrows():
            batas_awal = event["event_date"] - pd.Timedelta(days=jendela_hari)
            mask_jendela = (hasil["as_of_date"] >= batas_awal) & (
                hasil["as_of_date"] < event["event_date"]
            )
            mask = mask_symbol & mask_jendela
            hasil.loc[mask, "is_event_90d"] = 1
            hasil.loc[mask, "event_date"] = event["event_date"]
            hasil.loc[mask, "event_category"] = KATEGORI_LABEL_POSITIF

    return hasil


__all__ = [
    "TAKSONOMI_CONTOH",
    "KATEGORI_LABEL_POSITIF",
    "muat_taksonomi",
    "klasifikasi_alasan",
    "bentuk_label_is_event_90d",
]
