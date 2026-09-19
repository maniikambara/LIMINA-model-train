"""
test_artifacts_io.py -- Uji penulis JSON, terutama pembersihan NaN/Infinity
==============================================================================

Ditambahkan setelah insiden nyata: scores.json yang dihasilkan untuk
emiten data_complete=0 (skor/persentil NaN) sempat memuat token literal
NaN, yang TIDAK valid menurut standar JSON (RFC 8259) dan gagal dibaca
JSON.parse() di browser -- json.dump Python menangani float NaN secara
native SEBELUM sempat memanggil parameter default=, jadi harus
dibersihkan lebih dulu.
"""

import json
import math

import pandas as pd

from limina import artifacts_io


def test_tulis_json_mengubah_nan_jadi_null(tmp_path):
    data = {"skor": float("nan"), "daftar": [1.0, float("nan"), 3.0]}
    path = tmp_path / "keluaran.json"
    artifacts_io.tulis_json(data, path)

    mentah = path.read_text(encoding="utf-8")
    assert "NaN" not in mentah  # token literal NaN tidak valid JSON

    dibaca_ulang = json.loads(mentah)  # akan melempar kalau bukan JSON valid
    assert dibaca_ulang["skor"] is None
    assert dibaca_ulang["daftar"] == [1.0, None, 3.0]


def test_tulis_json_mengubah_infinity_jadi_null(tmp_path):
    data = {"a": float("inf"), "b": float("-inf")}
    path = tmp_path / "keluaran.json"
    artifacts_io.tulis_json(data, path)

    mentah = path.read_text(encoding="utf-8")
    assert "Infinity" not in mentah

    dibaca_ulang = json.loads(mentah)
    assert dibaca_ulang == {"a": None, "b": None}


def test_tulis_json_nan_di_dalam_struktur_bersarang(tmp_path):
    data = {"emiten": [{"symbol": "AAAA", "skor": float("nan")}, {"symbol": "BBBB", "skor": 1.5}]}
    path = tmp_path / "keluaran.json"
    artifacts_io.tulis_json(data, path)

    dibaca_ulang = json.loads(path.read_text(encoding="utf-8"))
    assert dibaca_ulang["emiten"][0]["skor"] is None
    assert dibaca_ulang["emiten"][1]["skor"] == 1.5


def test_tulis_json_pd_nat_tetap_jadi_null(tmp_path):
    data = {"tanggal": pd.NaT}
    path = tmp_path / "keluaran.json"
    artifacts_io.tulis_json(data, path)
    dibaca_ulang = json.loads(path.read_text(encoding="utf-8"))
    assert dibaca_ulang["tanggal"] is None


def test_tulis_json_timestamp_tetap_isoformat(tmp_path):
    data = {"tanggal": pd.Timestamp("2026-01-15")}
    path = tmp_path / "keluaran.json"
    artifacts_io.tulis_json(data, path)
    dibaca_ulang = json.loads(path.read_text(encoding="utf-8"))
    assert dibaca_ulang["tanggal"] == "2026-01-15T00:00:00"


def test_bangun_scores_json_untuk_emiten_tidak_lengkap_hasil_tetap_json_valid(tmp_path):
    # Reproduksi insiden: emiten data_complete=0 -> skor/persentil NaN
    # dari raw_ingest/model, langsung ke bangun_scores_json -> tulis_json.
    df_skor = pd.DataFrame({
        "symbol": ["AAAA"],
        "sector": [""],
        "board": ["Main"],
        "status": ["tidak_dapat_dinilai"],
        "skor": [float("nan")],
        "persentil": [float("nan")],
        "data_complete": [0],
    })
    data = artifacts_io.bangun_scores_json(
        df_skor, {}, jenis_model="rule_based", dilatih_pada="-",
        jumlah_sampel_positif_latih=0, ambang_persentil=95.0, ambang_nilai=1.0,
    )
    path = tmp_path / "scores.json"
    artifacts_io.tulis_json(data, path)

    mentah = path.read_text(encoding="utf-8")
    assert "NaN" not in mentah
    dibaca_ulang = json.loads(mentah)
    assert dibaca_ulang["emiten"][0]["skor"] is None
