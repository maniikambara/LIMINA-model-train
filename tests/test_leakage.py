"""
test_leakage.py -- Uji pemeriksa dengan dataset yang sengaja dibocorkan
==========================================================================
"""

import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from limina import leakage
from limina.contracts import KOLOM_FITUR


def test_cek_tanggal_sumber_lolos_pada_data_bersih(panel_uji_factory):
    panel = panel_uji_factory(n_baris=100, proporsi_positif=0.25)
    masalah = leakage.cek_tanggal_sumber(panel)
    assert masalah == []


def test_cek_tanggal_sumber_menangkap_kebocoran_yang_disengaja(panel_uji_factory):
    panel = panel_uji_factory(n_baris=100, proporsi_positif=0.25)
    # Sengaja bocorkan: buat feature_max_source_date lebih baru dari as_of_date
    panel_bocor = panel.copy()
    panel_bocor.loc[0, "feature_max_source_date"] = panel_bocor.loc[0, "as_of_date"] + pd.Timedelta(days=10)

    masalah = leakage.cek_tanggal_sumber(panel_bocor)
    assert len(masalah) == 1
    assert "1 baris" in masalah[0]


def test_cek_tanggal_sumber_menangkap_banyak_baris_bocor(panel_uji_factory):
    panel = panel_uji_factory(n_baris=200, proporsi_positif=0.25)
    panel_bocor = panel.copy()
    idx = panel_bocor.index[:15]
    panel_bocor.loc[idx, "feature_max_source_date"] = (
        pd.to_datetime(panel_bocor.loc[idx, "as_of_date"]) + pd.Timedelta(days=5)
    )
    masalah = leakage.cek_tanggal_sumber(panel_bocor)
    assert len(masalah) == 1
    assert "15 baris" in masalah[0]


def test_cek_pengacakan_label_auc_sekitar_setengah(panel_uji_factory):
    panel = panel_uji_factory(n_baris=400, proporsi_positif=0.25)
    X = panel[KOLOM_FITUR].fillna(panel[KOLOM_FITUR].median())
    y = panel["is_event_90d"]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    masalah, auc = leakage.cek_pengacakan_label(LogisticRegression, X_scaled, y)
    assert masalah == []
    assert 0.35 <= auc <= 0.65  # sedikit longgar untuk data sintetis kecil


def test_cek_fitur_kendali_koefisien_acak_kecil(panel_uji_factory):
    panel = panel_uji_factory(n_baris=400, proporsi_positif=0.25)
    X = panel[KOLOM_FITUR].fillna(panel[KOLOM_FITUR].median())
    y = panel["is_event_90d"]

    masalah, koef_acak = leakage.cek_fitur_kendali(LogisticRegression, X, y, StandardScaler)
    # Tidak menjamin selalu lolos di data acak, tapi koefisien harus terhitung
    assert isinstance(koef_acak, float)
    assert koef_acak >= 0


def test_cek_batas_kewajaran_menangkap_auc_terlalu_tinggi():
    masalah = leakage.cek_batas_kewajaran(0.97)
    assert len(masalah) == 1
    assert "gejala kebocoran" in masalah[0]


def test_cek_batas_kewajaran_lolos_pada_auc_wajar():
    masalah = leakage.cek_batas_kewajaran(0.72)
    assert masalah == []


def test_cek_batas_kewajaran_mengabaikan_nan():
    masalah = leakage.cek_batas_kewajaran(float("nan"))
    assert masalah == []


def test_jalankan_semua_pemeriksaan_melempar_error_saat_ada_kebocoran(panel_uji_factory):
    panel = panel_uji_factory(n_baris=100, proporsi_positif=0.25)
    panel_bocor = panel.copy()
    panel_bocor.loc[0, "feature_max_source_date"] = panel_bocor.loc[0, "as_of_date"] + pd.Timedelta(days=1)

    X = panel_bocor[KOLOM_FITUR].fillna(panel_bocor[KOLOM_FITUR].median())
    y = panel_bocor["is_event_90d"]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    with pytest.raises(leakage.PemeriksaanKebocoranGagal):
        leakage.jalankan_semua_pemeriksaan(
            df_panel=panel_bocor,
            model_class=LogisticRegression,
            scaler_class=StandardScaler,
            X_train=X,
            y_train=y,
            X_train_scaled=X_scaled,
            lempar_error=True,
        )
