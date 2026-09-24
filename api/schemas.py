"""
api/schemas.py
===============

Bentuk response, mengikuti persis field yang dihasilkan
`AMBAScoringService.score_features_dataframe()`
(`sectors_fetcher/service.py`).
"""

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
    kategori: str  # "Rendah" | "Sedang" | "Tinggi" | "Sangat Tinggi"
    arah_30h: str  # "naik" | "turun" | "stabil"
    status: str  # "dinilai" | "sudah_ditandai" | "tidak_dapat_dinilai"
    indikator_dominan: str
    kontribusi: dict[str, float]


class HealthResponse(BaseModel):
    status: str
    model_path: str
    model_loaded: bool
