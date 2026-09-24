"""
api/main.py
============

Entry point FastAPI. Jalankan lokal dengan:

    export SUPABASE_URL=...
    export SUPABASE_KEY=...
    uvicorn api.main:app --reload --port 8000

Lalu buka http://localhost:8000/docs untuk Swagger UI. Lihat
docs/PANDUAN-FASTAPI.md untuk penjelasan tiap bagian, termasuk Bagian 5
soal dari mana output/*.joblib didapat saat deploy.
"""

from fastapi import FastAPI

from api.dependencies import get_scoring_service
from api.routers import scores

app = FastAPI(
    title="LIMINA/AMBA Scoring API",
    description="Skor risiko suspensi emiten IDX, dihitung dari model produksi (Random Forest).",
    version="1.0.0",
)

app.include_router(scores.router)

# CORS: aktifkan kalau API ini dipanggil dari web frontend di domain lain.
# from fastapi.middleware.cors import CORSMiddleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["https://domain-frontend-anda.com"],
#     allow_methods=["GET"],
#     allow_headers=["*"],
# )


@app.get("/health")
def health():
    service = get_scoring_service()
    return {
        "status": "ok",
        "model_path": service.model_path,
        "model_loaded": service._rf_model is not None,
    }
