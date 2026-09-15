"""
test_raw_ingest.py -- Uji konversi tabel mentah Supabase jadi panel/potret
=============================================================================

Dibangun dengan data mentah BUATAN yang bentuk kolomnya persis sama dengan
skema Supabase asli (quarterly_financials, daily_transaction,
daily_full_universe_close, free_float_snapshot, plus tabel suspensi),
supaya limina/raw_ingest.py teruji tanpa koneksi database sungguhan.
"""

import numpy as np
import pandas as pd
import pytest

from limina import contracts, raw_ingest


@pytest.fixture
def symbols():
    return [f"SYM{i:03d}" for i in range(10)]


@pytest.fixture
def df_qf(symbols):
    rng = np.random.default_rng(0)
    report_dates = pd.date_range("2023-03-31", periods=8, freq="QE")
    rows = []
    for i, s in enumerate(symbols):
        bermasalah = i < 2
        for rd in report_dates:
            rows.append(
                dict(
                    symbol=s,
                    report_date=rd,
                    revenue=0.0 if bermasalah else rng.uniform(1e8, 1e9),
                    earnings=rng.uniform(-1e7, 1e7),
                    total_equity=-rng.uniform(1e6, 1e8) if bermasalah else rng.uniform(1e8, 1e9),
                    total_liabilities=rng.uniform(1e8, 5e8),
                    total_assets=rng.uniform(5e8, 1e9),
                    total_debt=rng.uniform(1e7, 1e8),
                    operating_cash_flow=-rng.uniform(1e6, 1e7) if bermasalah else rng.uniform(-1e6, 1e7),
                    free_cash_flow=rng.uniform(-1e6, 1e6),
                )
            )
    return pd.DataFrame(rows)


@pytest.fixture
def df_harga(symbols):
    rng = np.random.default_rng(1)
    dates = pd.date_range("2023-01-01", "2025-12-31", freq="B")
    rows = []
    for i, s in enumerate(symbols):
        bermasalah = i < 2
        for d in dates:
            volume = 0 if (bermasalah and rng.random() < 0.3) else int(rng.uniform(1_000, 100_000))
            close = 50 if (bermasalah and rng.random() < 0.1) else max(1.0, 100 + rng.normal(0, 5))
            rows.append(dict(symbol=s, date=d, close=float(close), volume=volume, market_cap=float(close) * 1e6))
    return pd.DataFrame(rows)


@pytest.fixture
def df_ff(symbols):
    rng = np.random.default_rng(2)
    return pd.DataFrame(
        {
            "symbol": symbols,
            "snapshot_date": pd.Timestamp("2024-06-01"),
            "free_float": rng.uniform(0.1, 0.6, len(symbols)),
            "sub_sector": rng.choice(["banks", "property"], len(symbols)),
        }
    )


@pytest.fixture
def df_suspensi(symbols):
    # Dua simbol "bermasalah" (index 0, 1), masing-masing satu peristiwa
    # kategori C SEBELUM cutoff latih 2025-01-01.
    return pd.DataFrame(
        {
            "symbol": [symbols[0], symbols[1]],
            "event_date": pd.to_datetime(["2024-08-01", "2024-10-15"]),
            "reason": ["belum menyampaikan laporan keuangan auditan tahunan", "ketidakpastian atas kelangsungan usaha"],
        }
    )


def test_gabungkan_harga_lebih_suka_daily_transaction_saat_tanggal_sama():
    dt = pd.DataFrame(
        {"symbol": ["AAA"], "date": [pd.Timestamp("2024-01-01")], "close": [111.0], "volume": [1], "market_cap": [1.0]}
    )
    dfu = pd.DataFrame(
        {"symbol": ["AAA"], "date": [pd.Timestamp("2024-01-01")], "close": [999.0], "volume": [2], "market_cap": [2.0]}
    )
    gabungan = raw_ingest.gabungkan_harga(dt, dfu)
    assert len(gabungan) == 1
    assert gabungan.iloc[0]["close"] == 111.0


def test_gabungkan_harga_kosong_tidak_error():
    kosong = pd.DataFrame(columns=["symbol", "date", "close", "volume", "market_cap"])
    hasil = raw_ingest.gabungkan_harga(kosong, kosong)
    assert len(hasil) == 0


def test_bangun_peta_sektor_ambil_snapshot_terbaru():
    ff = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA"],
            "snapshot_date": [pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01")],
            "free_float": [0.1, 0.2],
            "sub_sector": ["lama", "baru"],
        }
    )
    peta = raw_ingest.bangun_peta_sektor(ff)
    assert peta["AAA"] == "baru"


