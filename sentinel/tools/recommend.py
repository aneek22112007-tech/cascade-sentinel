"""recommend_action — act only with precedent; otherwise escalate."""

from __future__ import annotations

from sentinel import config
from sentinel.formulas import precedent_weight
from sentinel.tools.adjudicate import compute_accepted_risk
from sentinel.tools.common import CypherBag, split_signature
from sentinel.tools.precedent import query_precedent


def recommend_action(tenant: str, episode_id: str) -> dict:
    bag = CypherBag()
    adj = compute_accepted_risk(tenant, episode_id)
    bag.items.extend(adj["cypher"])
    bag.ms += adj["ms"]
    path_status: dict[str, str] = adj["result"]["path_status"]
    score_by_sig = {
        h["path_signature"]: h.get("path_score") or 0.0 for h in adj["result"]["hypotheses"]
    }
    # fill scores from CONSIDERED
    cons = bag.run(
        tenant,
        """
        MATCH (e:Episode {id: $eid})-[c:CONSIDERED]->(p:CascadePath)
        RETURN p.signature, p.score, p.node_ids
        """,
        {"eid": episode_id},
    ).rows
    nodes_by_sig = {}
    for sig, score, nodes in cons:
        score_by_sig[sig] = float(score or score_by_sig.get(sig, 0.0))
        nodes_by_sig[sig] = list(nodes or split_signature(sig))

    owner_row = bag.run(
        tenant,
        """
        MATCH (e:Episode {id: $eid})-[:IN]->(d:District)<-[:OWNS]-(o:Officer)
        RETURN o.id, o.name, o.role
        """,
        {"eid": episode_id},
    ).rows
    officer_id = owner_row[0][0] if owner_row else None
    officer_name = owner_row[0][1] if owner_row else "district officer"

    recs: list[dict] = []
    act_paths: set[str] = set()

    interesting = [s for s, st in path_status.items() if st in ("accepted", "proposed")]
    for sig in interesting:
        status = path_status[sig]
        prec = query_precedent(tenant, episode_id, sig, k=5)
        bag.items.extend(prec["cypher"])
        bag.ms += prec["ms"]
        analogs = prec["result"]["analogs"]
        analog_ids = [a["episode_id"] for a in analogs]
        S = score_by_sig.get(sig, 0.0)
        has_act = False
        if status == "accepted":
            for iv in prec["result"]["interventions"]:
                P = float(iv["precedent_weight"])
                trials = int(iv["trials"])
                kind = None
                if iv["in_analog"] and P >= config.PRECEDENT_ACT_MIN:
                    kind = "act"
                    has_act = True
                    act_paths.add(sig)
                elif trials >= 1 and P < config.PRECEDENT_ACT_MIN:
                    kind = "defeated_precedent"
                if not kind:
                    continue
                rid = f"rec_{episode_id}_{iv['id']}_{kind}_{sig}".replace(">", "__")
                rec = {
                    "id": rid,
                    "episode_id": episode_id,
                    "path_signature": sig,
                    "kind": kind,
                    "score": float(S * P) if kind == "act" else float(P),
                    "intervention_id": iv["id"],
                    "intervention_name": iv["name"],
                    "message": None,
                    "precedent_weight": P,
                    "trials": trials,
                    "successes": int(iv["successes"]),
                    "analog_episode_ids": analog_ids,
                    "lead_time_days": None,
                }
                recs.append(rec)
                _write_rec(bag, tenant, rec, officer_id=None)
        if not has_act:
            if analogs:
                rid = f"rec_{episode_id}_weak_analog_{sig}".replace(">", "__")
                rec = {
                    "id": rid,
                    "episode_id": episode_id,
                    "path_signature": sig,
                    "kind": "weak_analog",
                    "score": float(S),
                    "intervention_id": None,
                    "intervention_name": None,
                    "message": "WEAK ANALOG: similar episodes exist but this path cannot be acted on",
                    "precedent_weight": None,
                    "trials": None,
                    "successes": None,
                    "analog_episode_ids": analog_ids,
                }
                recs.append(rec)
                _write_rec(bag, tenant, rec, officer_id=None)
            else:
                rid = f"rec_{episode_id}_escalate_{sig}".replace(">", "__")
                rec = {
                    "id": rid,
                    "episode_id": episode_id,
                    "path_signature": sig,
                    "kind": "escalate",
                    "score": float(S),
                    "intervention_id": None,
                    "intervention_name": None,
                    "message": "UNPRECEDENTED: escalate to district officer",
                    "precedent_weight": None,
                    "trials": None,
                    "successes": None,
                    "analog_episode_ids": analog_ids,
                    "escalated_to": officer_id,
                    "escalated_to_name": officer_name,
                }
                recs.append(rec)
                _write_rec(bag, tenant, rec, officer_id=officer_id)

    recs.sort(
        key=lambda r: (
            {"act": 0, "defeated_precedent": 1, "weak_analog": 2, "escalate": 3}[r["kind"]],
            -r["score"],
        )
    )
    _prune_stale_recs(bag, tenant, episode_id, {r["id"] for r in recs})
    return bag.envelope({"episode_id": episode_id, "recommendations": recs, "officer_id": officer_id})


def _write_rec(bag: CypherBag, tenant: str, rec: dict, officer_id: str | None) -> None:
    bag.run(
        tenant,
        """
        MERGE (r:Recommendation {id: $id})
        SET r.episode_id = $eid,
            r.path_signature = $sig,
            r.kind = $kind,
            r.score = $score,
            r.created_at = coalesce(r.created_at, timestamp()),
            r.message = $message,
            r.superseded = false,
            r.provenance = 'synthetic',
            r.layer = 'procedural'
        """,
        {
            "id": rec["id"],
            "eid": rec["episode_id"],
            "sig": rec["path_signature"],
            "kind": rec["kind"],
            "score": rec["score"],
            "message": rec.get("message"),
        },
    )
    if rec.get("intervention_id"):
        bag.run(
            tenant,
            """
            MATCH (r:Recommendation {id: $rid}), (i:Intervention {id: $iid})
            MERGE (r)-[:OF]->(i)
            """,
            {"rid": rec["id"], "iid": rec["intervention_id"]},
        )
        lead = bag.run(
            tenant,
            "MATCH (i:Intervention {id: $iid}) RETURN i.lead_time_days",
            {"iid": rec["intervention_id"]},
        ).rows
        if lead:
            rec["lead_time_days"] = lead[0][0]
    if officer_id and rec["kind"] == "escalate":
        bag.run(
            tenant,
            """
            MATCH (r:Recommendation {id: $rid}), (o:Officer {id: $oid})
            MERGE (r)-[:ESCALATED_TO]->(o)
            """,
            {"rid": rec["id"], "oid": officer_id},
        )


def _prune_stale_recs(bag: CypherBag, tenant: str, episode_id: str, keep_ids: set[str]) -> None:
    rows = bag.run(
        tenant,
        """
        MATCH (r:Recommendation {episode_id: $eid})
        WHERE NOT r.id IN $keep
        OPTIONAL MATCH (o:Officer)-[:APPROVED]->(r)
        RETURN r.id, count(o)
        """,
        {"eid": episode_id, "keep": list(keep_ids)},
    ).rows
    for rid, n_approved in rows:
        if int(n_approved or 0) > 0:
            bag.run(
                tenant,
                "MATCH (r:Recommendation {id: $id}) SET r.superseded = true",
                {"id": rid},
            )
        else:
            bag.run(
                tenant,
                "MATCH (r:Recommendation {id: $id}) DETACH DELETE r",
                {"id": rid},
            )
