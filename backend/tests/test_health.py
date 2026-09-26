import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture
def no_db(monkeypatch):
    async def fail_connect(_settings):
        raise RuntimeError("no db")

    monkeypatch.setattr(db, "connect", fail_connect)


def test_health_reports_db_error_without_mongo(no_db):
    with TestClient(app) as client:
        resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["db"] == "error"
    assert body["llm_provider"] in ("mock", "muse")
    assert body["sim_active"] is False


def test_unknown_route_uses_error_shape(no_db):
    with TestClient(app) as client:
        resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert resp.json() == {"error": {"code": "NOT_FOUND", "message": "Not Found"}}
