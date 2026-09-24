"""
tests/test_api.py
===================

Uji asap (smoke test) untuk api/main.py. TestClient FastAPI tidak
memerlukan server sungguhan berjalan, tapi /health tetap memanggil
get_scoring_service() -> AMBAScoringService(storage=SupabaseStorage()),
jadi tes ini tetap butuh SUPABASE_URL/SUPABASE_KEY valid (lihat
docs/PANDUAN-FASTAPI.md).
"""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "model_path" in body
