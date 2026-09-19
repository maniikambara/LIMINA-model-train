"""
tests/test_labels.py -- Uji limina/labels.py

Sebelumnya modul ini SAMA SEKALI belum punya berkas uji sendiri, padahal
bentuk_label_is_event_90d adalah fungsi yang menentukan target latih.
Fokus di sini:

  1. Perilaku dasar klasifikasi_alasan dan bentuk_label_is_event_90d
     (batas jendela, hanya kategori C yang jadi positif, dst).
  2. Regresi KONSISTENSI untuk config.JENDELA_LABEL_HARI: default
     jendela_hari WAJIB sama dengan config.JENDELA_LABEL_HARI, dan
     raw_ingest.OFFSET_AS_OF_DARI_EVENT_HARI WAJIB sama dengan
     setengahnya. Ini dua tempat yang sebelumnya hardcode 90
     sendiri-sendiri secara diam-diam; kalau ada yang mengganti salah
     satu tanpa yang lain lagi di masa depan, uji ini yang menangkapnya
     -- lihat catatan di limina/config.py::JENDELA_LABEL_HARI kenapa
     desinkronisasi itu berbahaya (label tersensor, bukan cuma kurang
     presisi).
"""

from __future__ import annotations

import pandas as pd
import pytest

from limina import config, labels, raw_ingest


@pytest.fixture
def taksonomi():
    return {
        "A": ["permintaan emiten"],
        "B": ["cooling down"],
        "C": ["kelangsungan usaha", "laporan keuangan"],
    }


def test_klasifikasi_alasan_mencocokkan_kata_kunci(taksonomi):
    assert labels.klasifikasi_alasan("Menunda kelangsungan usaha", taksonomi) == "C"
    assert labels.klasifikasi_alasan("permintaan emiten sendiri", taksonomi) == "A"
    assert labels.klasifikasi_alasan("cooling down harga", taksonomi) == "B"


def test_klasifikasi_alasan_tidak_cocok_kembalikan_none(taksonomi):
    assert labels.klasifikasi_alasan("Suspend more than 6 month", taksonomi) is None


def test_klasifikasi_alasan_kosong_kembalikan_none(taksonomi):
    assert labels.klasifikasi_alasan("", taksonomi) is None
    assert labels.klasifikasi_alasan(None, taksonomi) is None


def test_bentuk_label_hanya_kategori_c_jadi_positif(taksonomi):
    df_suspensi = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "event_date": [pd.Timestamp("2026-03-01"), pd.Timestamp("2026-03-01")],
            "reason": ["kelangsungan usaha", "permintaan emiten"],  # C, A
        }
    )
    df_cakupan = pd.DataFrame(
        {"symbol": ["AAA", "BBB"], "as_of_date": [pd.Timestamp("2026-02-01"), pd.Timestamp("2026-02-01")]}
    )
    hasil = labels.bentuk_label_is_event_90d(
        df_suspensi, df_cakupan, taksonomi=taksonomi, jendela_hari=30
    )
    assert hasil.set_index("symbol").loc["AAA", "is_event_90d"] == 1
    assert hasil.set_index("symbol").loc["BBB", "is_event_90d"] == 0


def test_bentuk_label_batas_jendela_inklusif_eksklusif(taksonomi):
    # event_date = 2026-03-01, jendela_hari=30 -> batas_awal = 2026-01-30.
    # as_of tepat di batas_awal HARUS positif (>=), tepat di event_date
    # HARUS negatif (< event_date, hari kejadian sendiri bukan "sebelum").
    df_suspensi = pd.DataFrame(
        {"symbol": ["AAA"], "event_date": [pd.Timestamp("2026-03-01")], "reason": ["kelangsungan usaha"]}
    )
    df_cakupan = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "as_of_date": [
                pd.Timestamp("2026-01-30"),  # tepat batas_awal -> positif
                pd.Timestamp("2026-01-29"),  # sehari sebelum batas_awal -> negatif
                pd.Timestamp("2026-03-01"),  # tepat event_date -> negatif
            ],
        }
    )
    hasil = labels.bentuk_label_is_event_90d(
        df_suspensi, df_cakupan, taksonomi=taksonomi, jendela_hari=30
    )
    assert list(hasil["is_event_90d"]) == [1, 0, 0]


def test_bentuk_label_default_jendela_hari_ikut_config(taksonomi):
    # default jendela_hari HARUS sama dengan config.JENDELA_LABEL_HARI,
    # bukan angka hardcode terpisah -- lihat docstring modul ini.
    event_date = pd.Timestamp("2026-06-01")
    batas_awal = event_date - pd.Timedelta(days=config.JENDELA_LABEL_HARI)
    df_suspensi = pd.DataFrame({"symbol": ["AAA"], "event_date": [event_date], "reason": ["kelangsungan usaha"]})
    df_cakupan = pd.DataFrame({"symbol": ["AAA"], "as_of_date": [batas_awal]})

    hasil = labels.bentuk_label_is_event_90d(df_suspensi, df_cakupan, taksonomi=taksonomi)
    assert hasil.loc[0, "is_event_90d"] == 1


def test_offset_as_of_dari_event_hari_setengah_dari_jendela_label():
    # Titik tengah jendela positif (raw_ingest.bangun_baris_positif) wajib
    # ikut config.JENDELA_LABEL_HARI, bukan hardcode 45 yang cuma benar
    # kalau JENDELA_LABEL_HARI kebetulan 90.
    assert raw_ingest.OFFSET_AS_OF_DARI_EVENT_HARI == config.JENDELA_LABEL_HARI // 2
