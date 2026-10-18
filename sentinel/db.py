"""FalkorDB connection, tenant graphs, and a Cypher helper that logs every query."""

from __future__ import annotations

import time
from typing import Any

from falkordb import FalkorDB
from falkordb.graph import Graph

from sentinel import config

_client: FalkorDB | None = None
_query_log: list[dict[str, Any]] = []


class QueryResult:
    """Uniform wrapper: rows, the Cypher that produced them, and elapsed ms."""

    def __init__(
        self,
        rows: list[list[Any]],
        cypher: str,
        params: dict[str, Any],
        ms: float,
        header: list[str] | None = None,
    ):
        self.rows = rows
        self.cypher = cypher
        self.params = params
        self.ms = ms
        self.header = header or []

    def as_dicts(self) -> list[dict[str, Any]]:
        if not self.header:
            return [{"col": i, "value": row} for i, row in enumerate(self.rows)]
        out = []
        for row in self.rows:
            out.append({self.header[i]: row[i] if i < len(row) else None for i in range(len(self.header))})
        return out


def _lite_client(path: str):
    try:
        from redislite.falkordb_client import FalkorDB as LiteDB
    except ImportError:
        from falkordblite import FalkorDB as LiteDB
    return LiteDB(path)


def get_client() -> FalkorDB:
    global _client
    if _client is None:
        if config.FALKORDB_LITE:
            _client = _lite_client(config.FALKORDB_LITE)
        else:
            kwargs: dict[str, Any] = {
                "host": config.FALKORDB_HOST,
                "port": config.FALKORDB_PORT,
            }
            if config.FALKORDB_PASSWORD:
                kwargs["password"] = config.FALKORDB_PASSWORD
            _client = FalkorDB(**kwargs)
    return _client


def reset_client() -> None:
    global _client
    _client = None


def get_graph(tenant: str) -> Graph:
    return get_client().select_graph(config.graph_name(tenant))


def query(
    tenant: str,
    cypher: str,
    params: dict[str, Any] | None = None,
    *,
    header: list[str] | None = None,
) -> QueryResult:
    """Run parameterized Cypher on `sentinel_<tenant>` and log cypher + params + ms."""
    params = params or {}
    g = get_graph(tenant)
    t0 = time.perf_counter()
    raw = g.query(cypher, params)
    ms = (time.perf_counter() - t0) * 1000.0
    rows = raw.result_set or []
    entry = {
        "tenant": tenant,
        "cypher": cypher,
        "params": params,
        "ms": round(ms, 3),
        "n": len(rows),
    }
    _query_log.append(entry)
    if config.LOG_CYPHER:
        preview = " ".join(cypher.split())
        if len(preview) > 160:
            preview = preview[:157] + "..."
        print(f"[cypher {ms:.1f}ms n={len(rows)}] {preview}")
    return QueryResult(rows=rows, cypher=cypher, params=params, ms=ms, header=header)


def ping() -> int:
    """Acceptance probe: RETURN 1 against a throwaway health graph."""
    g = get_client().select_graph(config.HEALTH_GRAPH)
    raw = g.query("RETURN 1")
    return int(raw.result_set[0][0])


def query_log() -> list[dict[str, Any]]:
    return list(_query_log)


def reset_query_log() -> None:
    _query_log.clear()


def query_stats() -> dict[str, Any]:
    log = _query_log
    return {
        "count": len(log),
        "total_ms": round(sum(e["ms"] for e in log), 2),
        "log": log,
    }


def delete_graph(tenant: str) -> None:
    g = get_graph(tenant)
    try:
        g.delete()
    except Exception:
        pass


def node_edge_counts(tenant: str) -> tuple[int, int]:
    nodes = query(tenant, "MATCH (n) RETURN count(n)").rows[0][0]
    edges = query(tenant, "MATCH ()-[r]->() RETURN count(r)").rows[0][0]
    return int(nodes), int(edges)
