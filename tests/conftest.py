"""
conftest.py -- Fixture panel KHUSUS UNTUK UJI, bukan data proyek
====================================================================

Ini BUKAN pengganti data produk. Proyek ini (lihat notebooks/01-05)
hanya pernah melatih dan menilai memakai data sungguhan dari Supabase --
tidak ada satu pun jalur produksi yang memakai data buatan.

Yang ada di sini murni kebutuhan pengujian generik: beberapa uji di
tests/test_leakage.py dan tests/test_models.py menguji perilaku
STATISTIK/PLUMBING (mis. "apakah AUC dari label yang diacak mendekati
0,50", "apakah Kandidat 1 memakai data terstandardisasi") yang butuh
sebuah panel berbentuk kontrak dengan sinyal yang bisa dipelajari, dan
itu tidak bergantung sama sekali pada bagaimana panel itu diperoleh.
Untuk itu, tidak masuk akal mewajibkan koneksi Supabase sungguhan hanya
untuk menguji rumus AUC. Fixture ini menyediakan bentuk sekecil mungkin
yang dibutuhkan uji-uji itu.

sys.path diatur di sini SAJA (bukan diulang di setiap berkas uji) supaya
`import limina` berhasil dari mana pun pytest dijalankan, tanpa perlu
memasang paket ini lebih dulu.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from limina.contracts import KOLOM_FITUR

_SEKTOR_CONTOH = ["banks", "property", "consumer"]
_PAPAN_CONTOH = ["Main", "Development", "Acceleration"]


def _buat_indikator(rng: np.random.Generator, n: int, risiko: float) -> pd.DataFrame:
    """
    Nilai indikator dengan `risiko` 0..1 menggeser distribusinya ke arah
    kondisi bermasalah, supaya uji AUC/leakage punya sinyal yang
    benar-benar bisa dipelajari (bukan derau murni).
    """
    return pd.DataFrame(
        {
            "lapor_jarak_hari": rng.normal(60 + risiko * 40, 20, n).clip(0),
            "lapor_terlambat": rng.binomial(1, 0.1 + risiko * 0.5, n),
            "tanpa_pendapatan": rng.binomial(1, 0.05 + risiko * 0.3, n),
            "ekuitas_negatif": rng.binomial(1, 0.05 + risiko * 0.35, n),
            "utang_terhadap_aset": rng.normal(0.5 + risiko * 0.3, 0.15, n).clip(0, 2),
            "ako_negatif_berturut": rng.poisson(0.5 + risiko * 3, n),
            "hari_tanpa_transaksi_90d": rng.poisson(2 + risiko * 15, n).clip(0, 90),
            "rasio_volume_30_90": rng.normal(1.0 - risiko * 0.4, 0.3, n).clip(0),
            "hari_di_batas_bawah_90d": rng.poisson(1 + risiko * 10, n).clip(0, 90),
            "turun_dari_puncak_90d": rng.normal(-0.1 - risiko * 0.4, 0.15, n).clip(-1, 0),
            "volatilitas_90d": rng.normal(0.02 + risiko * 0.03, 0.01, n).clip(0),
        }
    )


def _buat_panel_uji(n_baris: int = 400, proporsi_positif: float = 0.25, *, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_pos = int(n_baris * proporsi_positif)
    n_neg = n_baris - n_pos
    tanggal_range = pd.date_range("2020-01-01", "2024-12-31", freq="D")

    def _bangun(n: int, risiko: float, positif: bool) -> pd.DataFrame:
        indikator = _buat_indikator(rng, n, risiko)
        as_of = pd.to_datetime(rng.choice(tanggal_range, size=n))
        event_date = (
            as_of + pd.to_timedelta(rng.integers(1, 90, n), unit="D") if positif else pd.NaT
        )
        identitas = pd.DataFrame(
            {
                "symbol": [f"UJI{i:04d}" for i in range(n)],
                "as_of_date": as_of,
                "sector": rng.choice(_SEKTOR_CONTOH, n),
                "board": rng.choice(_PAPAN_CONTOH, n),
                "is_event_90d": 1 if positif else 0,
                "event_date": event_date,
                "event_category": "C" if positif else "",
                "already_flagged": 0,
                "data_complete": 1,
            }
        )
        identitas["feature_max_source_date"] = identitas["as_of_date"] - pd.to_timedelta(
            rng.integers(1, 30, n), unit="D"
        )
        return pd.concat([identitas, indikator], axis=1)

    data = pd.concat(
        [_bangun(n_pos, risiko=1.0, positif=True), _bangun(n_neg, risiko=0.0, positif=False)],
        ignore_index=True,
    )
    data["symbol"] = [f"UJI{i:04d}" for i in range(len(data))]
    return data.sample(frac=1, random_state=seed).reset_index(drop=True)


@pytest.fixture
def panel_uji_factory():
    """Fixture callable: panel_uji_factory(n_baris=..., proporsi_positif=...)."""
    return _buat_panel_uji


__all__ = ["KOLOM_FITUR"]
