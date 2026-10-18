"""Per-visitor sandbox graphs for the public demo.

Every browser session sends ``X-Sentinel-Session: <id>``. Requests to ``/api/<tenant>/...``
then run against ``sentinel_<tenant>__<id>``, seeded lazily from the tenant seed on first use,
so two judges clicking at the same time never see each other's runs, closes or resets.

Sessions are capped (``SESSION_MAX``, default 50 graphs) and expire after ``SESSION_TTL_S``
(default 2 h idle); evicted graphs are deleted. Requests without the header (CLI, backtest,
MCP, tests) keep using the shared tenant graph exactly as before.
"""

from __future__ import annotations

import asyncio
import os
import re
import threading
import time

from sentinel import config

SID_RE = re.compile(r"^[a-z0-9]{8,40}$")
MAX_GRAPHS = int(os.getenv("SESSION_MAX", "50"))
TTL_S = float(os.getenv("SESSION_TTL_S", "7200"))

_last_used: dict[tuple[str, str], float] = {}
_key_locks: dict[tuple[str, str], threading.Lock] = {}
_lock = threading.Lock()


def clean_sid(raw: str | None) -> str:
    sid = (raw or "").strip().lower()
    return sid if SID_RE.match(sid) else ""


def _with_session(sid: str, fn, *args):
    token = config.SESSION.set(sid)
    try:
        return fn(*args)
    finally:
        config.SESSION.reset(token)


def _seed_if_empty(tenant: str) -> None:
    from sentinel.db import query
    from sentinel.seed.loader import load_tenant

    if query(tenant, "MATCH (n) RETURN count(n)").rows[0][0] == 0:
        load_tenant(tenant)


def _drop(tenant: str) -> None:
    from sentinel.db import delete_graph

    delete_graph(tenant)


def ensure(tenant: str, sid: str) -> None:
    """Make sure the session graph exists (seed on first use) and mark it as used."""
    key = (tenant, sid)
    with _lock:
        klock = _key_locks.setdefault(key, threading.Lock())
    with klock:
        if key not in _last_used:
            _with_session(sid, _seed_if_empty, tenant)
        with _lock:
            _last_used[key] = time.time()
    evict(keep=key)


def evict(keep: tuple[str, str] | None = None, now: float | None = None) -> list[tuple[str, str]]:
    now = time.time() if now is None else now
    with _lock:
        order = sorted(_last_used.items(), key=lambda kv: kv[1])
        doomed = [k for k, t in order if k != keep and now - t > TTL_S]
        alive = [k for k, _ in order if k not in doomed]
        extra = len(alive) - MAX_GRAPHS
        for k in alive:
            if extra <= 0:
                break
            if k != keep:
                doomed.append(k)
                extra -= 1
        for k in doomed:
            _last_used.pop(k, None)
            _key_locks.pop(k, None)
    for tenant, sid in doomed:
        try:
            _with_session(sid, _drop, tenant)
        except Exception:  # pragma: no cover - best effort cleanup
            pass
    return doomed


def active() -> int:
    with _lock:
        return len(_last_used)


class SessionGraphMiddleware:
    """Pure ASGI middleware: route /api/<tenant>/... to the caller's sandbox graph."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/api/"):
            parts = scope["path"].split("/")
            headers = dict(scope.get("headers") or [])
            sid = clean_sid(headers.get(b"x-sentinel-session", b"").decode("latin-1"))
            if sid and len(parts) > 3 and parts[2] in config.TENANTS:
                token = config.SESSION.set(sid)
                try:
                    await asyncio.to_thread(ensure, parts[2], sid)
                    await self.app(scope, receive, send)
                finally:
                    config.SESSION.reset(token)
                return
        await self.app(scope, receive, send)
