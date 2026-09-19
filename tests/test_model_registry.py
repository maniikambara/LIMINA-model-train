"""
test_model_registry.py -- Uji penyimpanan model berversi dan penulisan scores.json
======================================================================================
"""

import json

from limina import model_registry, models
from limina.contracts import KOLOM_FITUR


def _latih_model_kecil(panel_uji_factory):
    panel = panel_uji_factory(n_baris=200, proporsi_positif=0.25)
    X = panel[KOLOM_FITUR]
    y = panel["is_event_90d"]
    model, scaler = models.latih_kandidat_1(X, y)
    median_latih = X.median()
    return model, scaler, median_latih, panel


def test_simpan_dan_muat_model_round_trip(tmp_path, panel_uji_factory):
    model, scaler, median_latih, _ = _latih_model_kecil(panel_uji_factory)

    stempel = model_registry.simpan_model_terlatih(
        model, scaler, median_latih, artifacts_dir=tmp_path
    )

    assert (tmp_path / "model_kandidat_1.joblib").exists()
    assert (tmp_path / "models" / stempel / "model_kandidat_1.joblib").exists()

    model_muat, scaler_muat, median_muat = model_registry.muat_model_terlatih(tmp_path)
    assert median_muat.equals(median_latih)
    # Model yang dimuat ulang menghasilkan skor identik dengan yang asli
    assert model_muat.coef_.tolist() == model.coef_.tolist()


def test_simpan_model_dua_kali_menambah_versi_baru_tanpa_menghapus_kanonis(tmp_path, panel_uji_factory):
    model, scaler, median_latih, _ = _latih_model_kecil(panel_uji_factory)
    stempel_1 = model_registry.simpan_model_terlatih(model, scaler, median_latih, artifacts_dir=tmp_path)
    stempel_2 = model_registry.simpan_model_terlatih(model, scaler, median_latih, artifacts_dir=tmp_path)

    versi_tersimpan = {p.name for p in (tmp_path / "models").iterdir()}
    assert stempel_1 in versi_tersimpan
    assert stempel_2 in versi_tersimpan
    assert (tmp_path / "model_kandidat_1.joblib").exists()


def test_hasilkan_scores_json_menulis_berkas_dengan_skema_yang_benar(tmp_path, panel_uji_factory):
    model, scaler, median_latih, panel = _latih_model_kecil(panel_uji_factory)
    model_registry.simpan_model_terlatih(model, scaler, median_latih, artifacts_dir=tmp_path)

    output_path = tmp_path / "scores.json"
    data = model_registry.hasilkan_scores_json(
        panel.head(30),
        jumlah_sampel_positif_latih=50,
        dilatih_pada="peristiwa sebelum 2026-01-01",
        k_top=5,
        output_path=output_path,
        artifacts_dir=tmp_path,
    )

    assert output_path.exists()
    tertulis = json.loads(output_path.read_text())
    assert tertulis["cakupan"]["total_emiten"] == 30
    assert len(data["emiten"]) == 30
    assert data["model"]["jumlah_sampel_positif_latih"] == 50


def test_model_tersedia_false_sebelum_disimpan(tmp_path):
    assert model_registry.model_tersedia(tmp_path) is False


def test_model_tersedia_true_setelah_disimpan(tmp_path, panel_uji_factory):
    model, scaler, median_latih, _ = _latih_model_kecil(panel_uji_factory)
    assert model_registry.model_tersedia(tmp_path) is False
    model_registry.simpan_model_terlatih(model, scaler, median_latih, artifacts_dir=tmp_path)
    assert model_registry.model_tersedia(tmp_path) is True


def test_simpan_dan_muat_kandidat_5_round_trip(tmp_path, panel_uji_factory):
    panel = panel_uji_factory(n_baris=15, proporsi_positif=0.0)
    X = panel[KOLOM_FITUR]
    model = models.latih_kandidat_5(X)
    median_latih = X.median()

    assert model_registry.model_kandidat_5_tersedia(tmp_path) is False
    stempel = model_registry.simpan_model_kandidat_5(model, median_latih, artifacts_dir=tmp_path)
    assert model_registry.model_kandidat_5_tersedia(tmp_path) is True
    assert (tmp_path / "models" / stempel / "model_kandidat_5.joblib").exists()

    model_muat, median_muat = model_registry.muat_model_kandidat_5(tmp_path)
    assert median_muat.equals(median_latih)
    skor_asli = models.skor_kandidat_5(model, panel, median_latih)
    skor_muat = models.skor_kandidat_5(model_muat, panel, median_muat)
    assert skor_asli.tolist() == skor_muat.tolist()
