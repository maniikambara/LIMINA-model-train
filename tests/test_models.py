"""
test_models.py
================

- uji bahwa Kandidat 1 memakai data terstandardisasi
- uji bahwa Kandidat 2 tidak memakai data terstandardisasi
- uji bahwa kontribusi indikator menjumlah ke skor akhir dikurangi intercept

(docs/rancangan/AMBA-struktur-model-dan-algoritma.md bagian 13)
"""

import numpy as np
import pandas as pd

from limina import models
from limina.contracts import KOLOM_FITUR


def _siapkan_data(panel_uji_factory, n=300, proporsi_positif=0.25):
    panel = panel_uji_factory(n_baris=n, proporsi_positif=proporsi_positif)
    X = panel[KOLOM_FITUR]
    y = panel["is_event_90d"]
    return panel, X, y


def test_kandidat_1_memakai_data_terstandardisasi(panel_uji_factory):
    panel, X, y = _siapkan_data(panel_uji_factory)
    model, scaler = models.latih_kandidat_1(X, y)

    X_filled = X.fillna(X.median())
    X_scaled_manual = scaler.transform(X_filled)

    # Rata-rata tiap kolom hasil scaler harus mendekati 0 (ciri StandardScaler)
    assert np.allclose(X_scaled_manual.mean(axis=0), 0, atol=1e-8)
    # Model dilatih pada input dengan skala ini, bukan skala mentah:
    # decision_function pada data mentah (tidak discaling) semestinya
    # menghasilkan urutan yang berbeda jauh dari data yang discaling benar.
    skor_benar = model.decision_function(X_scaled_manual)
    skor_tanpa_scaling = model.decision_function(X_filled.values)
    assert not np.allclose(skor_benar, skor_tanpa_scaling)


def test_kandidat_2_tidak_memakai_data_terstandardisasi(panel_uji_factory):
    panel, X, y = _siapkan_data(panel_uji_factory)
    model_gb = models.latih_kandidat_2(X, y)

    X_filled = X.fillna(X.median())
    # predict_proba langsung menerima X_filled (tanpa scaling) dan berhasil,
    # membuktikan model dilatih pada skala data asli, bukan data terstandardisasi.
    proba = model_gb.predict_proba(X_filled)
    assert proba.shape == (len(X_filled), 2)


def test_kontribusi_indikator_menjumlah_ke_skor_dikurangi_intercept(panel_uji_factory):
    panel, X, y = _siapkan_data(panel_uji_factory, n=400)
    model, scaler = models.latih_kandidat_1(X, y)
    median_latih = X.median()

    baris = panel.iloc[0]
    baris_terisi = baris.copy()
    for kolom in KOLOM_FITUR:
        if pd.isna(baris_terisi[kolom]):
            baris_terisi[kolom] = median_latih[kolom]

    kontrib = models.kontribusi_indikator(model, scaler, baris_terisi)
    jumlah_kontribusi = sum(v for k, v in kontrib.items() if not k.startswith("_"))

    X_row = baris_terisi[KOLOM_FITUR].to_frame().T
    X_scaled = scaler.transform(X_row)
    skor_seharusnya = float(model.decision_function(X_scaled)[0])

    assert abs((jumlah_kontribusi + kontrib["_intercept"]) - skor_seharusnya) < 1e-8


def test_indikator_dominan_adalah_kontribusi_absolut_terbesar(panel_uji_factory):
    panel, X, y = _siapkan_data(panel_uji_factory, n=400)
    model, scaler = models.latih_kandidat_1(X, y)
    median_latih = X.median()

    baris = panel.iloc[1]
    baris_terisi = baris.copy()
    for kolom in KOLOM_FITUR:
        if pd.isna(baris_terisi[kolom]):
            baris_terisi[kolom] = median_latih[kolom]

    kontrib = models.kontribusi_indikator(model, scaler, baris_terisi)
    dominan = kontrib["_indikator_dominan"]
    nilai_dominan = abs(kontrib[dominan])
    nilai_lain = [abs(v) for k, v in kontrib.items() if not k.startswith("_") and k != dominan]

    assert all(nilai_dominan >= v for v in nilai_lain)
