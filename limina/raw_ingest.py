"""
raw_ingest.py -- Mengubah tabel mentah Supabase jadi panel/potret LIMINA
===========================================================================

Modul ini menjembatani DUA bentuk data:

  MENTAH (apa yang ada di tabel Supabase Anda):
    quarterly_financials        satu baris per (symbol, report_date)
    daily_transaction           satu baris per (symbol, date), harga+volume
    daily_full_universe_close   sama bentuknya, cakupan lebih luas/murah
    free_float_snapshot         satu baris per (symbol, snapshot_date)
    company_overview            satu baris per symbol (sector, sub_sector, board)
    stock_suspensions           satu baris per peristiwa suspensi (label)

  KONTRAK PANEL (apa yang dibutuhkan limina/contracts.py, lihat
  KOLOM_WAJIB_PANEL): satu baris per (symbol, as_of_date) berisi identitas,
  label, dan seluruh KOLOM_FITUR.

Semua fungsi di sini murni menerima/mengembalikan pandas.DataFrame biasa --
TIDAK ADA satu pun yang memanggil Supabase. Ini sengaja, supaya seluruh
logika di sini bisa diuji dengan tabel kecil buatan tangan tanpa koneksi
database (lihat tests/test_raw_ingest.py -- fixture uji, bukan data
proyek), dan supaya notebook 01/02 tinggal jadi lapisan tipis: unduh
tabel, panggil fungsi di sini, simpan ke CSV.

Batasan yang diwarisi dari skema mentah (baca sebelum mengubah nilai
default di bawah):

  - "board" (papan pencatatan) dan "sector" punya sumber utama di tabel
    company_overview. Kalau tabel itu belum mencakup suatu simbol, board
    jatuh ke BOARD_DEFAULT (menonaktifkan penyaringan "papan sebanding"
    di sampling.py untuk simbol itu saja), dan sector jatuh ke pendekatan
    dari sub_sector snapshot TERBARU di free_float_snapshot (bukan
    sektor pada as_of_date historisnya).
  - already_flagged (status Notasi Khusus BEI pada as_of_date) tidak
    punya sumber data mentah di enam tabel di atas. Diisi 0 untuk semua
    baris -- lihat README bagian keterbatasan.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, contracts, features as feat, labels, pit, sampling

BOARD_DEFAULT = "Main"  # lihat catatan batasan di atas modul ini
JENDELA_PIT_HARI = 30  # sama dengan default pit.titik_potong
JENDELA_HARGA_HARI = 90  # sama dengan default pit.rentang_harga_valid -- jendela LOOKBACK
# untuk fitur harga, TIDAK terkait dengan horizon peringatan ke depan; lihat
# limina/config.py::JENDELA_LABEL_HARI untuk itu.
OFFSET_AS_OF_DARI_EVENT_HARI = config.JENDELA_LABEL_HARI // 2  # titik tengah jendela
# label (config.JENDELA_LABEL_HARI), lihat bangun_baris_positif. Ikut berubah
# otomatis kalau JENDELA_LABEL_HARI diganti -- jangan hardcode ulang di sini.


def diagnosa_cakupan_mentah(
    symbols_universe: list[str],
    df_qf: pd.DataFrame,
    df_harga: pd.DataFrame,
    df_suspensi_c: pd.DataFrame | None = None,
    *,
    offset_as_of_hari: int = OFFSET_AS_OF_DARI_EVENT_HARI,
) -> dict:
    """
    Ringkasan cepat: seberapa besar symbols_universe tumpang tindih
    dengan symbol yang benar-benar punya baris di quarterly_financials
    dan di tabel harga, plus rentang tanggal report_date/date yang
    tersedia. Dipanggil notebook 02 SEBELUM membangun panel/potret.

    Kalau data_complete ternyata 0 untuk hampir semua baris, dua
    penyebab paling umum langsung kelihatan di sini: format symbol yang
    tidak cocok antar tabel (mis. "BBCA.JK" di satu tabel, "BBCA" di
    tabel lain -- lihat contoh_symbol_* di bawah), atau riwayat tanggal
    yang belum cukup panjang untuk titik potong yang dibutuhkan (lihat
    *_min/*_max di bawah, bandingkan dengan tanggal potret yang dipakai).

    Kalau df_suspensi_c diberikan (hasil klasifikasi kategori C dari
    stock_suspensions, lihat labels.klasifikasi_alasan), diagnosa juga
    menjawab pertanyaan yang paling menentukan bisa-tidaknya panel latih
    dibangun sama sekali: dari symbol yang benar-benar punya peristiwa
    kategori C, berapa yang punya baris di quarterly_financials, dan
    dari yang punya baris itu, berapa yang riwayat harganya BENAR-BENAR
    mencakup tanggal peristiwanya (bukan cuma "apakah symbol itu ada di
    tabel harga", tapi "apakah jendela tanggalnya sampai ke titik yang
    dibutuhkan"). Kalau jumlah_symbol_kategori_c_siap_dilatih nol, panel
    latih TIDAK BISA dibangun apa pun kondisi lainnya -- ini bukan
    sesuatu yang bisa diperbaiki dengan mengubah kode, hanya dengan
    memperluas cakupan quarterly_financials/daily_transaction Anda,
    idealnya ke symbol yang justru muncul di
    symbol_kategori_c_belum_punya_quarterly_financials_contoh.
    """
    universe = set(symbols_universe)
    symbol_qf = set(df_qf["symbol"]) if len(df_qf) else set()
    symbol_harga = set(df_harga["symbol"]) if len(df_harga) else set()

    def _persentase_tumpang_tindih(basis: set) -> float:
        if not universe:
            return 0.0
        return 100 * len(universe & basis) / len(universe)

    hasil = {
        "jumlah_symbols_universe": len(universe),
        "tumpang_tindih_quarterly_financials_persen": round(_persentase_tumpang_tindih(symbol_qf), 1),
        "tumpang_tindih_harga_persen": round(_persentase_tumpang_tindih(symbol_harga), 1),
        "contoh_symbol_universe": sorted(universe)[:5],
        "contoh_symbol_quarterly_financials": sorted(symbol_qf)[:5],
        "contoh_symbol_harga": sorted(symbol_harga)[:5],
        "report_date_min": None,
        "report_date_max": None,
        "harga_date_min": None,
        "harga_date_max": None,
    }

    if len(df_qf) and "report_date" in df_qf.columns:
        tanggal_qf = pd.to_datetime(df_qf["report_date"])
        hasil["report_date_min"] = tanggal_qf.min().strftime("%Y-%m-%d")
        hasil["report_date_max"] = tanggal_qf.max().strftime("%Y-%m-%d")

    if len(df_harga) and "date" in df_harga.columns:
        tanggal_harga = pd.to_datetime(df_harga["date"])
        hasil["harga_date_min"] = tanggal_harga.min().strftime("%Y-%m-%d")
        hasil["harga_date_max"] = tanggal_harga.max().strftime("%Y-%m-%d")

    if df_suspensi_c is not None and len(df_suspensi_c) and "symbol" in df_suspensi_c.columns:
        symbol_kategori_c = set(df_suspensi_c["symbol"].unique())
        symbol_c_dengan_qf = symbol_kategori_c & symbol_qf

        symbol_siap_dilatih = set()
        for _, baris in df_suspensi_c[df_suspensi_c["symbol"].isin(symbol_c_dengan_qf)].iterrows():
            symbol = baris["symbol"]
            as_of = pd.Timestamp(baris["event_date"]) - pd.Timedelta(days=offset_as_of_hari)
            titik_potong = pit.titik_potong(as_of, JENDELA_PIT_HARI)
            start, end = pit.rentang_harga_valid(titik_potong, JENDELA_HARGA_HARI)

            harga_symbol = df_harga[df_harga["symbol"] == symbol] if len(df_harga) else pd.DataFrame()
            if len(harga_symbol) and "date" in harga_symbol.columns:
                tanggal_harga_symbol = pd.to_datetime(harga_symbol["date"])
                if ((tanggal_harga_symbol >= start) & (tanggal_harga_symbol <= end)).any():
                    symbol_siap_dilatih.add(symbol)

        hasil["jumlah_symbol_kategori_c"] = len(symbol_kategori_c)
        hasil["jumlah_symbol_kategori_c_dengan_quarterly_financials"] = len(symbol_c_dengan_qf)
        hasil["symbol_kategori_c_dengan_quarterly_financials"] = sorted(symbol_c_dengan_qf)
        hasil["jumlah_symbol_kategori_c_siap_dilatih"] = len(symbol_siap_dilatih)
        hasil["symbol_kategori_c_belum_punya_quarterly_financials_contoh"] = sorted(
            symbol_kategori_c - symbol_qf
        )[:15]

    return hasil


def symbols_dengan_data_lengkap(df_qf: pd.DataFrame, df_harga: pd.DataFrame) -> list[str]:
    """
    Cakupan emiten yang REALISTIS untuk dinilai/dilatih: symbol yang
    punya baris di quarterly_financials DAN di tabel harga sekaligus.

    Ini SENGAJA bukan union dengan company_overview. company_overview
    mendaftar seluruh emiten TERCATAT di bursa (satu baris per symbol,
    lihat modul ini bagian atas), termasuk yang sama sekali belum
    tersedia di quarterly_financials maupun tabel harga Anda. Memakai
    union symbols_universe = qf | company_overview | harga membuat
    symbols_universe jauh lebih besar daripada symbol yang benar-benar
    bisa dinilai -- setiap symbol tambahan dari company_overview yang
    tidak ada di qf ATAU tidak ada di harga dijamin data_complete=0
    untuk SELURUH baris symbol itu (lihat tempel_fitur -> data_complete
    = data_lengkap_finansial AND data_lengkap_harga), apa pun jendela
    tanggal yang dipakai. Itu bukan cakupan yang bisa diperbaiki lewat
    kode; hanya menambah baris kosong yang membuat scores.json/panel
    kelihatan mencakup lebih banyak emiten daripada yang sebenarnya
    punya data.

    company_overview tetap dipakai di tempat lain (bangun_peta_sektor,
    bangun_peta_board) karena board/sector-nya berguna bahkan untuk
    symbol yang belum lengkap datanya -- fungsi ini HANYA menjawab
    "symbol mana yang layak masuk symbols_universe untuk membangun
    panel/potret/skor", bukan "symbol mana yang tercatat di bursa".
    """
    symbol_qf = set(df_qf["symbol"]) if len(df_qf) else set()
    symbol_harga = set(df_harga["symbol"]) if len(df_harga) else set()
    return sorted(symbol_qf & symbol_harga)


def prioritas_backfill_kategori_c(
    df_suspensi_c: pd.DataFrame,
    df_qf: pd.DataFrame,
    df_harga: pd.DataFrame,
    *,
    offset_hari: int = OFFSET_AS_OF_DARI_EVENT_HARI,
    mundur_hari_pit: int = JENDELA_PIT_HARI,
    jendela_harga_hari: int = JENDELA_HARGA_HARI,
) -> pd.DataFrame:
    """
    Untuk tiap symbol dengan peristiwa kategori C yang BELUM termasuk
    symbols_dengan_data_lengkap(df_qf, df_harga), hitung tanggal PALING
    AWAL dari tabel harga yang dibutuhkan supaya peristiwa itu bisa jadi
    baris POSITIF dengan data_complete=1: as_of_date = event_date -
    offset_hari (lihat bangun_baris_positif), lalu jendela harga
    [as_of - mundur_hari_pit - jendela_harga_hari, as_of - mundur_hari_pit]
    (lihat pit.rentang_harga_valid). "harga_awal_dibutuhkan" adalah ujung
    KIRI jendela itu -- tanggal tertua yang harus ada di
    daily_transaction/daily_full_universe_close untuk symbol tsb.

    Dipakai untuk MEMPRIORITASKAN backfill: makin baru event_date-nya,
    makin baru (makin dekat ke hari ini) harga_awal_dibutuhkan-nya,
    makin sedikit riwayat harga yang perlu diambil mundur. Diurutkan
    dari yang paling MURAH dibackfill (harga_awal_dibutuhkan paling
    baru) ke yang paling mahal.

    Kalau satu symbol punya lebih dari satu peristiwa kategori C,
    dipakai event_date PALING BARU (yang paling murah dibackfill).
    Symbol yang sudah masuk symbols_dengan_data_lengkap tidak
    disertakan -- symbol itu sudah tidak perlu diprioritaskan lagi.

    Catatan: fungsi ini HANYA menghitung syarat cakupan tabel harga.
    Bahkan setelah backfill, baris itu masih harus lolos
    batas_label_matang/cutoff_latih (splits.py) untuk benar-benar ikut
    melatih -- lihat README/notebook 02 bagian 4.
    """
    kolom_hasil = [
        "symbol",
        "event_date",
        "sudah_punya_quarterly_financials",
        "sudah_punya_harga",
        "harga_awal_dibutuhkan",
    ]
    if len(df_suspensi_c) == 0:
        return pd.DataFrame(columns=kolom_hasil)

    symbol_qf = set(df_qf["symbol"]) if len(df_qf) else set()
    symbol_harga = set(df_harga["symbol"]) if len(df_harga) else set()
    sudah_lengkap = set(symbols_dengan_data_lengkap(df_qf, df_harga))

    df = df_suspensi_c.copy()
    df["event_date"] = pd.to_datetime(df["event_date"])
    terbaru_per_symbol = df.sort_values("event_date").groupby("symbol", as_index=False).tail(1)
    terbaru_per_symbol = terbaru_per_symbol[~terbaru_per_symbol["symbol"].isin(sudah_lengkap)]

    if len(terbaru_per_symbol) == 0:
        return pd.DataFrame(columns=kolom_hasil)

    hasil = terbaru_per_symbol[["symbol", "event_date"]].copy()
    as_of = hasil["event_date"] - pd.Timedelta(days=offset_hari)
    titik_potong = as_of - pd.Timedelta(days=mundur_hari_pit)
    hasil["harga_awal_dibutuhkan"] = titik_potong - pd.Timedelta(days=jendela_harga_hari)
    hasil["sudah_punya_quarterly_financials"] = hasil["symbol"].isin(symbol_qf)
    hasil["sudah_punya_harga"] = hasil["symbol"].isin(symbol_harga)

    return hasil[kolom_hasil].sort_values("harga_awal_dibutuhkan", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 1. Penggabungan dan pemetaan dari tabel mentah
# ---------------------------------------------------------------------------

def gabungkan_harga(
    daily_transaction: pd.DataFrame, daily_full_universe_close: pd.DataFrame
) -> pd.DataFrame:
    """
    Menggabungkan dua tabel harga (bentuk kolomnya identik: symbol, date,
    close, volume, market_cap) jadi satu time series per symbol.

    Kalau ada baris (symbol, date) yang sama di kedua tabel, baris dari
    daily_transaction dipakai (biasanya lebih detail/lebih akurat),
    daily_full_universe_close mengisi tanggal/simbol yang tidak ada di sana.
    """
    kolom = ["symbol", "date", "close", "volume", "market_cap"]
    dt = daily_transaction[kolom].copy() if len(daily_transaction) else pd.DataFrame(columns=kolom)
    dfu = (
        daily_full_universe_close[kolom].copy()
        if len(daily_full_universe_close)
        else pd.DataFrame(columns=kolom)
    )
    dt["date"] = pd.to_datetime(dt["date"])
    dfu["date"] = pd.to_datetime(dfu["date"])

    gabungan = pd.concat([dt, dfu], ignore_index=True)
    if len(gabungan) == 0:
        return gabungan
    # drop_duplicates menjaga kemunculan PERTAMA -> taruh dt di atas dfu
    # supaya baris dt yang dipertahankan saat (symbol, date) bentrok.
    gabungan = gabungan.drop_duplicates(subset=["symbol", "date"], keep="first")
    return gabungan.sort_values(["symbol", "date"]).reset_index(drop=True)


def bangun_peta_sektor(free_float: pd.DataFrame, company_overview: pd.DataFrame | None = None) -> dict[str, str]:
    """
    symbol -> sector. Prioritas: company_overview.sector (satu nilai
    tetap per simbol) kalau tabel company_overview ada dan terisi;
    kalau tidak/kosong untuk simbol tertentu, didekati dari sub_sector
    snapshot TERBARU di free_float_snapshot (lihat batasan di docstring
    modul ini).
    """
    peta: dict[str, str] = {}
    if len(free_float) and "sub_sector" in free_float.columns:
        ff = free_float.dropna(subset=["sub_sector"]).copy()
        if len(ff):
            ff["snapshot_date"] = pd.to_datetime(ff["snapshot_date"])
            terbaru = ff.sort_values("snapshot_date").groupby("symbol").tail(1)
            peta.update(dict(zip(terbaru["symbol"], terbaru["sub_sector"])))
    if company_overview is not None and len(company_overview) and "sector" in company_overview.columns:
        co = company_overview.dropna(subset=["sector"])
        peta.update(dict(zip(co["symbol"], co["sector"])))  # company_overview menimpa pendekatan free_float
    return peta


def bangun_peta_board(company_overview: pd.DataFrame | None) -> dict[str, str]:
    """
    symbol -> board (papan pencatatan). HANYA dari company_overview --
    tidak ada tabel lain yang punya kolom ini. Mengembalikan dict
    kosong kalau company_overview belum ada/kosong, dan pemanggil jatuh
    kembali ke BOARD_DEFAULT per simbol yang tidak ada di dict ini.
    """
    if company_overview is None or len(company_overview) == 0 or "board" not in company_overview.columns:
        return {}
    co = company_overview.dropna(subset=["board"])
    return dict(zip(co["symbol"], co["board"]))


def bangun_peta_free_float_terkini(free_float: pd.DataFrame) -> dict[str, float]:
    """symbol -> free_float dari snapshot_date TERBARU. Hanya untuk live scoring."""
    if len(free_float) == 0:
        return {}
    ff = free_float.copy()
    ff["snapshot_date"] = pd.to_datetime(ff["snapshot_date"])
    terbaru = ff.sort_values("snapshot_date").groupby("symbol").tail(1)
    return dict(zip(terbaru["symbol"], terbaru["free_float"]))


# ---------------------------------------------------------------------------
# 2. Perhitungan fitur untuk SATU (symbol, as_of_date)
# ---------------------------------------------------------------------------

def hitung_fitur_finansial(
    df_qf_symbol: pd.DataFrame,
    as_of_date: pd.Timestamp,
    *,
    mundur_hari_pit: int = JENDELA_PIT_HARI,
    tenggat_lapor_hari: int = 90,
) -> dict:
    """
    Menghitung lapor_jarak_hari, lapor_terlambat, tanpa_pendapatan,
    ekuitas_negatif, utang_terhadap_aset, ako_negatif_berturut untuk satu
    symbol pada satu as_of_date, dari baris quarterly_financials symbol itu
    saja (df_qf_symbol).

    Kalau tidak ada report_date yang valid (sebelum titik potong
    point-in-time), mengembalikan seluruh fitur finansial sebagai NaN dan
    data_lengkap=False -- BUKAN mengisi nol atau nilai lain secara diam-diam.
    """
    titik_potong = pit.titik_potong(as_of_date, mundur_hari_pit)

    if len(df_qf_symbol) == 0:
        return {
            "lapor_jarak_hari": np.nan,
            "lapor_terlambat": np.nan,
            "tanpa_pendapatan": np.nan,
            "ekuitas_negatif": np.nan,
            "utang_terhadap_aset": np.nan,
            "ako_negatif_berturut": np.nan,
            "feature_max_source_date_finansial": pd.NaT,
            "data_lengkap_finansial": False,
        }

    df = df_qf_symbol.sort_values("report_date")
    tanggal_tersedia = pd.to_datetime(df["report_date"]).tolist()
    report_date_terakhir = pit.pilih_report_date_valid(tanggal_tersedia, titik_potong)

    if report_date_terakhir is None:
        return {
            "lapor_jarak_hari": np.nan,
            "lapor_terlambat": np.nan,
            "tanpa_pendapatan": np.nan,
            "ekuitas_negatif": np.nan,
            "utang_terhadap_aset": np.nan,
            "ako_negatif_berturut": np.nan,
            "feature_max_source_date_finansial": pd.NaT,
            "data_lengkap_finansial": False,
        }

    baris = df[pd.to_datetime(df["report_date"]) == report_date_terakhir].iloc[-1]
    lapor_jarak = feat.hitung_lapor_jarak_hari(as_of_date, report_date_terakhir)

    ocf_berurutan = (
        df[pd.to_datetime(df["report_date"]) <= report_date_terakhir]
        .sort_values("report_date")["operating_cash_flow"]
        .tolist()
    )

    return {
        "lapor_jarak_hari": lapor_jarak,
        "lapor_terlambat": feat.hitung_lapor_terlambat(lapor_jarak, tenggat_lapor_hari),
        "tanpa_pendapatan": feat.hitung_tanpa_pendapatan(baris["revenue"]),
        "ekuitas_negatif": feat.hitung_ekuitas_negatif(baris["total_equity"]),
        "utang_terhadap_aset": feat.hitung_utang_terhadap_aset(
            baris["total_liabilities"], baris["total_assets"]
        ),
        "ako_negatif_berturut": feat.hitung_ako_negatif_berturut(ocf_berurutan),
        "feature_max_source_date_finansial": report_date_terakhir,
        "data_lengkap_finansial": True,
    }


def hitung_fitur_harga(
    df_harga_symbol: pd.DataFrame,
    as_of_date: pd.Timestamp,
    *,
    mundur_hari_pit: int = JENDELA_PIT_HARI,
    jendela_hari: int = JENDELA_HARGA_HARI,
) -> dict:
    """
    Menghitung hari_tanpa_transaksi_90d, rasio_volume_30_90,
    hari_di_batas_bawah_90d, turun_dari_puncak_90d, volatilitas_90d untuk
    satu symbol pada satu as_of_date, dari time series harga symbol itu saja.
    """
    titik_potong = pit.titik_potong(as_of_date, mundur_hari_pit)
    start, end = pit.rentang_harga_valid(titik_potong, jendela_hari)

    if len(df_harga_symbol) == 0:
        jendela = df_harga_symbol
    else:
        tanggal = pd.to_datetime(df_harga_symbol["date"])
        jendela = df_harga_symbol[(tanggal >= start) & (tanggal <= end)]

    if len(jendela) == 0:
        return {
            "hari_tanpa_transaksi_90d": np.nan,
            "rasio_volume_30_90": np.nan,
            "hari_di_batas_bawah_90d": np.nan,
            "turun_dari_puncak_90d": np.nan,
            "volatilitas_90d": np.nan,
            "feature_max_source_date_harga": pd.NaT,
            "data_lengkap_harga": False,
        }

    jendela = jendela.sort_values("date")
    close_seri = pd.Series(jendela["close"].values, index=pd.to_datetime(jendela["date"]))
    volume_seri = pd.Series(jendela["volume"].values, index=pd.to_datetime(jendela["date"]))

    return {
        "hari_tanpa_transaksi_90d": feat.hitung_hari_tanpa_transaksi_90d(volume_seri),
        "rasio_volume_30_90": feat.hitung_rasio_volume_30_90(volume_seri),
        "hari_di_batas_bawah_90d": feat.hitung_hari_di_batas_bawah_90d(close_seri),
        "turun_dari_puncak_90d": feat.hitung_turun_dari_puncak_90d(close_seri),
        "volatilitas_90d": feat.hitung_volatilitas_90d(close_seri),
        "feature_max_source_date_harga": pd.to_datetime(jendela["date"]).max(),
        "data_lengkap_harga": True,
    }


def bangun_baris_fitur(
    symbol: str,
    as_of_date: pd.Timestamp,
    df_qf_by_symbol: dict[str, pd.DataFrame],
    df_harga_by_symbol: dict[str, pd.DataFrame],
) -> dict:
    """
    Menggabungkan hitung_fitur_finansial + hitung_fitur_harga untuk satu
    (symbol, as_of_date), mengembalikan dict siap jadi satu baris panel
    (belum termasuk kolom identitas/label -- itu urusan pemanggil).
    """
    fin = hitung_fitur_finansial(df_qf_by_symbol.get(symbol, pd.DataFrame()), as_of_date)
    harga = hitung_fitur_harga(df_harga_by_symbol.get(symbol, pd.DataFrame()), as_of_date)

    data_complete = int(fin.pop("data_lengkap_finansial") and harga.pop("data_lengkap_harga"))
    tanggal_sumber = [
        t
        for t in [fin.pop("feature_max_source_date_finansial"), harga.pop("feature_max_source_date_harga")]
        if pd.notna(t)
    ]
    feature_max_source_date = max(tanggal_sumber) if tanggal_sumber else pd.NaT

    baris = {**fin, **harga}
    baris["data_complete"] = data_complete
    baris["feature_max_source_date"] = feature_max_source_date
    return baris


# ---------------------------------------------------------------------------
# 3. Perakitan tabel identitas (symbol x as_of_date), lalu tempel fitur
# ---------------------------------------------------------------------------

def _kelompokkan_per_symbol(df: pd.DataFrame, kolom_symbol: str = "symbol") -> dict[str, pd.DataFrame]:
    if len(df) == 0:
        return {}
    return {symbol: grup for symbol, grup in df.groupby(kolom_symbol)}


def tempel_fitur(
    df_identitas: pd.DataFrame,
    df_qf: pd.DataFrame,
    df_harga: pd.DataFrame,
    peta_sektor: dict[str, str],
) -> pd.DataFrame:
    """
    df_identitas wajib punya kolom: symbol, as_of_date, board, is_event_90d,
    event_date, event_category. Fungsi ini menempelkan sector,
    already_flagged, seluruh KOLOM_FITUR, data_complete, dan
    feature_max_source_date, mengembalikan DataFrame yang sudah cocok
    dengan contracts.KOLOM_WAJIB_PANEL.
    """
    df_qf_by_symbol = _kelompokkan_per_symbol(df_qf)
    df_harga_by_symbol = _kelompokkan_per_symbol(df_harga)

    baris_keluaran = []
    for _, ident in df_identitas.iterrows():
        fitur = bangun_baris_fitur(
            ident["symbol"], pd.Timestamp(ident["as_of_date"]), df_qf_by_symbol, df_harga_by_symbol
        )
        baris = dict(ident)
        baris["sector"] = peta_sektor.get(ident["symbol"], "")
        baris.setdefault("already_flagged", 0)
        baris.update(fitur)
        baris_keluaran.append(baris)

    hasil = pd.DataFrame(baris_keluaran)
    for kolom in contracts.KOLOM_WAJIB_PANEL:
        if kolom not in hasil.columns:
            hasil[kolom] = pd.NA
    return hasil[contracts.KOLOM_WAJIB_PANEL]


def bangun_snapshot_pasar(
    tanggal: str | pd.Timestamp,
    symbols: list[str],
    df_qf: pd.DataFrame,
    df_harga: pd.DataFrame,
    peta_sektor: dict[str, str],
    *,
    board_default: str = BOARD_DEFAULT,
    peta_board: dict[str, str] | None = None,
    df_suspensi_c: pd.DataFrame | None = None,
    taksonomi: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """
    Membangun satu potret uji: seluruh symbols pada satu as_of_date.

    Kalau df_suspensi_c diberikan (hasil klasifikasi kategori C dari
    tabel stock_suspensions asli), label is_event_90d dihitung SUNGGUHAN
    lewat labels.bentuk_label_is_event_90d. Kalau None (mis. dipakai
    untuk scoring hari ini di notebook 05, bukan evaluasi historis),
    seluruh baris diberi is_event_90d=0 sebagai PLACEHOLDER -- potret ini
    valid untuk memeriksa nilai indikator pada data pasar asli, TAPI
    TIDAK VALID untuk Precision@20 atau metrik evaluasi apa pun.

    peta_board (biasanya dari bangun_peta_board) diprioritaskan per
    simbol; board_default hanya dipakai untuk simbol yang tidak ada di
    peta_board (mis. company_overview belum mencakup simbol itu).
    """
    as_of = pd.Timestamp(tanggal)
    peta_board = peta_board or {}
    df_cakupan = pd.DataFrame(
        {
            "symbol": symbols,
            "as_of_date": as_of,
            "board": [peta_board.get(s, board_default) for s in symbols],
        }
    )

    if df_suspensi_c is not None and len(df_suspensi_c) > 0:
        df_cakupan = labels.bentuk_label_is_event_90d(
            df_suspensi_c, df_cakupan, taksonomi=taksonomi, kolom_alasan="reason"
        )
    else:
        df_cakupan["is_event_90d"] = 0
        df_cakupan["event_date"] = pd.NaT
        df_cakupan["event_category"] = ""

    return tempel_fitur(df_cakupan, df_qf, df_harga, peta_sektor)


def bangun_riwayat_fitur_historis(
    symbol: str,
    tanggal_list: list[pd.Timestamp],
    df_qf: pd.DataFrame,
    df_harga: pd.DataFrame,
) -> pd.DataFrame:
    """
    Untuk SATU symbol, menghitung satu baris fitur (KOLOM_FITUR) pada
    setiap tanggal di tanggal_list, dari data mentah sungguhan. Dipakai
    notebook 04 untuk merekonstruksi riwayat skor historis sungguhan
    menjelang satu peristiwa -- pemanggil (notebook 04) yang menempelkan
    skor lewat models.skor_kandidat_1 pada hasil fungsi ini, karena
    fungsi ini sendiri tidak tahu apa-apa tentang model.

    Baris dengan data_complete=0 (tidak ada laporan/harga valid pada
    tanggal itu) tetap disertakan apa adanya -- pemanggil yang
    memutuskan mau memfilternya atau tidak.
    """
    df_qf_symbol = df_qf[df_qf["symbol"] == symbol] if len(df_qf) else df_qf
    df_harga_symbol = df_harga[df_harga["symbol"] == symbol] if len(df_harga) else df_harga
    df_qf_by_symbol = {symbol: df_qf_symbol}
    df_harga_by_symbol = {symbol: df_harga_symbol}

    baris_list = []
    for tanggal in tanggal_list:
        fitur = bangun_baris_fitur(symbol, pd.Timestamp(tanggal), df_qf_by_symbol, df_harga_by_symbol)
        fitur["tanggal"] = pd.Timestamp(tanggal)
        baris_list.append(fitur)
    return pd.DataFrame(baris_list)


def bangun_grid_kandidat_bulanan(
    symbols: list[str],
    tanggal_mulai: pd.Timestamp,
    tanggal_akhir: pd.Timestamp,
    *,
    board_default: str = BOARD_DEFAULT,
    peta_board: dict[str, str] | None = None,
    kecualikan_tanggal: list[str] | None = None,
    batas_akhir_as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Grid kandidat (symbol, as_of_date, board) pada tanggal 15 tiap bulan
    antara tanggal_mulai dan tanggal_akhir, dipakai sebagai df_cakupan
    untuk mencari sampel negatif (sampling.py). kecualikan_tanggal
    (biasanya tanggal potret evaluasi dari splits.hitung_jendela_bergulir)
    dibuang dari grid supaya baris latih negatif tidak pernah identik
    dengan baris potret uji.

    batas_akhir_as_of, kalau diisi (biasanya splits.batas_label_matang
    (sekarang)), memotong tanggal_akhir supaya grid TIDAK PERNAH memuat
    as_of_date yang jendela 90 harinya belum lewat -- baris seperti itu
    belum bisa diberi label negatif dengan benar karena kita sendiri
    belum tahu apakah sesuatu akan terjadi di 90 hari berikutnya
    (tersensor ke kanan).
    """
    if batas_akhir_as_of is not None:
        tanggal_akhir = min(pd.Timestamp(tanggal_akhir), pd.Timestamp(batas_akhir_as_of))

    tanggal_list = pd.date_range(tanggal_mulai, tanggal_akhir, freq="MS") + pd.Timedelta(days=14)
    kecualikan = {pd.Timestamp(t) for t in (kecualikan_tanggal or [])}
    tanggal_list = [t for t in tanggal_list if t not in kecualikan]

    if not tanggal_list or not symbols:
        return pd.DataFrame(columns=["symbol", "as_of_date", "board"])

    grid = pd.MultiIndex.from_product([symbols, tanggal_list], names=["symbol", "as_of_date"]).to_frame(
        index=False
    )
    peta_board = peta_board or {}
    grid["board"] = grid["symbol"].map(lambda s: peta_board.get(s, board_default))
    return grid


def bangun_baris_positif(
    df_suspensi_c: pd.DataFrame,
    *,
    offset_hari: int = OFFSET_AS_OF_DARI_EVENT_HARI,
    board_default: str = BOARD_DEFAULT,
    peta_board: dict[str, str] | None = None,
) -> pd.DataFrame:
    """
    Untuk tiap peristiwa kategori C, satu baris positif dengan as_of_date
    = event_date - offset_hari (default titik tengah jendela 90 hari),
    supaya baris ini benar-benar berada di dalam jendela 90 hari sebelum
    peristiwa (syarat is_event_90d=1).
    """
    if len(df_suspensi_c) == 0:
        return pd.DataFrame(
            columns=["symbol", "as_of_date", "board", "is_event_90d", "event_date", "event_category"]
        )

    peta_board = peta_board or {}
    hasil = df_suspensi_c[["symbol", "event_date"]].copy()
    hasil["event_date"] = pd.to_datetime(hasil["event_date"])
    hasil["as_of_date"] = hasil["event_date"] - pd.Timedelta(days=offset_hari)
    hasil["board"] = hasil["symbol"].map(lambda s: peta_board.get(s, board_default))
    hasil["is_event_90d"] = 1
    hasil["event_category"] = "C"
    return hasil[["symbol", "as_of_date", "board", "is_event_90d", "event_date", "event_category"]]


def bangun_panel_latih(
    df_suspensi_raw: pd.DataFrame,
    symbols_universe: list[str],
    df_qf: pd.DataFrame,
    df_harga: pd.DataFrame,
    peta_sektor: dict[str, str],
    *,
    taksonomi: dict[str, list[str]] | None = None,
    board_default: str = BOARD_DEFAULT,
    peta_board: dict[str, str] | None = None,
    rasio_negatif: int = sampling.RASIO_NEGATIF_PER_POSITIF,
    kecualikan_tanggal: list[str] | None = None,
    batas_akhir_as_of: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Alur lengkap: klasifikasi suspensi -> baris positif -> sampel negatif
    -> tempel fitur -> panel siap disimpan ke data/panel.csv.

    batas_akhir_as_of diteruskan ke bangun_grid_kandidat_bulanan supaya
    kandidat negatif tidak pernah memakai as_of_date yang labelnya belum
    matang -- lihat catatan di sana. Biasanya diisi
    splits.batas_label_matang(sekarang) oleh pemanggil (notebook 02).

    Mengembalikan (panel, ringkasan) supaya pemanggil bisa mencetak
    berapa banyak positif/negatif tanpa membaca ulang DataFrame.
    """
    taksonomi = taksonomi or labels.muat_taksonomi()

    df_suspensi_raw = df_suspensi_raw.copy()
    df_suspensi_raw["event_category"] = df_suspensi_raw["reason"].apply(
        lambda a: labels.klasifikasi_alasan(a, taksonomi)
    )
    df_suspensi_c = df_suspensi_raw[df_suspensi_raw["event_category"] == labels.KATEGORI_LABEL_POSITIF]

    ringkasan = {
        "total_suspensi_mentah": int(len(df_suspensi_raw)),
        "total_kategori_c": int(len(df_suspensi_c)),
        "tak_terklasifikasi": int(df_suspensi_raw["event_category"].isna().sum()),
    }

    df_positif_identitas = bangun_baris_positif(df_suspensi_c, board_default=board_default, peta_board=peta_board)

    if len(df_positif_identitas) == 0:
        return pd.DataFrame(columns=contracts.KOLOM_WAJIB_PANEL), ringkasan

    tanggal_mulai = df_positif_identitas["as_of_date"].min() - pd.Timedelta(days=180)
    tanggal_akhir = df_positif_identitas["as_of_date"].max() + pd.Timedelta(days=180)
    df_cakupan_grid = bangun_grid_kandidat_bulanan(
        symbols_universe,
        tanggal_mulai,
        tanggal_akhir,
        board_default=board_default,
        peta_board=peta_board,
        kecualikan_tanggal=kecualikan_tanggal,
        batas_akhir_as_of=batas_akhir_as_of,
    )

    identitas_lengkap = sampling.bentuk_sampel_pembanding(
        df_positif_identitas,
        df_cakupan_grid,
        df_suspensi_c.rename(columns={"reason": "reason"}),
        rasio=rasio_negatif,
    )

    panel = tempel_fitur(identitas_lengkap, df_qf, df_harga, peta_sektor)
    ringkasan["baris_panel"] = int(len(panel))
    ringkasan["positif_panel"] = int(panel["is_event_90d"].sum())
    return panel, ringkasan


__all__ = [
    "BOARD_DEFAULT",
    "diagnosa_cakupan_mentah",
    "symbols_dengan_data_lengkap",
    "prioritas_backfill_kategori_c",
    "gabungkan_harga",
    "bangun_peta_sektor",
    "bangun_peta_board",
    "bangun_peta_free_float_terkini",
    "hitung_fitur_finansial",
    "hitung_fitur_harga",
    "bangun_baris_fitur",
    "bangun_riwayat_fitur_historis",
    "tempel_fitur",
    "bangun_snapshot_pasar",
    "bangun_grid_kandidat_bulanan",
    "bangun_baris_positif",
    "bangun_panel_latih",
]
