"""
artifacts_io.py -- Penulis scores.json dan backtest.json
============================================================

Dua berkas ini adalah kontrak keluaran produk, strukturnya mengikuti
docs/rancangan/AMBANG-peran-model-dan-evaluasi.md bagian 8.

skor TIDAK PERNAH ditulis sebagai probabilitas ke berkas ini. Field yang
dikonsumsi antarmuka adalah persentil dan kategori
(docs/rancangan/AMBA-kamus-variabel.md bagian 4).
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path

import pandas as pd

LABEL_INDIKATOR = {
    "lapor_jarak_hari": "Keterlambatan laporan keuangan",
    "lapor_terlambat": "Status telat lapor",
    "tanpa_pendapatan": "Tanpa pendapatan usaha",
    "ekuitas_negatif": "Ekuitas negatif",
    "utang_terhadap_aset": "Rasio utang terhadap aset",
    "ako_negatif_berturut": "Arus kas operasi negatif berturut-turut",
    "hari_tanpa_transaksi_90d": "Hari tanpa transaksi",
    "rasio_volume_30_90": "Pengeringan volume",
    "hari_di_batas_bawah_90d": "Hari menempel di batas bawah",
    "turun_dari_puncak_90d": "Penurunan dari puncak 90 hari",
    "volatilitas_90d": "Volatilitas harga",
}


def _kategori_dari_persentil(persentil: float) -> str:
    if persentil >= 95:
        return "Sangat Tinggi"
    if persentil >= 80:
        return "Tinggi"
    if persentil >= 50:
        return "Sedang"
    return "Rendah"


def _status_emiten(row: pd.Series) -> str:
    if row.get("data_complete", 1) == 0:
        return "tidak_dapat_dinilai"
    if row.get("already_flagged", 0) == 1:
        return "sudah_ditandai"
    return "dinilai"


def bangun_scores_json(
    df_skor: pd.DataFrame,
    kontribusi_per_emiten: dict[str, dict],
    *,
    jenis_model: str,
    dilatih_pada: str,
    jumlah_sampel_positif_latih: int,
    ambang_persentil: float,
    ambang_nilai: float,
    dibuat_pada: str | None = None,
) -> dict:
    """
    Membangun struktur dict sesuai skema scores.json (bagian 8.1). df_skor
    wajib punya kolom: symbol, sector, board, status, skor, persentil,
    arah_30h, delta_30h, data_terakhir. kontribusi_per_emiten adalah
    {symbol: hasil kontribusi_indikator(...)} dari limina/models.py.
    """
    emiten = []
    status_terhitung = []
    for _, row in df_skor.iterrows():
        kontrib = kontribusi_per_emiten.get(row["symbol"], {})
        status = row.get("status") or _status_emiten(row)
        status_terhitung.append(status)
        indikator_list = [
            {
                "nama": nama,
                "label": LABEL_INDIKATOR.get(nama, nama),
                "nilai_mentah": row.get(nama),
                "kontribusi": kontrib.get(nama),
            }
            for nama in LABEL_INDIKATOR
            if nama in row.index
        ]
        emiten.append(
            {
                "symbol": row["symbol"],
                "nama": row.get("nama", ""),
                "sektor": row.get("sector", ""),
                "papan": row.get("board", ""),
                "status": status,
                "skor": float(row["skor"]),
                "persentil": float(row["persentil"]),
                "kategori": _kategori_dari_persentil(row["persentil"]),
                "arah_30h": row.get("arah_30h", "stabil"),
                "delta_30h": float(row.get("delta_30h", 0.0)),
                "indikator": indikator_list,
                "indikator_dominan": kontrib.get("_indikator_dominan", ""),
                "data_terakhir": row.get("data_terakhir", ""),
            }
        )

    # cakupan dihitung dari status_terhitung, persis nilai yang sama yang
    # sudah dipakai untuk tiap entri di emiten (bukan dibaca ulang dari
    # kolom "status" pada df_skor), supaya kedua angka ini tidak pernah
    # bisa berbeda walau pemanggil tidak mengisi kolom status sendiri dan
    # mengandalkan fallback _status_emiten di atas.
    return {
        "dibuat_pada": dibuat_pada or date.today().isoformat(),
        "cakupan": {
            "total_emiten": len(df_skor),
            "diberi_skor": status_terhitung.count("dinilai"),
            "tidak_dapat_dinilai": status_terhitung.count("tidak_dapat_dinilai"),
            "sudah_ditandai": status_terhitung.count("sudah_ditandai"),
        },
        "model": {
            "jenis": jenis_model,
            "dilatih_pada": dilatih_pada,
            "jumlah_sampel_positif_latih": jumlah_sampel_positif_latih,
        },
        "ambang": {"persentil": ambang_persentil, "nilai": ambang_nilai},
        "emiten": emiten,
    }


def bangun_backtest_json(
    hasil_lintas_potret: pd.DataFrame,
    ringkasan_selisih: dict,
    studi_kasus: list[dict],
    alarm_palsu: list[dict],
    kejadian_terlewat: list[dict],
) -> dict:
    """Membangun struktur dict sesuai skema backtest.json (bagian 8.2)."""
    potret = []
    for tanggal, grup in hasil_lintas_potret.groupby("tanggal_potret"):
        baris_lr = grup[grup["kandidat"] == "regresi_logistik"].iloc[0]
        potret.append(
            {
                "tanggal": tanggal,
                "emiten_dinilai": int(baris_lr.get("jumlah_emiten", 0)),
                "peristiwa_dalam_90_hari": int(baris_lr.get("jumlah_peristiwa", 0)),
                "precision_at_20": float(baris_lr["precision_at_20"]),
                "recall_90h": float(baris_lr["recall_90h"]),
                "auc": float(baris_lr["auc"]),
                "pembanding": {
                    "acak": float(grup[grup["kandidat"] == "acak"]["precision_at_20"].iloc[0]),
                    "aturan_tunggal": float(
                        grup[grup["kandidat"] == "aturan_tunggal"]["precision_at_20"].iloc[0]
                    ),
                    "rule_based": float(
                        grup[grup["kandidat"] == "rule_based"]["precision_at_20"].iloc[0]
                    ),
                },
            }
        )

    return {
        "ringkasan": {
            "jumlah_potret": hasil_lintas_potret["tanggal_potret"].nunique(),
            "jumlah_sampel_positif_latih": ringkasan_selisih.get("jumlah_sampel_positif_latih", 0),
            "jumlah_peristiwa_pada_periode_uji": sum(p["peristiwa_dalam_90_hari"] for p in potret),
            "selisih_waktu_median_hari": ringkasan_selisih.get("median_hari"),
            "selisih_waktu_p25_hari": ringkasan_selisih.get("p25_hari"),
            "selisih_waktu_p75_hari": ringkasan_selisih.get("p75_hari"),
            "kejadian_terlewat": ringkasan_selisih.get("kejadian_terlewat", 0),
            "rata_rata_alarm_palsu_per_potret": (
                len(alarm_palsu) / max(1, hasil_lintas_potret["tanggal_potret"].nunique())
            ),
        },
        "potret": potret,
        "studi_kasus": studi_kasus,
        "alarm_palsu": alarm_palsu,
        "kejadian_terlewat": kejadian_terlewat,
    }


def _bersihkan_nan(obj):
    """
    json.dump menangani float NaN/Infinity secara native -- memancarkan
    token NaN/Infinity/-Infinity yang TIDAK valid menurut standar JSON
    (RFC 8259) SEBELUM sempat memanggil default() -- jadi harus
    dibersihkan di sini dulu, bukan lewat parameter default= saja, atau
    scores.json/backtest.json yang dihasilkan tidak akan bisa dibaca
    JSON.parse() di browser.

    pd.NaT diperiksa lewat identitas (obj is pd.NaT), bukan pd.isna(obj)
    generik: pd.NaT ternyata instance datetime.datetime DAN datetime.date
    (walau bukan instance pd.Timestamp) -- kalau dibiarkan lolos ke
    default() di tulis_json, .isoformat()-nya menghasilkan STRING literal
    "NaT", bukan null.
    """
    if isinstance(obj, dict):
        return {k: _bersihkan_nan(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_bersihkan_nan(v) for v in obj]
    if obj is None or obj is pd.NaT:
        return None
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def tulis_json(data: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    def _default(obj):
        if pd.isna(obj):  # tangkap pd.NaT dkk lebih dulu -- lihat catatan _bersihkan_nan
            return None
        if isinstance(obj, (pd.Timestamp, datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Tidak tahu cara menulis tipe {type(obj)}")

    data_bersih = _bersihkan_nan(data)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data_bersih, f, ensure_ascii=False, indent=2, default=_default, allow_nan=False)


__all__ = [
    "LABEL_INDIKATOR",
    "bangun_scores_json",
    "bangun_backtest_json",
    "tulis_json",
]
