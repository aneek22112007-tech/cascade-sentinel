"""Deploy plumbing: FALKORDB_URL parsing, /healthz, landing + dashboard routes."""

import importlib
import os

from fastapi.testclient import TestClient


def test_falkordb_url_parsing(monkeypatch):
    from sentinel import config

    monkeypatch.setenv("FALKORDB_URL", "rediss://default:p%40ss@db.example.com:16379")
    try:
        cfg = importlib.reload(config)
        assert cfg.FALKORDB_HOST == "db.example.com"
        assert cfg.FALKORDB_PORT == 16379
        assert cfg.FALKORDB_PASSWORD == "p@ss"
        assert cfg.FALKORDB_USERNAME is None
        assert cfg.FALKORDB_SSL is True
    finally:
        monkeypatch.delenv("FALKORDB_URL")
        importlib.reload(config)


def test_healthz_and_pages():
    from sentinel.api.main import app

    c = TestClient(app)
    r = c.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert c.get("/").status_code == 200
    assert c.get("/app").status_code == 200
    assert c.get("/health").json()["ok"] is True


def test_serve_backend_choice(monkeypatch):
    from sentinel import serve

    monkeypatch.setenv("FALKORDB_URL", "redis://x:1")
    assert serve.choose_backend() == "external-url"
    monkeypatch.delenv("FALKORDB_URL")
    monkeypatch.setenv("FALKORDB_HOST", os.getenv("FALKORDB_HOST", "localhost"))
    assert serve.choose_backend() == "external-host"