def test_hitung_fitur_finansial_tanpa_report_date_valid_jadi_tidak_lengkap():
    qf_symbol = pd.DataFrame(
        {
            "report_date": [pd.Timestamp("2026-01-01")],  # hanya ada laporan MASA DEPAN
            "revenue": [1e8],
            "total_equity": [1e8],
            "total_liabilities": [1e8],
            "total_assets": [2e8],
            "operating_cash_flow": [1e7],
        }
    )
    hasil = raw_ingest.hitung_fitur_finansial(qf_symbol, pd.Timestamp("2025-06-01"))
    assert hasil["data_lengkap_finansial"] is False
    assert pd.isna(hasil["lapor_jarak_hari"])


def test_hitung_fitur_finansial_pit_terpenuhi():
    qf_symbol = pd.DataFrame(
        {
            "report_date": pd.to_datetime(["2024-12-31", "2025-03-31"]),
            "revenue": [1e8, 1e8],
            "total_equity": [1e8, 1e8],
            "total_liabilities": [5e7, 5e7],
            "total_assets": [2e8, 2e8],
            "operating_cash_flow": [-1e6, -1e6],
        }
    )
    # as_of_date jauh sesudah 2025-03-31 -> laporan itu valid dipakai
    hasil = raw_ingest.hitung_fitur_finansial(qf_symbol, pd.Timestamp("2025-06-01"))
    assert hasil["data_lengkap_finansial"] is True
    assert hasil["feature_max_source_date_finansial"] == pd.Timestamp("2025-03-31")
    assert hasil["ako_negatif_berturut"] == 2  # dua kuartal berturut OCF negatif


def test_bangun_panel_latih_menghasilkan_rasio_1_banding_3(symbols, df_qf, df_harga, df_ff, df_suspensi):
    peta_sektor = raw_ingest.bangun_peta_sektor(df_ff)
    panel, ringkasan = raw_ingest.bangun_panel_latih(
        df_suspensi, symbols, df_qf, df_harga, peta_sektor
    )

    assert ringkasan["total_kategori_c"] == 2
    assert ringkasan["positif_panel"] == 2
    # Rasio 1:3 -> 2 positif harus diikuti hingga 6 negatif (bisa kurang kalau
    # kandidat tidak cukup, tapi dengan 10 simbol dan grid bulanan harusnya cukup)
    assert len(panel) <= 2 + 2 * 3
    assert len(panel) >= 2

    masalah = contracts.validate_panel(panel, ketat=False)
    assert masalah == []


def test_bangun_panel_latih_tanpa_suspensi_mengembalikan_kosong(symbols, df_qf, df_harga, df_ff):
    peta_sektor = raw_ingest.bangun_peta_sektor(df_ff)
    kosong = pd.DataFrame(columns=["symbol", "event_date", "reason"])
    panel, ringkasan = raw_ingest.bangun_panel_latih(kosong, symbols, df_qf, df_harga, peta_sektor)
    assert len(panel) == 0
    assert ringkasan["total_kategori_c"] == 0


def test_bangun_snapshot_pasar_placeholder_semua_negatif(symbols, df_qf, df_harga, df_ff):
    peta_sektor = raw_ingest.bangun_peta_sektor(df_ff)
    snap = raw_ingest.bangun_snapshot_pasar("2025-01-15", symbols, df_qf, df_harga, peta_sektor)
    assert snap["is_event_90d"].sum() == 0
    assert len(snap) == len(symbols)
    masalah = contracts.validate_panel(snap, ketat=False)
    assert masalah == []


