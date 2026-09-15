"""
test_splits.py -- Uji jendela bergulir (relatif ke tanggal berjalan)
========================================================================
"""

import pandas as pd
import pytest

from limina import splits


def test_batas_label_matang_mundur_90_hari_dari_sekarang():
    batas = splits.batas_label_matang("2026-09-11", jendela_label_hari=90)
    assert batas == pd.Timestamp("2026-06-13")


def test_hitung_jendela_bergulir_bentuk_dan_urutan():
    cutoff, tanggal_potret = splits.hitung_jendela_bergulir(
        "2026-09-11", jendela_label_hari=90, jumlah_potret=6, jarak_potret_hari=30
    )
    assert len(tanggal_potret) == 6
    # terurut naik (kronologis)
    assert tanggal_potret == sorted(tanggal_potret)
    # tanggal potret terakhir persis di batas label matang
    assert pd.Timestamp(tanggal_potret[-1]) == splits.batas_label_matang("2026-09-11", 90)
    # cutoff_latih sama dengan tanggal potret paling awal
    assert cutoff == pd.Timestamp(tanggal_potret[0])
    # berjarak 30 hari satu sama lain
    for a, b in zip(tanggal_potret, tanggal_potret[1:]):
        assert (pd.Timestamp(b) - pd.Timestamp(a)).days == 30


def test_hitung_jendela_bergulir_bergeser_maju_seiring_waktu():
    _, potret_awal = splits.hitung_jendela_bergulir("2026-09-11")
    _, potret_sebulan_kemudian = splits.hitung_jendela_bergulir("2026-10-11")
    assert pd.Timestamp(potret_sebulan_kemudian[-1]) > pd.Timestamp(potret_awal[-1])


def test_pisahkan_temporal_hanya_menyisihkan_positif_setelah_cutoff():
    df = pd.DataFrame(
        {
            "symbol": ["A", "B", "C", "D"],
            "is_event_90d": [1, 1, 0, 0],
            "event_date": pd.to_datetime(["2026-01-01", "2026-08-01", pd.NaT, pd.NaT]),
        }
    )
    cutoff = pd.Timestamp("2026-06-01")
    train = splits.pisahkan_temporal(df, cutoff)
    # A (positif sebelum cutoff) dan kedua negatif tetap ikut; B (positif
    # setelah cutoff) disisihkan untuk evaluasi, tidak ikut latih.
    assert set(train["symbol"]) == {"A", "C", "D"}


def test_validasi_tidak_ada_tumpang_tindih_mendeteksi_symbol_event_date_sama():
    train_data = pd.DataFrame(
        {
            "symbol": ["A"],
            "is_event_90d": [1],
            "event_date": pd.to_datetime(["2026-01-01"]),
        }
    )
    snapshot_dict = {
        "2025-12-01": pd.DataFrame(
            {
                "symbol": ["A"],
                "is_event_90d": [1],
                "event_date": pd.to_datetime(["2026-01-01"]),
            }
        )
    }
    masalah = splits.validasi_tidak_ada_tumpang_tindih(train_data, snapshot_dict)
    assert len(masalah) == 1


def test_saring_data_lengkap_membuang_baris_tidak_lengkap():
    df = pd.DataFrame({
        "is_event_90d": [1, 1, 0, 0, 0, 0],
        "data_complete": [1, 1, 1, 1, 0, 0],
    })
    hasil = splits.saring_data_lengkap(df, minimum_baris=1, minimum_positif=1)
    assert len(hasil) == 4
    assert (hasil["data_complete"] == 1).all()


def test_saring_data_lengkap_melempar_error_jelas_saat_semua_tidak_lengkap():
    df = pd.DataFrame({
        "is_event_90d": [1, 1, 0, 0],
        "data_complete": [0, 0, 0, 0],
    })
    with pytest.raises(RuntimeError, match="terlalu sedikit untuk"):
        splits.saring_data_lengkap(df)


def test_saring_data_lengkap_melempar_error_saat_positif_hilang_setelah_saring():
    df = pd.DataFrame({
        "is_event_90d": [1, 0, 0, 0, 0, 0] + [0] * 20,
        "data_complete": [0, 1, 1, 1, 1, 1] + [1] * 20,  # satu-satunya positif justru tidak lengkap
    })
    with pytest.raises(RuntimeError, match="terlalu sedikit untuk"):
        splits.saring_data_lengkap(df, minimum_baris=1, minimum_positif=1)
