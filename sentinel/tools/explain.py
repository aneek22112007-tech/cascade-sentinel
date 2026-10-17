"""explain() — path, analogs, precedents, defeated rivals, Cypher, owner."""

from __future__ import annotations

from sentinel.tools.common import CypherBag, split_signature
from sentinel.tools.precedent import query_precedent


def explain(tenant: str, recommendation_id: str) -> dict:
    bag = CypherBag()
    row = bag.run(
        tenant,
        """
        MATCH (r:Recommendation {id: $rid})
        OPTIONAL MATCH (r)-[:OF]->(i:Intervention)
        OPTIONAL MATCH (r)-[:ESCALATED_TO]->(o:Officer)
        OPTIONAL MATCH (own:Officer)-[:OWNS]->(i)
        OPTIONAL MATCH (ap:Officer)-[appr:APPROVED]->(r)
        RETURN r, i, o, own, collect({officer: ap.id, name: ap.name, at: appr.at}) AS approvals
        """,
        {"rid": recommendation_id},
    ).rows
    if not row:
        raise KeyError(f"recommendation not found: {recommendation_id}")

    def as_dict(n):
        if n is None:
            return {}
        if hasattr(n, "properties"):
            return dict(n.properties)
        return dict(n) if isinstance(n, dict) else {}

    rec, iv, esc, owner, approvals = row[0]
    rec_d = as_dict(rec)
    iv_d = as_dict(iv)
    esc_d = as_dict(esc)
    owner_d = as_dict(owner)
    episode_id = rec_d.get("episode_id")
    sig = rec_d.get("path_signature") or ""
    path_ids = split_signature(sig)

    hops = []
    if len(path_ids) >= 2:
        hop_rows = bag.run(
            tenant,
            """
            MATCH (a)-[r]->(b)
            WHERE a.id IN $ids AND b.id IN $ids
            RETURN a.id, type(r), b.id, r.weight, r.confidence, r.lag_days, r.source
            """,
            {"ids": path_ids},
        ).rows
        by_pair = {(h[0], h[2]): h for h in hop_rows}
        for a, b in zip(path_ids, path_ids[1:]):
            h = by_pair.get((a, b))
            if h:
                hops.append(
                    {
                        "from": a,
                        "type": h[1],
                        "to": b,
                        "weight": h[3],
                        "confidence": h[4],
                        "lag_days": h[5],
                        "source": h[6],
                    }
                )
            else:
                hops.append({"from": a, "type": "?", "to": b})

    prec = query_precedent(tenant, episode_id, sig, k=5)
    bag.items.extend(prec["cypher"])
    bag.ms += prec["ms"]

    rivals = bag.run(
        tenant,
        """
        MATCH (a:Agent)-[:PROPOSED]->(h:Hypothesis {episode_id: $eid})
        WHERE h.status = 'defeated'
        RETURN h.id, a.id, h.path_signature, h.claim, h.reason, h.eff_confidence
        """,
        {"eid": episode_id},
    ).rows
    defeated = [
        {
            "id": r[0],
            "agent_id": r[1],
            "path_signature": r[2],
            "claim": r[3],
            "reason": r[4],
            "eff_confidence": r[5],
        }
        for r in rivals
    ]

    sources = bag.run(
        tenant,
        """
        MATCH (s:Source)
        WHERE s.id IN $ids
        RETURN s.id, s.title, s.url, s.provenance
        """,
        {"ids": list({h.get("source") for h in hops if h.get("source")} | {"src_synthetic_corridor", "src_imd"})},
    ).rows
    source_chips = [
        {"id": s[0], "title": s[1], "url": s[2], "provenance": s[3]} for s in sources
    ]

    if not owner_d and episode_id:
        drow = bag.run(
            tenant,
            """
            MATCH (e:Episode {id: $eid})-[:IN]->(d:District)<-[:OWNS]-(o:Officer)
            RETURN o.id, o.name, o.role
            """,
            {"eid": episode_id},
        ).rows
        if drow:
            owner_d = {"id": drow[0][0], "name": drow[0][1], "role": drow[0][2]}

    trail = bag.run(
        tenant,
        """
        MATCH (run:Run)-[s:STEP]->(n)
        WHERE run.tenant = $tenant
        RETURN run.id, s.order, s.agent, s.tool, s.ms, s.summary
        ORDER BY s.order
        """,
        {"tenant": tenant},
    ).rows

    return bag.envelope(
        {
            "recommendation": rec_d,
            "intervention": iv_d,
            "path": {"signature": sig, "node_ids": path_ids, "hops": hops},
            "analogs": prec["result"]["analogs"],
            "precedents": prec["result"]["interventions"],
            "defeated_rivals": defeated,
            "sources": source_chips,
            "owner": owner_d or esc_d,
            "escalated_to": esc_d,
            "approvals": [a for a in (approvals or []) if a and a.get("officer")],
            "audit_trail": [
                {
                    "run": t[0],
                    "order": t[1],
                    "agent": t[2],
                    "tool": t[3],
                    "ms": t[4],
                    "summary": t[5],
                }
                for t in trail
            ],
            "cypher": None,  # filled from envelope
        }
    )
