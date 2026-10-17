from fastapi.testclient import TestClient

from sentinel import config
from sentinel.api.main import app


client = TestClient(app)


def test_memory_invalid_layer_is_400():
    r = client.get("/api/demo/memory/not_a_layer")
    assert r.status_code == 400
    assert "layer" in (r.json().get("detail") or "").lower()


def test_explain_unknown_id_is_404():
    r = client.get("/api/demo/explain/rec_does_not_exist")
    assert r.status_code == 404


def test_close_unknown_id_is_404():
    r = client.post("/api/demo/close/ep_does_not_exist")
    assert r.status_code == 404


def test_admin_token_required_when_set(monkeypatch):
    monkeypatch.setattr(config, "SENTINEL_ADMIN_TOKEN", "s3cret-token")
    r = client.post("/api/demo/close/ep_does_not_exist")
    assert r.status_code == 401
    r = client.post(
        "/api/demo/close/ep_does_not_exist",
        headers={"X-Sentinel-Token": "wrong"},
    )
    assert r.status_code == 401
    r = client.post(
        "/api/demo/close/ep_does_not_exist",
        headers={"X-Sentinel-Token": "s3cret-token"},
    )
    assert r.status_code == 404
    r = client.post("/api/demo/reset")
    assert r.status_code == 401
    r = client.post("/api/demo/run/2024")
    assert r.status_code == 401
    r = client.post("/api/demo/approve/rec_x")
    assert r.status_code == 401


def test_admin_token_unset_allows_local_dev(monkeypatch):
    monkeypatch.setattr(config, "SENTINEL_ADMIN_TOKEN", "")
    r = client.post("/api/demo/close/ep_does_not_exist")
    assert r.status_code == 404
