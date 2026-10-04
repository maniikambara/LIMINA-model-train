"""
sectors_fetcher/service.py
==========================

Layanan Produksi LIMINA (Production Scoring & Preprocessing Service).

Modul ini dirancang untuk dapat digunakan ulang (reusable) di lingkungan produksi,
backend API (FastAPI/Flask/Next.js), atau batch worker terjadwal:
1. Menghubungkan ke database Supabase untuk menarik data mentah terbaru.
2. Melakukan preprocessing point-in-time bebas dari data leakage untuk data baru.
3. Menghitung seluruh 11 indikator risiko turunan (Kamus Variabel LIMINA Bagian 3).
4. Menjalankan inferensi model ML terlatih (Random Forest / Logistic Regression).
5. Menghasilkan output scoring resmi (skor, persentil, kategori, arah_30h, status,
   indikator_dominan, kontribusi) yang siap disimpan ke database atau scores.json.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from . import config, supabase_io

logger = logging.getLogger("amba_service")

# 11 Indikator Risiko Turunan Resmi (LIMINA Kamus Variabel Bagian 3)
_INDIKATOR_RISIKO_11 = [
    "lapor_jarak_hari",
    "lapor_terlambat",
    "tanpa_pendapatan",
    "ekuitas_negatif",
    "utang_terhadap_aset",
    "ako_negatif_berturut",
    "hari_tanpa_transaksi_90d",
    "rasio_volume_30_90",
    "hari_di_batas_bawah_90d",
    "turun_dari_puncak_90d",
    "volatilitas_90d",
]

# 3 rasio tambahan yang ikut dipakai saat training (lihat README: "14 fitur").
_RASIO_TAMBAHAN_3 = ["earnings_margin", "fcf_margin", "ocf_to_debt"]

# Seluruh fitur model (14). Urutan HARUS sama dengan saat fit; scikit-learn
# memeriksa nama DAN urutan kolom lewat feature_names_in_. Daftar ini hanya
# fallback -- saat inferensi, daftar sebenarnya dibaca dari model yang dimuat
# (lihat LiminaScoringService._feature_cols).
RISK_FEATURE_COLS = _INDIKATOR_RISIKO_11 + _RASIO_TAMBAHAN_3

# Path default artefak model
OUTPUT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "output"))
DEFAULT_MODEL_PATH = os.path.join(OUTPUT_DIR, "model_random_forest.joblib")  # fallback lama
DEFAULT_LR_PATH = os.path.join(OUTPUT_DIR, "model_lr_balanced.joblib")
BACKTEST_PATH = os.path.join(OUTPUT_DIR, "backtest.json")
PRODUCTION_MODEL_PATH = os.path.join(OUTPUT_DIR, "model_produksi.joblib")

# Nama di backtest.json["model_selected"] (= `best_model_name` di
# modeling_and_evaluation.ipynb) -> berkas artefak yang disimpan notebook itu.
MODEL_FILE_BY_NAME = {
    "baseline logistic regression": "model_baseline_lr.joblib",
    "logistic regression (balanced)": "model_lr_balanced.joblib",
    "random forest (balanced bootstrap)": "model_random_forest.joblib",
    "blend lr+rf": "model_blend.joblib",
}


def resolve_model_path(
    output_dir: str = OUTPUT_DIR,
) -> tuple[str, str | None]:
    """
    Tentukan model produksi. Mengembalikan (path, nama_model_terpilih).

    Urutan prioritas:
      1. env LIMINA_MODEL_PATH (override manual, mis. untuk uji/rollback);
      2. `model_selected` di output/backtest.json -> berkas modelnya;
      3. output/model_produksi.joblib (disimpan notebook = model_terpilih);
      4. output/model_random_forest.joblib (perilaku lama).
    """
    override = os.environ.get("LIMINA_MODEL_PATH")
    if override:
        return os.path.normpath(override), None

    selected: str | None = None
    backtest_file = os.path.join(output_dir, "backtest.json")
    try:
        with open(backtest_file, encoding="utf-8") as f:
            selected = json.load(f).get("model_selected")
    except (OSError, ValueError) as exc:
        logger.warning("backtest.json tidak bisa dibaca (%s); pakai model_produksi.joblib", exc)

    if isinstance(selected, str):
        fname = MODEL_FILE_BY_NAME.get(selected.strip().casefold())
        if fname is None:
            logger.warning(
                "model_selected=%r tidak dikenal di MODEL_FILE_BY_NAME; pakai model_produksi.joblib",
                selected,
            )
        else:
            candidate = os.path.join(output_dir, fname)
            if os.path.exists(candidate):
                return candidate, selected
            logger.warning("Berkas %s untuk model_selected=%r tidak ada", candidate, selected)

    for fallback in ("model_produksi.joblib", "model_random_forest.joblib"):
        candidate = os.path.join(output_dir, fallback)
        if os.path.exists(candidate):
            return candidate, selected
    # Tidak ada satu pun: kembalikan path utama supaya FileNotFoundError (-> 503) jelas.
    return os.path.join(output_dir, "model_produksi.joblib"), selected


def normalize_symbol(symbol: str) -> str:
    """Normalisasi simbol menjadi format standar uppercase dengan suffix .JK."""
    s = symbol.strip().upper()
    return s if s.endswith(".JK") else f"{s}.JK"


def classify_suspension_reason(reason_text: str | None) -> str:
    """Klasifikasi alasan suspensi BEI ke dalam Taksonomi LIMINA (A, B, C)."""
    if not isinstance(reason_text, str) or not reason_text.strip():
        return "Unknown"
    r = reason_text.lower()
    cat_c_keywords = [
        "suspend more than 6 month",
        "laporan keuangan auditan",
        "kelangsungan usaha",
        "going concern",
        "peraturan bursa",
        "pemantauan khusus selama lebih dari 1",
        "biaya pencatatan",
        "pkpu",
        "pailit",
        "keterlambatan pembayaran",
        "meragukan",
    ]
    for kw in cat_c_keywords:
        if kw in r:
            return "C"
    if "penurunan harga" in r:
        return "B"
    if any(k in r for k in ["peningkatan harga", "cooling down", "perlindungan bagi investor", "uma"]):
        return "A"
    return "C"


def preprocess_single_ticker(
    symbol: str,
    as_of_date: date,
    df_qf: pd.DataFrame,
    df_dt: pd.DataFrame,
    df_ff: pd.DataFrame,
    df_co: pd.DataFrame,
    df_sus: pd.DataFrame | None = None,
    sertakan_free_float: bool = True,
) -> dict[str, Any]:
    """
    Eksekusi preprocessing Point-in-Time untuk satu emiten pada as_of_date tertentu.
    Mencegah kebocoran data dengan memastikan hanya data pada atau sebelum as_of_date
    yang diikutsertakan dalam pembentukan fitur.
    """
    sym = normalize_symbol(symbol)
    as_of_dt = pd.to_datetime(as_of_date)
    window_90d_start = as_of_dt - pd.Timedelta(days=90)
    window_30d_start = as_of_dt - pd.Timedelta(days=30)

    # 1. Identitas Emiten
    ov = df_co[df_co["symbol"] == sym] if (df_co is not None and not df_co.empty) else pd.DataFrame()
    company_name = ov["company_name"].iloc[0] if not ov.empty else sym
    sector = ov["sector"].iloc[0] if not ov.empty else None
    sub_sector = ov["sub_sector"].iloc[0] if not ov.empty else None
    board = ov["board"].iloc[0] if not ov.empty else None

    # 2. Laporan Keuangan Kuartalan (report_date <= as_of_date)
    source_dates = []
    qf = df_qf[(df_qf["symbol"] == sym) & (pd.to_datetime(df_qf["report_date"]) <= as_of_dt)] if (df_qf is not None and not df_qf.empty) else pd.DataFrame()
    if not qf.empty:
        qf = qf.sort_values("report_date")
        latest_qf = qf.iloc[-1]
        last_rep_date = pd.to_datetime(latest_qf["report_date"]).date()
        source_dates.append(last_rep_date)

        rev = float(latest_qf["revenue"]) if pd.notna(latest_qf.get("revenue")) else None
        eq = float(latest_qf["total_equity"]) if pd.notna(latest_qf.get("total_equity")) else None
        liab = float(latest_qf["total_liabilities"]) if pd.notna(latest_qf.get("total_liabilities")) else None
        asset = float(latest_qf["total_assets"]) if pd.notna(latest_qf.get("total_assets")) else None

        lapor_jarak_hari = (as_of_date - last_rep_date).days
        lapor_terlambat = int(lapor_jarak_hari > config.LAPOR_TENGGAT_HARI)
        tanpa_pendapatan = int(rev <= config.REVENUE_MENDEKATI_NOL) if rev is not None else 0
        ekuitas_negatif = int(eq < 0) if eq is not None else 0
        utang_terhadap_aset = (liab / asset) if (liab is not None and asset is not None and asset != 0) else None

        # Streak OCF negatif
        ocf_list = qf["operating_cash_flow"].dropna().tolist() if "operating_cash_flow" in qf.columns else []
        streak = 0
        for v in reversed(ocf_list):
            if v < 0:
                streak += 1
            else:
                break
        ako_negatif_berturut = streak

        # Rasio tambahan -- definisi identik dengan eda_and_feature_engineering.ipynb
        # (sel 4.1) supaya tidak ada train/serve skew. None (bukan 0) kalau
        # penyebut nol/tidak valid; SimpleImputer di dalam pipeline model yang
        # mengisinya, persis seperti saat training.
        def _num(kolom: str) -> float | None:
            v = latest_qf.get(kolom)
            return float(v) if pd.notna(v) else None

        earnings = _num("earnings")
        total_debt = _num("total_debt")
        ocf = _num("operating_cash_flow")
        fcf = _num("free_cash_flow")

        earnings_margin = (earnings / rev) if (earnings is not None and rev not in (None, 0)) else None
        fcf_margin = (fcf / rev) if (fcf is not None and rev not in (None, 0)) else None
        ocf_to_debt = (ocf / total_debt) if (ocf is not None and total_debt not in (None, 0)) else None
    else:
        last_rep_date = None
        lapor_jarak_hari = None
        lapor_terlambat = None
        tanpa_pendapatan = None
        ekuitas_negatif = None
        utang_terhadap_aset = None
        ako_negatif_berturut = None
        earnings_margin = None
        fcf_margin = None
        ocf_to_debt = None

    # 3. Transaksi Harian (date <= as_of_date)
    dt = df_dt[(df_dt["symbol"] == sym) & (pd.to_datetime(df_dt["date"]) <= as_of_dt)] if (df_dt is not None and not df_dt.empty) else pd.DataFrame()
    if not dt.empty:
        dt = dt.sort_values("date")
        dt_dates = pd.to_datetime(dt["date"])
        dt_90d = dt[(dt_dates > window_90d_start) & (dt_dates <= as_of_dt)]
        dt_30d = dt[(dt_dates > window_30d_start) & (dt_dates <= as_of_dt)]

        if not dt_90d.empty:
            latest_dt = dt_90d.iloc[-1]
            source_dates.append(pd.to_datetime(latest_dt["date"]).date())
            close_now = float(latest_dt["close"]) if pd.notna(latest_dt.get("close")) else None

            hari_tanpa_transaksi_90d = int((dt_90d["volume"].fillna(0) == 0).sum())
            hari_di_batas_bawah_90d = int((dt_90d["close"] == config.HARGA_BATAS_BAWAH).sum())

            avg_vol_90 = dt_90d["volume"].mean()
            avg_vol_30 = dt_30d["volume"].mean() if not dt_30d.empty else None
            rasio_volume_30_90 = (float(avg_vol_30) / float(avg_vol_90)) if (avg_vol_30 is not None and avg_vol_90 and avg_vol_90 > 0) else 1.0

            close_max_90 = dt_90d["close"].max()
            turun_dari_puncak_90d = float((close_max_90 - close_now) / close_max_90) if (pd.notna(close_max_90) and close_max_90 > 0 and close_now is not None) else 0.0

            rets = dt_90d["close"].pct_change().dropna()
            volatilitas_90d = float(rets.std()) if len(rets) >= 2 else 0.0
        else:
            hari_tanpa_transaksi_90d = hari_di_batas_bawah_90d = rasio_volume_30_90 = turun_dari_puncak_90d = volatilitas_90d = None
    else:
        hari_tanpa_transaksi_90d = hari_di_batas_bawah_90d = rasio_volume_30_90 = turun_dari_puncak_90d = volatilitas_90d = None

    # 4. Struktur Kepemilikan (Free Float Snapshot)
    ff = df_ff[(df_ff["symbol"] == sym) & (pd.to_datetime(df_ff["snapshot_date"]) <= as_of_dt)] if (df_ff is not None and not df_ff.empty) else pd.DataFrame()
    if sertakan_free_float and not ff.empty:
        latest_ff = ff.sort_values("snapshot_date").iloc[-1]
        raw_ff = float(latest_ff["free_float"]) if pd.notna(latest_ff.get("free_float")) else None
        free_float_rendah = int(raw_ff < (config.FREE_FLOAT_RENDAH_AMBANG_PERSEN / 100.0)) if raw_ff is not None else None
    else:
        raw_ff = free_float_rendah = None

    # 5. Kontrol Status & Audit Kebocoran
    already_flagged = 0
    if df_sus is not None and not df_sus.empty:
        prior_sus = df_sus[(df_sus["symbol"] == sym) & (pd.to_datetime(df_sus["event_date"]) <= as_of_dt)]
        if not prior_sus.empty and (board == "Watchlist" or (as_of_dt - pd.to_datetime(prior_sus["event_date"].max())).days <= 180):
            already_flagged = 1
    if board == "Watchlist":
        already_flagged = 1

    feature_max_source_date = max(source_dates) if source_dates else None
    inti_features = [lapor_jarak_hari, utang_terhadap_aset, hari_tanpa_transaksi_90d, volatilitas_90d]
    data_complete = int(all(v is not None for v in inti_features))

    return {
        "symbol": sym,
        "company_name": company_name,
        "as_of_date": as_of_date.isoformat(),
        "sector": sector,
        "sub_sector": sub_sector,
        "board": board,
        "already_flagged": already_flagged,
        "data_complete": data_complete,
        "feature_max_source_date": feature_max_source_date.isoformat() if feature_max_source_date else None,
        # 11 Indikator Risiko
        "lapor_jarak_hari": lapor_jarak_hari,
        "lapor_terlambat": lapor_terlambat,
        "tanpa_pendapatan": tanpa_pendapatan,
        "ekuitas_negatif": ekuitas_negatif,
        "utang_terhadap_aset": utang_terhadap_aset,
        "ako_negatif_berturut": ako_negatif_berturut,
        "hari_tanpa_transaksi_90d": hari_tanpa_transaksi_90d,
        "rasio_volume_30_90": rasio_volume_30_90,
        "hari_di_batas_bawah_90d": hari_di_batas_bawah_90d,
        "turun_dari_puncak_90d": turun_dari_puncak_90d,
        "volatilitas_90d": volatilitas_90d,
        # 3 Rasio tambahan (fitur ke-12..14 model)
        "earnings_margin": earnings_margin,
        "fcf_margin": fcf_margin,
        "ocf_to_debt": ocf_to_debt,
        "free_float_rendah": free_float_rendah,
    }


class LiminaScoringService:
    """
    Service terintegrasi untuk menarik data baru dari database Supabase,
    menjalankan preprocessing, inferensi model machine learning, dan menghasilkan
    output scoring sesuai Kamus Variabel LIMINA Bagian 4.
    """

    def __init__(
        self,
        storage: SupabaseStorage | None = None,
        model_path: str | None = None,
        lr_model_path: str = DEFAULT_LR_PATH,
    ):
        self.storage = storage or self._default_storage()
        # model_path=None -> pilih otomatis dari output/backtest.json.
        if model_path is None:
            self.model_path, self.model_selected = resolve_model_path()
        else:
            self.model_path, self.model_selected = os.path.normpath(model_path), None
        self.lr_model_path = lr_model_path
        self._model: Any = None
        self._lr_pipeline: Any = None
        self._feature_cols: list[str] = list(RISK_FEATURE_COLS)

    @staticmethod
    def _default_storage() -> SupabaseStorage:
        """Import SupabaseStorage hanya saat benar dibutuhkan (bukan saat
        modul ini di-import) -- sectors_fetcher/storage/ belum ada di
        checkout ini. Beri RuntimeError yang jelas di sini, bukan biarkan
        ModuleNotFoundError membingungkan menyusul saat `import sectors_fetcher`."""
        try:
            from .storage.supabase_client import SupabaseStorage as _Storage
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "LiminaScoringService butuh koneksi Supabase tapi "
                "sectors_fetcher/storage/ tidak ada di checkout ini. "
                "Sediakan instance storage sendiri lewat parameter `storage=`, "
                "atau lengkapi paket storage/ terlebih dahulu."
            ) from exc
        return _Storage()

    @staticmethod
    def _members(model: Any) -> list[Any]:
        """Anggota ensemble (BlendedClassifier.fitted_), atau [] kalau model tunggal."""
        return [est for _, est in getattr(model, "fitted_", [])]

    @classmethod
    def _model_feature_names(cls, model: Any) -> list[str] | None:
        """Nama fitur saat fit. BlendedClassifier tidak punya feature_names_in_
        sendiri -- ambil dari anggota pertamanya."""
        for kandidat in [model, *cls._members(model)]:
            nama = getattr(kandidat, "feature_names_in_", None)
            if nama is not None:
                return [str(n) for n in nama]
        return None

    def _ensure_models_loaded(self) -> None:
        """Lazy load model ML."""
        if self._model is None:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Model file tidak ditemukan di {self.model_path}")
            self._model = joblib.load(self.model_path)
            logger.info(
                "Model %s (%s) loaded dari %s",
                self.model_selected or "tanpa-nama",
                type(self._model).__name__,
                self.model_path,
            )
            # Sumber kebenaran daftar fitur = model itu sendiri, bukan konstanta
            # di sini. Dengan begitu retrain dengan fitur baru tidak lagi
            # memecahkan /scores diam-diam.
            nama_fit = self._model_feature_names(self._model)
            if nama_fit is not None:
                self._feature_cols = nama_fit

        if self._lr_pipeline is None:
            if os.path.exists(self.lr_model_path):
                self._lr_pipeline = joblib.load(self.lr_model_path)
                logger.info("Logistic Regression pipeline loaded dari %s", self.lr_model_path)
            else:
                # Tanpa berkas LR terpisah, pakai LR tertuning yang sudah ada di
                # dalam blend (nama "lr_balanced") sebagai proksi penjelas.
                for nama, est in getattr(self._model, "fitted_", []):
                    if nama == "lr_balanced":
                        self._lr_pipeline = est
                        break

    @property
    def model_loaded(self) -> bool:
        return self._model is not None

    def load_all_raw_data(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Tarik semua tabel mentah dari Supabase."""
        logger.info("Mengambil data mentah dari Supabase...")
        df_qf = pd.DataFrame(self.storage.select_all("quarterly_financials"))
        df_dt = pd.DataFrame(self.storage.select_all("daily_transaction"))
        df_ff = pd.DataFrame(self.storage.select_all("free_float_snapshot"))
        df_sus = pd.DataFrame(self.storage.select_all("stock_suspensions"))
        if not df_sus.empty:
            # Tabel mentah bisa memakai nama kolom tanggal/alasan berbeda
            # (config.KOLOM_TANGGAL_SUSPENSI/KOLOM_ALASAN_SUSPENSI) --
            # 01_ambil_data.ipynb sudah menyamakan ini lewat fungsi yang
            # sama; service.py perlu memanggilnya sendiri karena jalur ini
            # (API live) tidak lewat notebook itu.
            df_sus = supabase_io.normalisasi_tabel_suspensi(df_sus)
        df_co = pd.DataFrame(self.storage.select_all("company_overview"))
        return df_qf, df_dt, df_ff, df_sus, df_co

    def preprocess_universe(
        self,
        tickers: list[str] | None = None,
        as_of_date: date | None = None,
        raw_tables: tuple | None = None,
    ) -> pd.DataFrame:
        """
        Lakukan preprocessing point-in-time untuk seluruh ticker atau daftar tertentu.
        """
        as_of_date = as_of_date or date.today()
        if raw_tables is None:
            df_qf, df_dt, df_ff, df_sus, df_co = self.load_all_raw_data()
        else:
            df_qf, df_dt, df_ff, df_sus, df_co = raw_tables

        if tickers is None:
            if not df_co.empty:
                tickers = df_co["symbol"].unique().tolist()
            else:
                tickers = config.DEFAULT_TICKERS

        rows = []
        for ticker in tickers:
            row = preprocess_single_ticker(
                symbol=ticker,
                as_of_date=as_of_date,
                df_qf=df_qf,
                df_dt=df_dt,
                df_ff=df_ff,
                df_co=df_co,
                df_sus=df_sus,
                sertakan_free_float=True,
            )
            rows.append(row)

        return pd.DataFrame(rows)

    def score_features_dataframe(
        self,
        df_features: pd.DataFrame,
        historical_df_prev: pd.DataFrame | None = None,
    ) -> list[dict[str, Any]]:
        """
        Hitung skor, persentil, kategori, arah_30h, status, indikator dominan,
        dan kontribusi dari dataframe fitur hasil preprocessing.
        """
        self._ensure_models_loaded()
        df_calc = df_features.copy().reset_index(drop=True)

        feature_cols = self._feature_cols
        kolom_hilang = [c for c in feature_cols if c not in df_calc.columns]
        if kolom_hilang:
            raise ValueError(
                f"Fitur yang dibutuhkan model tidak dihasilkan preprocessing: {kolom_hilang}. "
                "Tambahkan perhitungannya di preprocess_single_ticker()."
            )

        # Kirim NaN apa adanya: SimpleImputer di dalam pipeline model sudah
        # fit pada data training, jadi imputasinya konsisten dengan training
        # (bukan median batch request, yang berubah-ubah tiap panggilan).
        # Urutan kolom wajib sama dengan saat fit.
        X_input = df_calc[feature_cols].apply(pd.to_numeric, errors="coerce").astype(float)

        # 1. Probabilitas Risiko (Skor mentah)
        probs = self._model.predict_proba(X_input)[:, 1]
        df_calc["skor"] = np.round(probs, 4)

        # 2. Persentil (0 - 100)
        df_calc["persentil"] = np.round(df_calc["skor"].rank(pct=True) * 100, 1)

        # 3. Kategori Risiko
        def _to_category(p: float) -> str:
            if p >= 90.0:
                return "Sangat Tinggi"
            elif p >= 75.0:
                return "Tinggi"
            elif p >= 50.0:
                return "Sedang"
            return "Rendah"

        df_calc["kategori"] = df_calc["persentil"].apply(_to_category)

        # 4. Status (Aturan isolasi already_flagged)
        def _to_status(row: pd.Series) -> str:
            if row.get("data_complete", 1) == 0:
                return "tidak_dapat_dinilai"
            elif row.get("already_flagged", 0) == 1:
                return "sudah_ditandai"
            return "dinilai"

        df_calc["status"] = df_calc.apply(_to_status, axis=1)

        # 5. Arah Tren 30 Hari (arah_30h)
        prev_map: dict[str, float] = {}
        if historical_df_prev is not None and not historical_df_prev.empty:
            if "persentil" in historical_df_prev.columns:
                prev_map = dict(zip(historical_df_prev["symbol"], historical_df_prev["persentil"]))

        def _to_direction(row: pd.Series) -> str:
            sym = row["symbol"]
            curr_pct = row["persentil"]
            if sym in prev_map:
                diff = curr_pct - prev_map[sym]
                if diff > 5.0:
                    return "naik"
                elif diff < -5.0:
                    return "turun"
            return "stabil"

        df_calc["arah_30h"] = df_calc.apply(_to_direction, axis=1)

        # 6. Kontribusi Fitur & Indikator Dominan
        if self._lr_pipeline is not None:
            steps = self._lr_pipeline.named_steps
            # Pipeline LR: imputer -> scaler -> clf. Imputer harus dijalankan
            # dulu, kalau tidak NaN menjalar ke kontribusi.
            # Imputer di-fit dengan nama kolom -> beri DataFrame. Scaler di-fit
            # tanpa nama kolom -> beri ndarray. Kalau tertukar, sklearn
            # mengeluarkan UserWarning "X does not have valid feature names".
            X_imp = steps["imputer"].transform(X_input) if "imputer" in steps else X_input
            X_scaled = steps["scaler"].transform(np.asarray(X_imp))
            coefs = steps["clf"].coef_[0]
            contribs = X_scaled * coefs
        else:
            # Fallback jika tidak ada LR sama sekali: nilai terimputasi x importance.
            # Model bisa Pipeline (imputer -> clf), BlendedClassifier, atau
            # estimator polos -- ambil imputer & importance dari yang tersedia.
            steps = getattr(self._model, "named_steps", {})
            anggota = self._members(self._model)
            sumber = anggota[0] if (not steps and anggota) else self._model
            steps_imp = getattr(sumber, "named_steps", {})
            X_imp = steps_imp["imputer"].transform(X_input) if "imputer" in steps_imp else X_input.fillna(0)
            inti = steps.get("clf", self._model)
            if hasattr(inti, "feature_importances_"):
                bobot = inti.feature_importances_
            else:  # mis. model linear: pakai koefisien
                bobot = inti.coef_[0]
            contribs = np.asarray(X_imp) * bobot

        scores_payload = []
        for i, row in df_calc.iterrows():
            row_contrib = dict(zip(feature_cols, np.round(contribs[i], 4)))
            pos_contrib = {k: v for k, v in row_contrib.items() if v > 0}
            dominant = max(pos_contrib, key=pos_contrib.get) if pos_contrib else max(row_contrib, key=row_contrib.get)

            scores_payload.append({
                "symbol": row["symbol"],
                "company_name": row.get("company_name", row["symbol"]),
                "as_of_date": row["as_of_date"],
                "sector": row.get("sector"),
                "sub_sector": row.get("sub_sector"),
                "board": row.get("board"),
                "skor": float(row["skor"]),
                "persentil": float(row["persentil"]),
                "kategori": row["kategori"],
                "arah_30h": row["arah_30h"],
                "status": row["status"],
                "indikator_dominan": dominant,
                "kontribusi": row_contrib,
            })

        # Urutkan berdasarkan persentil tertinggi
        scores_payload.sort(key=lambda x: x["persentil"], reverse=True)
        return scores_payload

    def score_latest_universe(
        self,
        tickers: list[str] | None = None,
        as_of_date: date | None = None,
        export_json_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Pipeline lengkap end-to-end untuk produksi:
        Ingesti database -> Preprocessing PIT -> Inferensi Model -> Ranking & Ekspor JSON.
        """
        raw_tables = self.load_all_raw_data()
        df_features = self.preprocess_universe(tickers=tickers, as_of_date=as_of_date, raw_tables=raw_tables)
        results = self.score_features_dataframe(df_features)

        if export_json_path:
            out_path = Path(export_json_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
            logger.info("Scores berhasil diekspor ke %s (%d records)", out_path, len(results))

        return results

    def score_single_ticker(
        self,
        symbol: str,
        as_of_date: date | None = None,
    ) -> dict[str, Any]:
        """Helper ringan untuk endpoint API scoring satu emiten."""
        res = self.score_latest_universe(tickers=[symbol], as_of_date=as_of_date)
        return res[0] if res else {}

