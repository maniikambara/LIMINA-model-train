"""
api/routers/scores.py
=======================

Endpoint HTTP di atas `AMBAScoringService.score_latest_universe()` dan
`.score_single_ticker()` (`sectors_fetcher/service.py`). Router ini tidak
menghitung apa pun sendiri -- murni memvalidasi input, memanggil service,
dan menerjemahkan error jadi status HTTP yang sesuai.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_scoring_service
from api.schemas import SkorEmiten
from sectors_fetcher.service import AMBAScoringService

router = APIRouter(prefix="/scores", tags=["scores"])


@router.get("", response_model=list[SkorEmiten])
def daftar_skor(
    tickers: list[str] | None = Query(
        default=None,
        description="Kosongkan untuk seluruh emiten di tabel company_overview.",
    ),
    as_of_date: date | None = Query(default=None),
    service: AMBAScoringService = Depends(get_scoring_service),
):
    try:
        return service.score_latest_universe(tickers=tickers, as_of_date=as_of_date)
    except FileNotFoundError as exc:
        # output/model_random_forest.joblib belum ada di server ini --
        # lihat docs/PANDUAN-FASTAPI.md Bagian 5 (model file).
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{symbol}", response_model=SkorEmiten)
def skor_satu_emiten(
    symbol: str,
    as_of_date: date | None = Query(default=None),
    service: AMBAScoringService = Depends(get_scoring_service),
):
    try:
        hasil = service.score_single_ticker(symbol=symbol, as_of_date=as_of_date)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not hasil:
        raise HTTPException(status_code=404, detail=f"Tidak ada data untuk {symbol}")
    return hasil
