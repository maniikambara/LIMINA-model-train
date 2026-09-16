"""
splits.py -- Pemisahan temporal, dihitung BERGULIR relatif ke hari ini
=========================================================================

LIMINA berjalan sebagai layanan yang dilatih ulang setiap hari/minggu,
bukan submisi dengan tanggal potret tetap. Karena itu, cutoff latih dan
tanggal potret evaluasi TIDAK berupa string tanggal tetap -- keduanya
dihitung ulang setiap kali notebook 02 dijalankan, relatif terhadap
tanggal hari itu, lewat hitung_jendela_bergulir() di bawah.

Aturan yang tetap mengikat, tidak berubah dari desain awal
(docs/rancangan/AMBANG-peran-model-dan-evaluasi.md bagian 4.1):

    Latih : seluruh peristiwa dengan event_date sebelum cutoff_latih
    Uji   : potret evaluasi pada beberapa tanggal SEBELUM cutoff_label,
            dilihat sekali per siklus latih

Satu aturan tambahan yang penting justru karena sistem ini sekarang hidup
dan terus berjalan: as_of_date tidak boleh lebih baru dari
(hari_ini - jendela_label_hari). is_event_90d menengok jendela_label_hari
(config.JENDELA_LABEL_HARI, SATU sumber yang sama dipakai
labels.bentuk_label_is_event_90d) hari KE DEPAN dari as_of_date -- untuk
as_of_date yang lebih baru dari itu, kita sendiri belum tahu apakah
sesuatu akan terjadi dalam jendela itu (datanya belum "matang"/masih
tersensor ke kanan). Memberi label negatif pada baris semacam itu akan
salah, bukan sekadar tidak presisi.

Validasi silang acak (KFold dengan shuffle=True) TIDAK PERNAH dipakai di
proyek ini. Jika ada yang mengusulkannya, tolak dengan alasan: ia
mencampur masa depan ke dalam data latih.
"""

from __future__ import annotations

import pandas as pd

from . import config

JENDELA_LABEL_HARI_DEFAULT = config.JENDELA_LABEL_HARI
JUMLAH_POTRET_DEFAULT = config.JUMLAH_POTRET_EVALUASI
JARAK_POTRET_HARI_DEFAULT = config.JARAK_POTRET_HARI


def batas_label_matang(
    sekarang: str | pd.Timestamp | None = None, jendela_label_hari: int = JENDELA_LABEL_HARI_DEFAULT
) -> pd.Timestamp:
    """
    Tanggal PALING BARU yang boleh dipakai sebagai as_of_date supaya
    is_event_90d-nya sudah "matang" (jendela_label_hari ke depannya sudah
    lewat, jadi labelnya benar-benar sudah bisa diketahui, bukan
    tersensor).
    """
    sekarang = pd.Timestamp(sekarang) if sekarang is not None else pd.Timestamp.now().normalize()
    return sekarang - pd.Timedelta(days=jendela_label_hari)


def hitung_jendela_bergulir(
    sekarang: str | pd.Timestamp | None = None,
    *,
    jendela_label_hari: int = JENDELA_LABEL_HARI_DEFAULT,
    jumlah_potret: int = JUMLAH_POTRET_DEFAULT,
    jarak_potret_hari: int = JARAK_POTRET_HARI_DEFAULT,
) -> tuple[pd.Timestamp, list[str]]:
    """
    Menghitung (cutoff_latih, tanggal_potret) relatif ke `sekarang`
    (default: hari ini). Dipanggil ulang setiap kali notebook 02 jalan,
    sehingga jendela latih/uji otomatis bergeser maju seiring waktu --
    tidak pernah jadi kadaluarsa seperti tanggal tetap.

    tanggal_potret: `jumlah_potret` tanggal berjarak `jarak_potret_hari`
    hari, berakhir tepat di batas_label_matang(sekarang), terurut naik.
    cutoff_latih: tanggal potret PALING AWAL -- seluruh event pada atau
    setelah tanggal ini disisihkan untuk evaluasi, tidak ikut melatih.
    """
    batas = batas_label_matang(sekarang, jendela_label_hari)
    tanggal_potret = [
        batas - pd.Timedelta(days=i * jarak_potret_hari)
        for i in range(jumlah_potret - 1, -1, -1)
    ]
    cutoff_latih = tanggal_potret[0]
    return cutoff_latih, [t.strftime("%Y-%m-%d") for t in tanggal_potret]


