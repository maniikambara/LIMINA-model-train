"""Bentuk response, mengikuti LiminaScoringService.score_features_dataframe()."""

from pydantic import BaseModel


class SkorEmiten(BaseModel):
    symbol: str
    company_name: str
    as_of_date: str
    sector: str | None = None
    sub_sector: str | None = None
    board: str | None = None
    skor: float
    persentil: float
    kategori: str  # Rendah | Sedang | Tinggi | Sangat Tinggi
    arah_30h: str  # naik | turun | stabil
    status: str  # dinilai | sudah_ditandai | tidak_dapat_dinilai
    indikator_dominan: str
    kontribusi: dict[str, float]


class HealthResponse(BaseModel):
    status: str
    model_path: str
    # model_selected di output/backtest.json (mis. "Blend LR+RF"); None kalau
    # model di-override lewat LIMINA_MODEL_PATH atau backtest.json tidak ada.
    model_selected: str | None = None
    model_loaded: bool
