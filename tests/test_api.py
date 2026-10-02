"""Smoke test api/main.py. Butuh SUPABASE_URL/SUPABASE_KEY valid."""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "model_path" in body
