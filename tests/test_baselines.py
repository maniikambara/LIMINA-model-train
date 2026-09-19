"""tests/test_baselines.py -- Uji limina/baselines.py (sebelumnya tidak ada test sama sekali)."""

from __future__ import annotations

import pandas as pd

from limina import baselines


def _baris(**override) -> pd.Series:
    dasar = {
        "lapor_terlambat": 0,
        "tanpa_pendapatan": 0,
        "ekuitas_negatif": 0,
        "ako_negatif_berturut": 0,
        "hari_tanpa_transaksi_90d": 0,
        "utang_terhadap_aset": 0.5,
    }
    dasar.update(override)
    return pd.Series(dasar)


def test_skor_rule_based_mentah_baris_bersih_nol():
    assert baselines.skor_rule_based_mentah(_baris()) == 0.0


def test_skor_rule_based_mentah_sesuai_bobot_dokumentasi():
    baris = _baris(
        lapor_terlambat=1,
        tanpa_pendapatan=1,
        ekuitas_negatif=1,
        ako_negatif_berturut=2,
        hari_tanpa_transaksi_90d=21,
        utang_terhadap_aset=0.9,
    )
    assert baselines.skor_rule_based_mentah(baris) == baselines.SKOR_RULE_BASED_MAKS == 12.0


def test_skor_rule_based_mentah_nan_tidak_meracuni_indikator_lain():
    # ekuitas_negatif NaN (data finansial sebagian) -- indikator lain yang
    # tersedia tetap harus dihitung, bukan seluruh skor jadi NaN.
    baris = _baris(lapor_terlambat=1, ekuitas_negatif=float("nan"))
    assert baselines.skor_rule_based_mentah(baris) == baselines.BOBOT_RULE_BASED["lapor_terlambat"]


def test_skor_rule_based_mentah_semua_nan_nol_bukan_nan():
    baris = pd.Series({k: float("nan") for k in _baris().index})
    assert baselines.skor_rule_based_mentah(baris) == 0.0


def test_skor_rule_based_mengurutkan_ke_persentil():
    df = pd.DataFrame([_baris(), _baris(lapor_terlambat=1, tanpa_pendapatan=1)])
    hasil = baselines.skor_rule_based(df)
    assert hasil.iloc[1] > hasil.iloc[0]
    assert hasil.between(0, 100).all()


def test_skor_aturan_tunggal_urut_dari_jarak_lapor_terbesar():
    df = pd.DataFrame({"lapor_jarak_hari": [10, 100, 50]})
    hasil = baselines.skor_aturan_tunggal(df)
    assert hasil.idxmax() == 1  # jarak lapor terbesar -> persentil tertinggi


def test_skor_acak_deterministik_dengan_seed_sama():
    df = pd.DataFrame({"x": range(5)})
    assert baselines.skor_acak(df, seed=1).tolist() == baselines.skor_acak(df, seed=1).tolist()
