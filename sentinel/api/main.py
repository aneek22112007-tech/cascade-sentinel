"""FastAPI: REST + static UI + SSE stream of orchestrator steps."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from sentinel import config
from sentinel.agents.orchestrator import run_season
from sentinel.db import ping, query
from sentinel.seed.loader import load_tenant
from sentinel.db import delete_graph
from sentinel.tools.episodes import close_episode
from sentinel.tools.registry import call_tool, list_tool_names

STATIC = config.ROOT / "static"

app = FastAPI(
    title="Cascade Sentinel",
    description="The climate-crisis agent that refuses to act without precedent.",
    version="0.1.0",
)


def _ok_tenant(tenant: str) -> str:
    if tenant not in config.TENANTS:
        raise HTTPException(400, f"unknown tenant {tenant}")
    return tenant


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "ping": ping(),
        "tenant_default": config.DEFAULT_TENANT,
        "synthetic": True,
        "tools": list_tool_names(),
    }


@app.get("/api/tenants")
def tenants() -> dict[str, Any]:
    return {
        "tenants": [
            {"id": "demo", "name": "Rajpur (archetype)", "badge": "synthetic"},
            {"id": "district_b", "name": "Kalinagar (archetype)", "badge": "synthetic"},
        ]
    }


@app.post("/api/{tenant}/reset")
def reset_tenant(tenant: str) -> dict[str, Any]:
    tenant = _ok_tenant(tenant)
    delete_graph(tenant)
    counts = load_tenant(tenant)
    return {"ok": True, "tenant": tenant, "nodes": counts["nodes"], "edges": counts["edges"]}


@app.post("/api/{tenant}/run/{year}")
async def run(tenant: str, year: int, sse: bool = True) -> Any:
    tenant = _ok_tenant(tenant)
    if year not in (2024, 2025):
        raise HTTPException(400, "year must be 2024 or 2025")
    if not sse:
        bundle = await asyncio.to_thread(run_season, tenant, year)
        bundle.pop("step_events", None)
        return bundle

    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def on_step(ev: dict[str, Any]) -> None:
        slim = {k: ev[k] for k in ("order", "agent", "tool", "ms", "summary") if k in ev}
        loop.call_soon_threadsafe(queue.put_nowait, slim)

    def work() -> dict[str, Any]:
        bundle = run_season(tenant, year, on_step=on_step)
        bundle.pop("step_events", None)
        return bundle

    async def gen():
        fut = asyncio.ensure_future(asyncio.to_thread(work))
        while not fut.done() or not queue.empty():
            try:
                ev = await asyncio.wait_for(queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            yield f"event: step\ndata: {json.dumps(ev)}\n\n"
        bundle = await fut
        yield f"event: done\ndata: {json.dumps(bundle, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/{tenant}/close/{episode_id}")
def close(tenant: str, episode_id: str) -> dict[str, Any]:
    tenant = _ok_tenant(tenant)
    return close_episode(tenant, episode_id)


@app.get("/api/{tenant}/snapshot/{episode_id}")
def snapshot(tenant: str, episode_id: str) -> dict[str, Any]:
    tenant = _ok_tenant(tenant)
    return call_tool("graph_snapshot", tenant=tenant, episode_id=episode_id)


@app.get("/api/{tenant}/explain/{recommendation_id}")
def explain_route(tenant: str, recommendation_id: str) -> dict[str, Any]:
    tenant = _ok_tenant(tenant)
    out = call_tool("explain", tenant=tenant, recommendation_id=recommendation_id)
    out["result"]["cypher"] = out["cypher"]
    return out


@app.post("/api/{tenant}/approve/{recommendation_id}")
def approve(tenant: str, recommendation_id: str) -> dict[str, Any]:
    tenant = _ok_tenant(tenant)
    rec = query(
        tenant,
        "MATCH (r:Recommendation {id: $id}) RETURN r.episode_id",
        {"id": recommendation_id},
    ).rows
    if not rec:
        raise HTTPException(404, "recommendation not found")
    eid = rec[0][0]
    row = query(
        tenant,
        """
        MATCH (r:Recommendation {id: $rid})
        MATCH (e:Episode {id: $eid})-[:IN]->(d:District)<-[:OWNS]-(o:Officer)
        MERGE (o)-[a:APPROVED]->(r)
        SET a.at = timestamp()
        RETURN o.id, o.name, o.role
        """,
        {"rid": recommendation_id, "eid": eid},
    ).rows
    if not row:
        raise HTTPException(400, "no owning officer")
    return {"ok": True, "officer": {"id": row[0][0], "name": row[0][1], "role": row[0][2]}}


@app.get("/api/{tenant}/memory/{layer}")
def memory(tenant: str, layer: str) -> dict[str, Any]:
    tenant = _ok_tenant(tenant)
    return call_tool("memory_view", tenant=tenant, layer=layer)


@app.get("/api/{tenant}/episode/{year}")
def episode_info(tenant: str, year: int) -> dict[str, Any]:
    tenant = _ok_tenant(tenant)
    eid = f"ep_{year}_{tenant}"
    rows = query(
        tenant,
        """
        MATCH (e:Episode {id: $eid})
        OPTIONAL MATCH (e)-[:IN]->(d:District)
        RETURN e.status, e.opened_at, e.closed_at, d.id, d.name
        """,
        {"eid": eid},
    ).rows
    if not rows:
        return {"id": eid, "status": "absent"}
    return {
        "id": eid,
        "status": rows[0][0],
        "opened_at": rows[0][1],
        "closed_at": rows[0][2],
        "district_id": rows[0][3],
        "district_name": rows[0][4],
        "synthetic": True,
    }


@app.get("/api/{tenant}/recommendations/{episode_id}")
def recs(tenant: str, episode_id: str) -> dict[str, Any]:
    tenant = _ok_tenant(tenant)
    rows = query(
        tenant,
        """
        MATCH (r:Recommendation {episode_id: $eid})
        OPTIONAL MATCH (r)-[:OF]->(i:Intervention)
        OPTIONAL MATCH (r)-[:ESCALATED_TO]->(o:Officer)
        RETURN r.id, r.kind, r.score, r.path_signature, r.message,
               i.id, i.name, i.lead_time_days, i.trials, i.successes, i.precedent_weight,
               o.id, o.name
        """,
        {"eid": episode_id},
    ).rows
    items = []
    for row in rows:
        items.append(
            {
                "id": row[0],
                "kind": row[1],
                "score": row[2],
                "path_signature": row[3],
                "message": row[4],
                "intervention_id": row[5],
                "intervention_name": row[6],
                "lead_time_days": row[7],
                "trials": row[8],
                "successes": row[9],
                "precedent_weight": row[10],
                "escalated_to": {"id": row[11], "name": row[12]} if row[11] else None,
            }
        )
    return {"episode_id": episode_id, "recommendations": items, "synthetic": True}


@app.get("/")
def index() -> FileResponse:
    page = STATIC / "index.html"
    if not page.exists():
        return JSONResponse({"ok": True, "ui": "pending", "health": "/health"})
    return FileResponse(page)


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
