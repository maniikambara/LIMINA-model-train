"""
FastAPI LIMINA. Jalankan lokal:

    export SUPABASE_URL=...
    export SUPABASE_KEY=...
    uvicorn api.main:app --reload --port 8000

Swagger UI di http://localhost:8000/docs. Lihat docs/PANDUAN-FASTAPI.md.
"""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from api.dependencies import get_scoring_service
from api.routers import scores

app = FastAPI(
    title="LIMINA Scoring API",
    description="Skor risiko suspensi emiten IDX dari model produksi.",
    version="1.0.0",
)

app.include_router(scores.router)

# CORS (kalau dipanggil dari web frontend di domain lain):
# from fastapi.middleware.cors import CORSMiddleware
# app.add_middleware(CORSMiddleware, allow_origins=["https://domain-anda.com"],
#                    allow_methods=["GET"], allow_headers=["*"])


@app.get("/", include_in_schema=False)
def root():
    """Health-check/browser yang membuka '/' diarahkan ke Swagger, bukan 404."""
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    service = get_scoring_service()
    return {
        "status": "ok",
        "model_path": service.model_path,
        "model_loaded": service._rf_model is not None,
    }
