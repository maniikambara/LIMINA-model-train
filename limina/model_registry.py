"""
model_registry.py -- Penyimpanan model dan penulisan scores.json (orkestrasi)
================================================================================

Modul ini BUKAN duplikat limina/artifacts_io.py. artifacts_io.py membangun
struktur dict sesuai skema dan menulis file JSON secara generik, murni
fungsi. Modul ini adalah lapisan orkestrasi tingkat proyek dipakai
notebook 03 dan 05: menyimpan model yang baru dilatih, memuatnya kembali,
memberi skor ke seluruh pasar dengan model itu, lalu memanggil
artifacts_io.py untuk menulis artifacts/scores.json.

simpan_model_terlatih menulis DUA salinan setiap kali dipanggil:
  - salinan "kanonis" tanpa akhiran tanggal (artifacts/model_kandidat_1.joblib
    dkk.) -- ini yang dibaca layanan penyajian/scoring, SELALU model
    terbaru hasil siklus latih paling akhir.
  - salinan berstempel waktu di artifacts/models/<stempel>/ -- riwayat
    versi model dari tiap siklus latih, supaya kalau satu siklus retraining
    menghasilkan model yang tiba-tiba jauh lebih buruk, ada versi
    sebelumnya untuk dibandingkan atau dikembalikan secara manual.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

from . import config, models
from .artifacts_io import bangun_scores_json, tulis_json


def _paths(artifacts_dir: Path | str | None) -> dict[str, Path]:
    root = Path(artifacts_dir) if artifacts_dir is not None else config.ARTIFACTS_DIR
    return {
        "root": root,
        "model_lr": root / "model_kandidat_1.joblib",
        "scaler": root / "scaler_kandidat_1.joblib",
        "median": root / "median_latih.joblib",
        "model_gb": root / "model_kandidat_2.joblib",
        "riwayat": root / "models",
    }


def simpan_model_terlatih(
    model, scaler, median_latih: pd.Series, *, model_gb=None, artifacts_dir: Path | str | None = None
) -> str:
    """
    Menulis salinan kanonis (dibaca layanan penyajian) DAN satu salinan
    berstempel waktu (riwayat versi). Mengembalikan nama folder stempel
    waktu yang baru ditulis, untuk dicatat di log siklus latih.
    """
    p = _paths(artifacts_dir)
    p["root"].mkdir(parents=True, exist_ok=True)
    joblib.dump(model, p["model_lr"])
    joblib.dump(scaler, p["scaler"])
    joblib.dump(median_latih, p["median"])
    if model_gb is not None:
        joblib.dump(model_gb, p["model_gb"])

    stempel = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    folder_versi = p["riwayat"] / stempel
    folder_versi.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, folder_versi / "model_kandidat_1.joblib")
    joblib.dump(scaler, folder_versi / "scaler_kandidat_1.joblib")
    joblib.dump(median_latih, folder_versi / "median_latih.joblib")
    if model_gb is not None:
        joblib.dump(model_gb, folder_versi / "model_kandidat_2.joblib")
    return stempel


def model_tersedia(artifacts_dir: Path | str | None = None) -> bool:
    """
    True kalau model Kandidat 1 (regresi logistik) kanonis sudah pernah
    disimpan. Dipakai notebook 05 untuk memutuskan antara skor model
    terlatih atau jalur cadangan rule-based (Kandidat 4, tidak perlu
    pelatihan) saat notebook 03 belum pernah berhasil menyelesaikan
    siklus latih -- mis. karena data belum cukup, lihat
    limina/splits.py::saring_data_lengkap.
    """
    return _paths(artifacts_dir)["model_lr"].exists()


def muat_model_terlatih(artifacts_dir: Path | str | None = None):
    p = _paths(artifacts_dir)
    model = joblib.load(p["model_lr"])
    scaler = joblib.load(p["scaler"])
    median_latih = joblib.load(p["median"])
    return model, scaler, median_latih


def hasilkan_scores_json(
    df_seluruh_pasar: pd.DataFrame,
    *,
    jumlah_sampel_positif_latih: int,
    dilatih_pada: str,
    k_top: int = config.K_TOP,
    output_path: str | Path | None = None,
    artifacts_dir: Path | str | None = None,
) -> dict:
    """
    Alur akhir: muat model terlatih, beri skor ke SELURUH pasar pada
    data paling baru (biasanya potret hari ini, bukan potret evaluasi
    yang sengaja ditunda 90 hari), hitung kontribusi tiap emiten, tulis
    artifacts/scores.json. Ini keluaran yang dibaca dashboard/produk --
    beda dari backtest.json yang hanya untuk laporan performa historis.
    """
    model, scaler, median_latih = muat_model_terlatih(artifacts_dir)
    output_path = Path(output_path) if output_path is not None else config.ARTIFACTS_DIR / "scores.json"

    skor_mentah = models.skor_kandidat_1(model, scaler, df_seluruh_pasar, median_latih)
    persentil = skor_mentah.rank(pct=True) * 100

    df_skor = df_seluruh_pasar.copy()
    df_skor["skor"] = skor_mentah
    df_skor["persentil"] = persentil
    # arah_30h/delta_30h HANYA diisi "stabil"/0.0 kalau pemanggil belum
    # mengisinya sendiri. Notebook 05 mengisi nilai sungguhan (dibandingkan
    # terhadap artifacts/riwayat_skor.csv) sebelum memanggil fungsi ini;
    # pemanggil lain (mis. pengujian) yang tidak peduli tren otomatis
    # mendapat nilai netral ini.
    if "arah_30h" not in df_skor.columns:
        df_skor["arah_30h"] = "stabil"
    if "delta_30h" not in df_skor.columns:
        df_skor["delta_30h"] = 0.0

    kontribusi_per_emiten = {
        row["symbol"]: models.kontribusi_indikator(model, scaler, row)
        for _, row in df_seluruh_pasar.iterrows()
    }

    ambang_persentil = 100 * (1 - k_top / len(df_skor)) if len(df_skor) else 0.0
    ambang_nilai = skor_mentah.quantile(ambang_persentil / 100) if len(df_skor) else 0.0

    data = bangun_scores_json(
        df_skor,
        kontribusi_per_emiten,
        jenis_model="regresi_logistik",
        dilatih_pada=dilatih_pada,
        jumlah_sampel_positif_latih=jumlah_sampel_positif_latih,
        ambang_persentil=float(ambang_persentil),
        ambang_nilai=float(ambang_nilai),
    )
    tulis_json(data, output_path)
    return data


__all__ = [
    "simpan_model_terlatih",
    "muat_model_terlatih",
    "model_tersedia",
    "hasilkan_scores_json",
]
