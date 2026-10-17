"""enumerate_cascade_paths — multi-hop hazard → health traversal."""

from __future__ import annotations

from sentinel import config
from sentinel.formulas import exposure_factor, intensity_factor, path_signature, timing_factor
from sentinel.tools.common import CypherBag, district_maps, episode_context


ENUMERATE_CYPHER = """
MATCH (f:Forecast {id: $fid})-[:INSTANCE_OF]->(h:HazardType)
MATCH p = (h)-[*2..5]->(o:HealthOutcome)
WITH p, relationships(p) AS rels, nodes(p) AS ns
RETURN [n IN ns | n.id] AS ids,
       [r IN rels | type(r)] AS types,
       reduce(s = 1.0, r IN rels | s * r.weight * r.confidence) AS base,
       reduce(l = 0, r IN rels | l + coalesce(r.lag_days, 0)) AS lag
ORDER BY base DESC LIMIT 50
"""


def enumerate_cascade_paths(tenant: str, episode_id: str, k: int = 6) -> dict:
    bag = CypherBag()
    ctx = episode_context(bag, tenant, episode_id)
    fid = ctx["forecast_id"]
    if not fid:
        raise KeyError(f"episode {episode_id} has no forecast")
    maps = district_maps(bag, tenant, ctx["district_id"])
    doy = int(ctx["forecast"]["doy"])
    anomaly = float(ctx["forecast"]["anomaly_c"])
    I = intensity_factor(anomaly)

    raw = bag.run(tenant, ENUMERATE_CYPHER, {"fid": fid}).rows
    scored: list[dict] = []
    seen: set[str] = set()
    labor_ids = set(maps["size_estimate"])
    for ids, types, base, lag in raw:
        ids = list(ids)
        sig = path_signature(ids)
        if sig in seen:
            continue
        seen.add(sig)
        stages = [n for n in ids if n in maps["windows"]]
        if stages:
            timings = []
            for sid in stages:
                start, end = maps["windows"][sid]
                timings.append(timing_factor(doy, start, end))
            T = min(timings)
        else:
            T = 1.0
        crop_on_path = [n for n in ids if n in maps["crop_ids"]]
        if crop_on_path:
            area = maps["area_share"].get(crop_on_path[0], 0.0)
        else:
            area = 1.0
        labor = next((n for n in ids if n in labor_ids), None)
        size = maps["size_estimate"].get(labor, 1.0) if labor else 1.0
        exp = exposure_factor(area, size)
        S = I * T * exp * float(base)
        scored.append(
            {
                "signature": sig,
                "node_ids": ids,
                "types": list(types),
                "score": float(S),
                "lag_days": int(lag or 0),
                "intensity": float(I),
                "timing": float(T),
                "exposure": float(exp),
                "base": float(base),
            }
        )
    scored.sort(key=lambda p: (-p["score"], p["signature"]))
    top = scored[: int(k or config.TOP_K_PATHS)]
    for rank, path in enumerate(top, start=1):
        path["rank"] = rank
        pid = f"path_{path['signature']}"
        bag.run(
            tenant,
            """
            MERGE (p:CascadePath {id: $pid})
            SET p.signature = $sig,
                p.node_ids = $ids,
                p.score = $score,
                p.realized = coalesce(p.realized, false),
                p.provenance = 'synthetic',
                p.layer = 'episodic'
            WITH p
            MATCH (e:Episode {id: $eid})
            MERGE (e)-[c:CONSIDERED]->(p)
            SET c.rank = $rank, c.score = $score
            """,
            {
                "pid": pid,
                "sig": path["signature"],
                "ids": path["node_ids"],
                "score": path["score"],
                "eid": episode_id,
                "rank": rank,
            },
        )
    return bag.envelope({"paths": top, "episode_id": episode_id, "k": len(top)})
