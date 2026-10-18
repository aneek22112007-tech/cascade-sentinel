"""Per-session sandbox graphs: concurrent visitors never see each other's state."""

from fastapi.testclient import TestClient

from sentinel import config, sessions
from sentinel.api.main import app

A = {"X-Sentinel-Session": "testsessaaaa1111"}
B = {"X-Sentinel-Session": "testsessbbbb2222"}


def test_graph_name_routing():
    assert config.graph_name("demo") == "sentinel_demo"
    tok = config.SESSION.set("abcdefgh12")
    try:
        assert config.graph_name("demo") == "sentinel_demo__abcdefgh12"
        assert config.graph_name("not_a_tenant") == "sentinel_not_a_tenant"
    finally:
        config.SESSION.reset(tok)
    assert sessions.clean_sid("ABCDEFGH12") == "abcdefgh12"
    assert sessions.clean_sid("x;FLUSHALL") == "" and sessions.clean_sid("short") == ""


def test_sessions_are_isolated():
    c = TestClient(app)
    base_before = c.get("/api/demo/episode/2024").json().get("status")
    assert c.post("/api/demo/reset", headers=A).status_code == 200
    assert c.post("/api/demo/reset", headers=B).status_code == 200
    r = c.post("/api/demo/run/2024?sse=false", headers=A)
    assert r.status_code == 200 and r.json()["recommendations"]
    assert c.get("/api/demo/episode/2024", headers=A).json()["status"] == "open"
    # B and the shared graph are untouched by A's run
    assert c.get("/api/demo/episode/2024", headers=B).json()["status"] in (None, "absent")
    assert c.get("/api/demo/episode/2024").json().get("status") == base_before
    # B resetting does not touch A
    c.post("/api/demo/reset", headers=B)
    assert c.get("/api/demo/episode/2024", headers=A).json()["status"] == "open"
    sessions.evict(now=10**12)  # expire everything created by this test
    assert sessions.active() == 0


def test_eviction_cap(monkeypatch):
    monkeypatch.setattr(sessions, "MAX_GRAPHS", 2)
    for i in range(4):
        sessions.ensure("demo", f"testcap{i:04d}xx")
    assert sessions.active() == 2
    sessions.evict(now=10**12)
    assert sessions.active() == 0
