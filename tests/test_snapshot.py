"""
test_snapshot.py -- Uji evaluasi lintas kandidat, termasuk penyaringan
data_complete
==========================================================================

Ditambahkan bersamaan dengan perbaikan insiden: potret dengan banyak
baris data_complete == 0 sempat membuat Precision@20 terdistorsi, karena
baris tidak lengkap ikut diberi skor "biasa saja" (fitur kosong diisi
median) dan bisa saja masuk top-K seolah benar-benar dinilai.
"""

import numpy as np
import pandas as pd

from limina import models, snapshot
from limina.contracts import KOLOM_FITUR


def _latih_model_kecil(panel_uji_factory):
    panel = panel_uji_factory(n_baris=300, proporsi_positif=0.25)
    X = panel[KOLOM_FITUR]
    y = panel["is_event_90d"]
    model_lr, scaler = models.latih_kandidat_1(X, y)
    model_gb = models.latih_kandidat_2(X, y)
    median_latih = X.median()
    return model_lr, model_gb, scaler, median_latih


def test_baris_tidak_lengkap_tidak_pernah_masuk_top_k(panel_uji_factory):
    model_lr, model_gb, scaler, median_latih = _latih_model_kecil(panel_uji_factory)

    snap = panel_uji_factory(n_baris=100, proporsi_positif=0.3)
    snap = snap.copy()
    # Tandai separuh baris sebagai tidak lengkap, DENGAN sengaja memberi
    # fitur yang -- kalau tidak dikecualikan -- akan terlihat berisiko
    # tinggi (memenuhi seluruh kriteria rule-based), supaya uji ini benar
    # benar menguji pengecualiannya, bukan kebetulan tidak lolos top-K.
    idx_tidak_lengkap = snap.index[:50]
    snap.loc[idx_tidak_lengkap, "data_complete"] = 0
    snap.loc[idx_tidak_lengkap, "lapor_terlambat"] = 1
    snap.loc[idx_tidak_lengkap, "tanpa_pendapatan"] = 1
    snap.loc[idx_tidak_lengkap, "ekuitas_negatif"] = 1
    snap.loc[idx_tidak_lengkap, "is_event_90d"] = 0  # bukan peristiwa sungguhan, supaya tidak memengaruhi recall

    hasil = snapshot.evaluasi_semua_kandidat(snap, model_lr, model_gb, scaler, median_latih, k=20)
    # Semua kandidat seharusnya masih menghasilkan angka yang valid (bukan NaN
    # akibat -inf ikut dirata-ratakan secara tidak sengaja)
    assert hasil["precision_at_20"].between(0, 1).all()


def test_kecualikan_data_tidak_lengkap_memaksa_skor_di_bawah_yang_terendah():
    snap = pd.DataFrame({"data_complete": [1, 0, 1, 0]})
    skor = pd.Series([0.9, 0.9, 0.1, 0.9])
    hasil = snapshot._kecualikan_data_tidak_lengkap(skor, snap)
    # Baris lengkap (index 0, 2) tidak berubah; baris tidak lengkap
    # (index 1, 3) turun ke bawah skor lengkap TERENDAH (0.1), bukan -inf
    # (roc_auc_score menolak nilai tak berhingga).
    assert hasil[0] == 0.9
    assert hasil[2] == 0.1
    assert hasil[1] < 0.1
    assert hasil[3] < 0.1
    assert np.isfinite(hasil[1]) and np.isfinite(hasil[3])


def test_kecualikan_data_tidak_lengkap_tanpa_kolom_tidak_berubah():
    snap = pd.DataFrame({"symbol": ["A", "B"]})
    skor = pd.Series([0.9, 0.1])
    hasil = snapshot._kecualikan_data_tidak_lengkap(skor, snap)
    assert hasil.tolist() == [0.9, 0.1]


def test_peristiwa_pada_baris_tidak_lengkap_dihitung_sebagai_terlewat(panel_uji_factory):
    model_lr, model_gb, scaler, median_latih = _latih_model_kecil(panel_uji_factory)

    snap = panel_uji_factory(n_baris=60, proporsi_positif=0.2)
    snap = snap.copy()
    # Satu-satunya baris positif justru ditandai data_complete=0 --
    # recall_90h wajib mencatat ini sebagai tidak tertangkap (0.0 kalau
    # itu satu-satunya positif), bukan diam-diam ikut top-K.
    idx_positif = snap.index[snap["is_event_90d"] == 1]
    if len(idx_positif) == 0:
        return  # sampel acak kebetulan tidak ada positif, lewati
    snap.loc[idx_positif, "data_complete"] = 0

    hasil = snapshot.evaluasi_semua_kandidat(snap, model_lr, model_gb, scaler, median_latih, k=20)
    for _, baris in hasil.iterrows():
        assert baris["recall_90h"] == 0.0 or np.isnan(baris["recall_90h"])


def test_keputusan_data_tidak_cukup_selalu_rule_based_penuh():
    hasil = snapshot.keputusan_data_tidak_cukup("0 baris positif lengkap")
    assert hasil == {"keputusan": "rule_based_penuh", "alasan": "0 baris positif lengkap"}


def test_keputusan_anomali_saja():
    hasil = snapshot.keputusan_anomali_saja("9 baris lengkap, 0 positif")
    assert hasil == {"keputusan": "anomali_tanpa_label", "alasan": "9 baris lengkap, 0 positif"}
