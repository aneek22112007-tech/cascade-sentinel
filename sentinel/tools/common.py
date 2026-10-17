"""Shared Cypher bag and graph helpers for tools."""

from __future__ import annotations

from typing import Any

from sentinel import config
from sentinel.db import query as db_query
from sentinel.formulas import path_signature


class CypherBag:
    def __init__(self) -> None:
        self.items: list[str] = []
        self.ms: float = 0.0

    def run(
        self,
        tenant: str,
        cypher: str,
        params: dict[str, Any] | None = None,
        header: list[str] | None = None,
    ):
        result = db_query(tenant, cypher, params, header=header)
        self.items.append(cypher)
        self.ms += result.ms
        return result

    def envelope(self, result: Any) -> dict[str, Any]:
        return {"result": result, "cypher": list(self.items), "ms": round(self.ms, 3)}


def first_row(bag: CypherBag, tenant: str, cypher: str, params: dict | None = None) -> list[Any] | None:
    rows = bag.run(tenant, cypher, params).rows
    return rows[0] if rows else None


def props(bag: CypherBag, tenant: str, node_id: str) -> dict[str, Any]:
    row = first_row(bag, tenant, "MATCH (n {id: $id}) RETURN n", {"id": node_id})
    if not row:
        return {}
    node = row[0]
    if hasattr(node, "properties"):
        return dict(node.properties)
    if isinstance(node, dict):
        return node
    return {}


def episode_context(bag: CypherBag, tenant: str, episode_id: str) -> dict[str, Any]:
    row = first_row(
        bag,
        tenant,
        """
        MATCH (e:Episode {id: $eid})
        OPTIONAL MATCH (e)-[:TRIGGERED_BY]->(f:Forecast)
        OPTIONAL MATCH (e)-[:IN]->(d:District)
        OPTIONAL MATCH (d)-[:HAS_PROFILE]->(v:VulnerabilityProfile)
        RETURN e, f, d, v
        """,
        {"eid": episode_id},
    )
    if not row:
        raise KeyError(f"episode not found: {episode_id}")

    def as_dict(n: Any) -> dict[str, Any]:
        if n is None:
            return {}
        if hasattr(n, "properties"):
            return dict(n.properties)
        if isinstance(n, dict):
            return n
        return {}

    e, f, d, v = row
    ep = as_dict(e)
    fc = as_dict(f)
    dist = as_dict(d)
    prof = as_dict(v)
    return {
        "episode": ep,
        "forecast": fc,
        "district": dist,
        "profile": prof,
        "episode_id": episode_id,
        "forecast_id": fc.get("id"),
        "district_id": dist.get("id"),
        "vector": list(prof.get("vector") or []),
        "water_stress": float(prof.get("water_stress") or 0.0),
    }


def episode_year(bag: CypherBag, tenant: str, ctx: dict[str, Any]) -> int:
    """Season year for this episode. Falls back to config.CURRENT_YEAR."""
    ep = ctx.get("episode") or {}
    season_id = ep.get("season_id") or ""
    if season_id.startswith("season_"):
        try:
            return int(season_id.split("_", 1)[1])
        except ValueError:
            pass
    if season_id:
        row = bag.run(
            tenant,
            "MATCH (s:Season {id: $sid}) RETURN s.year",
            {"sid": season_id},
        ).rows
        if row and row[0][0] is not None:
            return int(row[0][0])
    return int(config.CURRENT_YEAR)


def district_maps(bag: CypherBag, tenant: str, district_id: str) -> dict[str, Any]:
    grows = bag.run(
        tenant,
        """
        MATCH (d:District {id: $did})-[g:GROWS]->(c)
        RETURN c.id, g.area_share, c.window_start_doy, c.window_end_doy, labels(c)
        """,
        {"did": district_id},
    ).rows
    groups = bag.run(
        tenant,
        """
        MATCH (d:District {id: $did})-[h:HAS_GROUP]->(l:LaborGroup)
        RETURN l.id, h.size_estimate, l.outdoor_hours
        """,
        {"did": district_id},
    ).rows
    stages = bag.run(
        tenant,
        """
        MATCH (c)
        WHERE c:CropStage OR c:LivestockStage
        RETURN c.id, c.window_start_doy, c.window_end_doy, labels(c)
        """,
    ).rows
    area = {r[0]: float(r[1]) for r in grows}
    windows = {r[0]: (r[1], r[2]) for r in stages}
    size = {r[0]: float(r[1]) for r in groups}
    outdoor = {r[0]: float(r[2]) for r in groups}
    crop_ids = {r[0] for r in stages if r[3] and "CropStage" in str(r[3])}
    livestock_ids = {r[0] for r in stages if r[3] and "LivestockStage" in str(r[3])}
    # labels() may come back as list
    if not crop_ids:
        crop_ids = {
            r[0]
            for r in bag.run(tenant, "MATCH (c:CropStage) RETURN c.id").rows
        }
        livestock_ids = {
            r[0]
            for r in bag.run(tenant, "MATCH (c:LivestockStage) RETURN c.id").rows
        }
        windows = {
            r[0]: (r[1], r[2])
            for r in bag.run(
                tenant,
                "MATCH (c) WHERE c:CropStage OR c:LivestockStage RETURN c.id, c.window_start_doy, c.window_end_doy",
            ).rows
        }
    return {
        "area_share": area,
        "windows": windows,
        "size_estimate": size,
        "outdoor_hours": outdoor,
        "crop_ids": crop_ids,
        "livestock_ids": livestock_ids,
    }


def split_signature(signature: str) -> list[str]:
    if ">" in signature:
        return [p for p in signature.split(">") if p]
    return [p for p in signature.split("|") if p]


def signature_of(node_ids: list[str]) -> str:
    return path_signature(node_ids)


def crop_stage_on(node_ids: list[str], crop_ids: set[str]) -> str | None:
    for nid in node_ids:
        if nid in crop_ids:
            return nid
    return None


def labor_on(node_ids: list[str], labor_ids: set[str]) -> str | None:
    for nid in node_ids:
        if nid in labor_ids:
            return nid
    return None
