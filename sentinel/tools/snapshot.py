"""graph_snapshot — Cytoscape elements with status/layer classes."""

from __future__ import annotations

from sentinel.tools.adjudicate import compute_accepted_risk
from sentinel.tools.common import CypherBag, split_signature
from sentinel.tools.recommend import recommend_action


def graph_snapshot(tenant: str, episode_id: str) -> dict:
    bag = CypherBag()
    adj = compute_accepted_risk(tenant, episode_id)
    bag.items.extend(adj["cypher"])
    bag.ms += adj["ms"]
    path_status: dict[str, str] = adj["result"]["path_status"]

    recs = recommend_action(tenant, episode_id)
    bag.items.extend(recs["cypher"])
    bag.ms += recs["ms"]
    unprec = {
        r["path_signature"]
        for r in recs["result"]["recommendations"]
        if r["kind"] == "escalate"
    }
    act_iv = {
        r["intervention_id"]
        for r in recs["result"]["recommendations"]
        if r["kind"] == "act" and r.get("intervention_id")
    }
    dead_iv = {
        r["intervention_id"]
        for r in recs["result"]["recommendations"]
        if r["kind"] == "defeated_precedent" and r.get("intervention_id")
    }

    def path_class(sig: str) -> str:
        if sig in unprec:
            return "unprecedented"
        st = path_status.get(sig)
        if st == "accepted":
            return "accepted"
        if st == "defeated":
            return "defeated"
        if st == "proposed":
            return "contested"
        return ""

    edge_class: dict[tuple[str, str], str] = {}
    for sig, st in path_status.items():
        cls = path_class(sig)
        ids = split_signature(sig)
        for a, b in zip(ids, ids[1:]):
            prev = edge_class.get((a, b), "")
            rank = {"accepted": 4, "unprecedented": 3, "contested": 2, "defeated": 1, "": 0}
            if rank.get(cls, 0) >= rank.get(prev, 0):
                edge_class[(a, b)] = cls

    nodes_raw = bag.run(
        tenant,
        """
        MATCH (n)
        WHERE n:HazardType OR n:CropStage OR n:LivestockStage OR n:Commodity
           OR n:Market OR n:LaborGroup OR n:HealthOutcome OR n:Intervention
           OR n:District OR n:Officer
        RETURN n.id, labels(n), n.layer, n.provenance, n.name, n.score, n.status, n.kind
        """,
    ).rows
    node_els = []
    seen = set()
    for nid, labels, layer, prov, name, score, status, kind in nodes_raw:
        if not nid or nid in seen:
            continue
        seen.add(nid)
        labels = list(labels or [])
        classes = [f"layer-{layer}"] if layer else []
        if nid in act_iv:
            classes.append("act")
        if nid in dead_iv:
            classes.append("defeated_precedent")
        if any(nid in split_signature(sig) for sig in unprec):
            if "Intervention" not in labels:
                classes.append("on-unprecedented")
        node_els.append(
            {
                "data": {
                    "id": nid,
                    "label": name or nid,
                    "kind": labels[0] if labels else "Node",
                    "layer": layer,
                    "provenance": prov or "synthetic",
                    "score": score,
                    "status": status,
                    "rec_kind": kind,
                },
                "classes": " ".join(classes),
            }
        )

    rels = bag.run(
        tenant,
        """
        MATCH (a)-[r]->(b)
        WHERE a.id IS NOT NULL AND b.id IS NOT NULL
          AND type(r) IN [
            'STRESSES','REDUCES_YIELD_OF','SHOCKS_PRICE_AT','PRESSURES',
            'EXPOSES','AT_RISK_OF','TARGETS','GROWS','HAS_MARKET','HAS_GROUP',
            'HAS_PROFILE','INSTANCE_OF','FOR','MAY_TRIGGER','OWNS'
          ]
        RETURN a.id, b.id, type(r), r.weight, r.confidence, r.lag_days, r.source
        """,
    ).rows
    edge_els = []
    for src, dst, typ, w, c, lag, source in rels:
        cls = edge_class.get((src, dst), "")
        eid = f"{typ}:{src}:{dst}"
        edge_els.append(
            {
                "data": {
                    "id": eid,
                    "source": src,
                    "target": dst,
                    "label": typ,
                    "weight": w,
                    "confidence": c,
                    "lag_days": lag,
                    "cite": source,
                },
                "classes": cls,
            }
        )

    node_ids = {n["data"]["id"] for n in node_els}
    edge_els = [
        e
        for e in edge_els
        if e["data"]["source"] in node_ids and e["data"]["target"] in node_ids
    ]
    return bag.envelope(
        {
            "episode_id": episode_id,
            "elements": {"nodes": node_els, "edges": edge_els},
            "path_status": path_status,
            "unprecedented": sorted(unprec),
        }
    )