def pisahkan_temporal(df: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """
    Mengembalikan hanya bagian data latih: baris tanpa event_date (negatif)
    atau dengan event_date sebelum cutoff. Baris dengan event_date pada
    atau setelah cutoff dikeluarkan dari data latih sepenuhnya, supaya
    tidak ada informasi dari periode uji yang ikut melatih model.
    """
    event_date = pd.to_datetime(df["event_date"])
    mask_negatif = df["is_event_90d"] == 0
    mask_positif_lama = (df["is_event_90d"] == 1) & (event_date < cutoff)
    return df[mask_negatif | mask_positif_lama].reset_index(drop=True)


def saring_data_lengkap(
    df: pd.DataFrame, *, minimum_baris: int = 20, minimum_positif: int = 2
) -> pd.DataFrame:
    """
    Menyaring baris dengan data_complete == 1 saja, sebelum dipakai
    melatih model. Baris data_complete == 0 tidak berguna dilatih --
    seluruh KOLOM_FITUR-nya NaN, diisi median hanya saat SCORING (lihat
    limina/models.py), bukan nilai yang benar-benar terukur untuk baris
    itu; melatih model dari baris semacam ini sama saja melatihnya dari
    nilai yang sama berulang-ulang, tidak menambah informasi apa pun.

    Melempar RuntimeError dengan pesan yang menjelaskan kemungkinan
    penyebab (bukan traceback sklearn yang membingungkan soal "Input X
    contains NaN") kalau baris yang tersisa setelah disaring terlalu
    sedikit untuk dilatih, atau kelas positifnya hilang.
    """
    sebelum = len(df)
    df_lengkap = df[df["data_complete"] == 1].reset_index(drop=True)
    dibuang = sebelum - len(df_lengkap)
    print(
        f"Data lengkap: {len(df_lengkap)} dari {sebelum} baris "
        f"({dibuang} dibuang karena data_complete=0)"
    )

    positif = int(df_lengkap["is_event_90d"].sum()) if len(df_lengkap) else 0
    if len(df_lengkap) < minimum_baris or positif < minimum_positif:
        raise RuntimeError(
            f"Data latih yang lengkap (data_complete == 1) terlalu sedikit untuk "
            f"dilatih: {len(df_lengkap)} baris, {positif} positif, setelah "
            f"membuang baris yang tidak lengkap.\n\n"
            f"Dua penyebab paling umum, keduanya bisa diperiksa lewat cetakan "
            f"raw_ingest.diagnosa_cakupan_mentah di notebook 02:\n"
            f"  1. Riwayat quarterly_financials/daily_transaction di Supabase "
            f"Anda belum cukup panjang untuk titik potong yang dibutuhkan -- "
            f"bandingkan report_date_min/max dan harga_date_min/max dengan "
            f"tanggal potret yang dipakai siklus ini.\n"
            f"  2. Format symbol tidak cocok antar tabel (mis. \"BBCA.JK\" di "
            f"satu tabel, \"BBCA\" di tabel lain) -- bandingkan "
            f"contoh_symbol_universe, contoh_symbol_quarterly_financials, dan "
            f"contoh_symbol_harga pada cetakan yang sama; kalau formatnya "
            f"berbeda, seragamkan sebelum tabel diunduh (atau tambahkan "
            f"langkah normalisasi di notebook 01, seperti "
            f"limina/supabase_io.py::normalisasi_tabel_suspensi menyeragamkan "
            f"tabel suspensi)."
        )
    return df_lengkap


def validasi_tidak_ada_tumpang_tindih(
    train_data: pd.DataFrame, snapshot_dict: dict[str, pd.DataFrame]
) -> list[str]:
    """
    Pemeriksaan tambahan: symbol yang event-nya dipakai sebagai label
    positif di data latih semestinya tidak juga muncul sebagai kasus
    positif dengan event_date yang sama di salah satu potret uji.
    Bukan pengganti pemeriksaan kebocoran temporal di leakage.py, hanya
    lapisan sanity-check tambahan yang murah untuk dijalankan.
    """
    masalah: list[str] = []
    if "symbol" not in train_data.columns or "event_date" not in train_data.columns:
        return masalah

    event_latih = set(
        zip(
            train_data.loc[train_data["is_event_90d"] == 1, "symbol"],
            pd.to_datetime(train_data.loc[train_data["is_event_90d"] == 1, "event_date"]),
        )
    )
    for tanggal, snap in snapshot_dict.items():
        if "symbol" not in snap.columns or "event_date" not in snap.columns:
            continue
        event_uji = set(
            zip(
                snap.loc[snap["is_event_90d"] == 1, "symbol"],
                pd.to_datetime(snap.loc[snap["is_event_90d"] == 1, "event_date"]),
            )
        )
        tumpang_tindih = event_latih & event_uji
        if tumpang_tindih:
            masalah.append(
                f"Potret {tanggal} punya {len(tumpang_tindih)} pasangan "
                f"(symbol, event_date) yang juga dipakai sebagai label latih"
            )
    return masalah


def muat_semua_potret(loader, tanggal_list: list[str]) -> dict[str, pd.DataFrame]:
    """
    Memanggil `loader(tanggal)` untuk tiap tanggal pada tanggal_list dan
    mengembalikan dict {tanggal: DataFrame}. `loader` biasanya
    `raw_ingest.bangun_snapshot_pasar` dibungkus lambda.
    """
    return {tanggal: loader(tanggal) for tanggal in tanggal_list}


__all__ = [
    "JENDELA_LABEL_HARI_DEFAULT",
    "JUMLAH_POTRET_DEFAULT",
    "JARAK_POTRET_HARI_DEFAULT",
    "batas_label_matang",
    "hitung_jendela_bergulir",
    "pisahkan_temporal",
    "saring_data_lengkap",
    "validasi_tidak_ada_tumpang_tindih",
    "muat_semua_potret",
]