def test_bangun_snapshot_pasar_dengan_label_asli(symbols, df_qf, df_harga, df_ff, df_suspensi):
    peta_sektor = raw_ingest.bangun_peta_sektor(df_ff)
    # Potret 30 hari sebelum event_date simbol pertama -> wajib is_event_90d=1
    tanggal_uji = (df_suspensi["event_date"].min() - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    snap = raw_ingest.bangun_snapshot_pasar(
        tanggal_uji, symbols, df_qf, df_harga, peta_sektor, df_suspensi_c=df_suspensi.assign(event_category="C")
    )
    baris_positif = snap[snap["symbol"] == df_suspensi.iloc[0]["symbol"]]
    assert baris_positif.iloc[0]["is_event_90d"] == 1


def test_bangun_riwayat_fitur_historis_satu_baris_per_tanggal(symbols, df_qf, df_harga):
    tanggal_list = pd.date_range("2024-06-01", "2024-08-01", freq="14D")
    riwayat = raw_ingest.bangun_riwayat_fitur_historis(symbols[0], tanggal_list, df_qf, df_harga)
    assert len(riwayat) == len(tanggal_list)
    assert list(riwayat["tanggal"]) == list(tanggal_list)
    for kolom in contracts.KOLOM_FITUR:
        assert kolom in riwayat.columns


def test_feature_max_source_date_tidak_pernah_melewati_as_of_date(symbols, df_qf, df_harga, df_ff):
    peta_sektor = raw_ingest.bangun_peta_sektor(df_ff)
    snap = raw_ingest.bangun_snapshot_pasar("2025-06-15", symbols, df_qf, df_harga, peta_sektor)
    as_of = pd.to_datetime(snap["as_of_date"])
    sumber = pd.to_datetime(snap["feature_max_source_date"])
    terisi = sumber.notna()
    assert (sumber[terisi] <= as_of[terisi]).all()


def test_diagnosa_cakupan_mentah_tumpang_tindih_penuh_saat_symbol_cocok(symbols, df_qf, df_harga):
    hasil = raw_ingest.diagnosa_cakupan_mentah(symbols, df_qf, df_harga)
    assert hasil["jumlah_symbols_universe"] == len(symbols)
    assert hasil["tumpang_tindih_quarterly_financials_persen"] == 100.0
    assert hasil["tumpang_tindih_harga_persen"] == 100.0
    assert hasil["report_date_min"] is not None
    assert hasil["harga_date_min"] is not None


def test_diagnosa_cakupan_mentah_mendeteksi_format_symbol_tidak_cocok(df_qf, df_harga):
    # Universe memakai akhiran ".JK", tapi df_qf/df_harga (dari fixture)
    # tidak -- persis pola bug format symbol yang pernah terjadi di
    # tabel stock_suspensions sungguhan.
    universe_akhiran_jk = [f"{s}.JK" for s in df_qf["symbol"].unique()]
    hasil = raw_ingest.diagnosa_cakupan_mentah(universe_akhiran_jk, df_qf, df_harga)
    assert hasil["tumpang_tindih_quarterly_financials_persen"] == 0.0
    assert hasil["tumpang_tindih_harga_persen"] == 0.0


def test_diagnosa_cakupan_mentah_tabel_kosong_tidak_error():
    kosong = pd.DataFrame(columns=["symbol", "report_date"])
    hasil = raw_ingest.diagnosa_cakupan_mentah(["AAAA"], kosong, kosong.rename(columns={"report_date": "date"}))
    assert hasil["tumpang_tindih_quarterly_financials_persen"] == 0.0
    assert hasil["report_date_min"] is None


def test_diagnosa_cakupan_mentah_mendeteksi_symbol_kategori_c_tanpa_qf(df_qf, df_harga):
    # df_qf/df_harga (fixture) hanya mencakup 10 symbol; simulasikan
    # peristiwa kategori C pada symbol LAIN yang tidak ada di keduanya --
    # persis pola insiden nyata: quarterly_financials/daily_transaction
    # baru mencakup sebagian kecil emiten, dan justru tidak mencakup
    # emiten yang pernah kena kategori C.
    df_suspensi_c = pd.DataFrame({
        "symbol": ["TIDAK_ADA_QF"],
        "event_date": ["2025-01-01"],
    })
    hasil = raw_ingest.diagnosa_cakupan_mentah(
        list(df_qf["symbol"].unique()), df_qf, df_harga, df_suspensi_c
    )
    assert hasil["jumlah_symbol_kategori_c"] == 1
    assert hasil["jumlah_symbol_kategori_c_dengan_quarterly_financials"] == 0
    assert hasil["jumlah_symbol_kategori_c_siap_dilatih"] == 0
    assert "TIDAK_ADA_QF" in hasil["symbol_kategori_c_belum_punya_quarterly_financials_contoh"]


def test_diagnosa_cakupan_mentah_mendeteksi_riwayat_harga_tidak_menjangkau_event(symbols, df_qf, df_harga):
    # Symbol PUNYA baris quarterly_financials, tapi peristiwanya terlalu
    # jauh di masa lalu dibanding riwayat df_harga (fixture hanya
    # mencakup 2023-2025) -- ini pola persis MGLV.JK pada insiden nyata:
    # punya laporan keuangan, tapi riwayat harganya belum menjangkau
    # tanggal peristiwa yang dibutuhkan.
    df_suspensi_c = pd.DataFrame({
        "symbol": [symbols[0]],
        "event_date": ["2019-01-01"],  # jauh sebelum riwayat df_harga dimulai
    })
    hasil = raw_ingest.diagnosa_cakupan_mentah(symbols, df_qf, df_harga, df_suspensi_c)
    assert hasil["jumlah_symbol_kategori_c_dengan_quarterly_financials"] == 1
    assert hasil["jumlah_symbol_kategori_c_siap_dilatih"] == 0


def test_diagnosa_cakupan_mentah_symbol_siap_dilatih_saat_riwayat_cukup(symbols, df_qf, df_harga):
    # Peristiwa dalam rentang yang benar-benar dicakup df_harga fixture
    # (2023-2025) -- symbol_kategori_c_siap_dilatih wajib mendeteksi ini.
    df_suspensi_c = pd.DataFrame({
        "symbol": [symbols[0]],
        "event_date": ["2025-06-01"],
    })
    hasil = raw_ingest.diagnosa_cakupan_mentah(symbols, df_qf, df_harga, df_suspensi_c)
    assert hasil["jumlah_symbol_kategori_c_siap_dilatih"] == 1
