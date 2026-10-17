"""Run a season: open → enumerate → propose → critique → adjudicate → recommend."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sentinel import config
from sentinel.agents.agronomy import AgronomyAgent
from sentinel.agents.base import EpisodeView, ToolCall
from sentinel.agents.health import HealthAgent
from sentinel.agents.llm import write_rationale
from sentinel.agents.weather import WeatherAgent
from sentinel.db import query
from sentinel.tools.common import CypherBag, district_maps, episode_context
from sentinel.tools.episodes import open_episode, reset_episode_runtime
from sentinel.tools.registry import call_tool

OnStep = Callable[[dict[str, Any]], None]


def _agents() -> list:
    return [WeatherAgent(), AgronomyAgent(), HealthAgent()]


def _write_step(
    tenant: str,
    run_id: str,
    episode_id: str,
    order: int,
    agent: str,
    tool: str,
    ms: float,
    summary: str,
) -> None:
    query(
        tenant,
        """
        MATCH (run:Run {id: $rid}), (e:Episode {id: $eid})
        MERGE (run)-[s:STEP {order: $order}]->(e)
        SET s.agent = $agent, s.tool = $tool, s.ms = $ms, s.summary = $summary
        """,
        {
            "rid": run_id,
            "eid": episode_id,
            "order": order,
            "agent": agent,
            "tool": tool,
            "ms": ms,
            "summary": summary,
        },
    )


def _exec(tenant: str, call: ToolCall) -> dict[str, Any]:
    kwargs = dict(call.kwargs)
    kwargs["tenant"] = tenant
    return call_tool(call.name, **kwargs)


def _view(tenant: str, episode_id: str, season_year: int, paths: list[dict]) -> EpisodeView:
    bag = CypherBag()
    ctx = episode_context(bag, tenant, episode_id)
    maps = district_maps(bag, tenant, ctx["district_id"])
    return EpisodeView(
        tenant=tenant,
        episode_id=episode_id,
        season_year=season_year,
        forecast=ctx["forecast"],
        district=ctx["district"],
        profile=ctx["profile"],
        paths=paths,
        water_stress=float(ctx["water_stress"]),
        area_share=maps["area_share"],
        outdoor_hours=maps["outdoor_hours"],
        crop_ids=maps["crop_ids"],
        windows=maps["windows"],
    )


def run_season(
    tenant: str,
    season_year: int,
    on_step: OnStep | None = None,
    *,
    with_llm: bool = True,
) -> dict[str, Any]:
    config.set_current_year(season_year)
    run_id = f"run_{tenant}_{season_year}"
    query(tenant, "MATCH (run:Run {id: $rid}) DETACH DELETE run", {"rid": run_id})
    opened = open_episode(tenant, season_year)
    eid = opened["result"]["id"]
    status_row = query(
        tenant, "MATCH (e:Episode {id: $eid}) RETURN e.status, e.closed_at", {"eid": eid}
    ).rows
    if status_row and status_row[0][0] != "closed":
        reset_episode_runtime(tenant, eid)

    steps: list[dict[str, Any]] = []
    order = 0

    def emit(agent: str, tool: str, ms: float, summary: str, payload: Any) -> None:
        nonlocal order
        order += 1
        event = {
            "order": order,
            "agent": agent,
            "tool": tool,
            "ms": round(ms, 3),
            "summary": summary,
            "payload": payload,
        }
        steps.append(event)
        query(
            tenant,
            """
            MERGE (run:Run {id: $rid})
            SET run.tenant = $tenant, run.season_id = $sid,
                run.started_at = coalesce(run.started_at, $started)
            """,
            {
                "rid": run_id,
                "tenant": tenant,
                "sid": f"season_{season_year}",
                "started": f"{season_year}-05-10",
            },
        )
        _write_step(tenant, run_id, eid, order, agent, tool, ms, summary)
        if on_step:
            on_step(event)

    emit("orchestrator", "open_episode", opened["ms"], f"opened {eid}", opened["result"])

    enumerated = call_tool("enumerate_cascade_paths", tenant=tenant, episode_id=eid, k=config.TOP_K_PATHS)
    paths = enumerated["result"]["paths"]
    emit("orchestrator", "enumerate_cascade_paths", enumerated["ms"], f"{len(paths)} paths", enumerated["result"])

    view = _view(tenant, eid, season_year, paths)
    agents = _agents()

    for agent in agents:
        for call in agent.propose(view):
            out = _exec(tenant, call)
            emit(agent.agent_id, call.name, out["ms"], call.summary, out["result"])

    def load_hyps() -> list[dict[str, Any]]:
        adj = call_tool("compute_accepted_risk", tenant=tenant, episode_id=eid)
        return adj["result"]["hypotheses"]

    hyps = load_hyps()
    view.hypotheses = hyps
    for agent in agents:
        for call in agent.critique(view, hyps):
            out = _exec(tenant, call)
            emit(agent.agent_id, call.name, out["ms"], call.summary, out["result"])

    adj = call_tool("compute_accepted_risk", tenant=tenant, episode_id=eid)
    emit("orchestrator", "compute_accepted_risk", adj["ms"], "round 1 adjudication", adj["result"])

    contested = [h for h in adj["result"]["hypotheses"] if h["status"] == "proposed"]
    if contested:
        hyps = adj["result"]["hypotheses"]
        view.hypotheses = hyps
        for agent in agents:
            for call in agent.critique(view, hyps):
                out = _exec(tenant, call)
                emit(agent.agent_id, call.name, out["ms"], f"round2 {call.summary}", out["result"])
        adj = call_tool("compute_accepted_risk", tenant=tenant, episode_id=eid)
        emit("orchestrator", "compute_accepted_risk", adj["ms"], "round 2 adjudication", adj["result"])

    recs = call_tool("recommend_action", tenant=tenant, episode_id=eid)
    emit("orchestrator", "recommend_action", recs["ms"], f"{len(recs['result']['recommendations'])} recs", recs["result"])

    bundle = {
        "tenant": tenant,
        "season_year": season_year,
        "episode_id": eid,
        "run_id": run_id,
        "paths": paths,
        "hypotheses": adj["result"]["hypotheses"],
        "path_status": adj["result"]["path_status"],
        "recommendations": recs["result"]["recommendations"],
    }
    rationale = write_rationale(bundle) if with_llm else ""
    bundle["rationale"] = rationale
    query(
        tenant,
        "MATCH (run:Run {id: $rid}) SET run.finished_at = $done, run.rationale = $rationale",
        {"rid": run_id, "done": f"{season_year}-05-12", "rationale": rationale},
    )
    bundle["steps"] = [{k: s[k] for k in ("order", "agent", "tool", "ms", "summary")} for s in steps]
    bundle["step_events"] = steps
    return bundle
