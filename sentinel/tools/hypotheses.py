"""propose / support / attack hypotheses, including MAY_TRIGGER write."""

from __future__ import annotations

from sentinel.formulas import credibility, effective_confidence
from sentinel.tools.common import CypherBag, episode_context, split_signature


def _agent_cred(bag: CypherBag, tenant: str, agent_id: str) -> float:
    row = bag.run(
        tenant,
        "MATCH (a:Agent {id: $id}) RETURN a.hits, a.misses, a.credibility",
        {"id": agent_id},
    ).rows
    if not row:
        raise KeyError(f"unknown agent {agent_id}")
    hits, misses, stored = row[0]
    return float(stored if stored is not None else credibility(int(hits), int(misses)))


def hypothesis_id(agent_id: str, episode_id: str, path_signature: str) -> str:
    safe = path_signature.replace(">", "__")
    return f"hyp_{agent_id}_{episode_id}_{safe}"


def propose_hypothesis(
    tenant: str,
    agent_id: str,
    episode_id: str,
    path_signature: str,
    claim: str,
    confidence: float,
) -> dict:
    bag = CypherBag()
    ctx = episode_context(bag, tenant, episode_id)
    hid = hypothesis_id(agent_id, episode_id, path_signature)
    C = _agent_cred(bag, tenant, agent_id)
    eff = effective_confidence(float(confidence), C)
    pid = f"path_{path_signature}"
    bag.run(
        tenant,
        """
        MERGE (p:CascadePath {id: $pid})
        ON CREATE SET p.signature = $sig, p.node_ids = $ids,
                      p.score = 0.0, p.realized = false,
                      p.provenance = 'synthetic', p.layer = 'episodic'
        WITH p
        MATCH (a:Agent {id: $aid}), (e:Episode {id: $eid})
        MERGE (h:Hypothesis {id: $hid})
        SET h.episode_id = $eid,
            h.path_signature = $sig,
            h.claim = $claim,
            h.confidence = $conf,
            h.eff_confidence = $eff,
            h.status = coalesce(h.status, 'proposed'),
            h.reason = coalesce(h.reason, ''),
            h.provenance = 'synthetic',
            h.layer = 'episodic'
        MERGE (a)-[pr:PROPOSED]->(h)
        SET pr.at = coalesce(pr.at, timestamp())
        MERGE (h)-[:ABOUT]->(p)
        """,
        {
            "pid": pid,
            "sig": path_signature,
            "ids": split_signature(path_signature),
            "aid": agent_id,
            "eid": episode_id,
            "hid": hid,
            "claim": claim,
            "conf": float(confidence),
            "eff": float(eff),
        },
    )

    crop_ids = {r[0] for r in bag.run(tenant, "MATCH (c:CropStage) RETURN c.id").rows}
    fid = ctx["forecast_id"]
    for nid in split_signature(path_signature):
        if nid in crop_ids and fid:
            bag.run(
                tenant,
                """
                MATCH (f:Forecast {id: $fid}), (c:CropStage {id: $cid})
                MERGE (f)-[r:MAY_TRIGGER]->(c)
                SET r.confidence = $conf, r.provenance = 'synthetic', r.hypothesis_id = $hid
                """,
                {"fid": fid, "cid": nid, "conf": float(confidence), "hid": hid},
            )

    return bag.envelope(
        {
            "id": hid,
            "episode_id": episode_id,
            "path_signature": path_signature,
            "agent_id": agent_id,
            "claim": claim,
            "confidence": float(confidence),
            "eff_confidence": float(eff),
            "status": "proposed",
            "reason": "",
        }
    )


def _assert_evidence(
    tenant: str,
    agent_id: str,
    hypothesis_id_: str,
    evidence: dict,
    rel: str,
) -> dict:
    bag = CypherBag()
    kind = evidence.get("kind", "note")
    eid = f"ev_{agent_id}_{hypothesis_id_}_{rel}_{kind}"
    strength = float(evidence["strength"])
    bag.run(
        tenant,
        f"""
        MATCH (a:Agent {{id: $aid}}), (h:Hypothesis {{id: $hid}})
        MERGE (e:Evidence {{id: $eid}})
        SET e.kind = $kind,
            e.statement = $statement,
            e.value = $value,
            e.strength = $strength,
            e.source = $source,
            e.provenance = 'synthetic',
            e.layer = 'episodic'
        MERGE (a)-[:ASSERTED]->(e)
        MERGE (e)-[r:{rel}]->(h)
        SET r.strength = $strength
        """,
        {
            "aid": agent_id,
            "hid": hypothesis_id_,
            "eid": eid,
            "kind": kind,
            "statement": evidence.get("statement", ""),
            "value": "" if evidence.get("value") is None else evidence.get("value"),
            "strength": strength,
            "source": evidence.get("source", "src_synthetic_episode"),
        },
    )
    return bag.envelope(
        {
            "evidence_id": eid,
            "hypothesis_id": hypothesis_id_,
            "rel": rel,
            "strength": strength,
            "agent_id": agent_id,
        }
    )


def support_hypothesis(tenant: str, agent_id: str, hypothesis_id: str, evidence: dict) -> dict:
    if hasattr(evidence, "model_dump"):
        evidence = evidence.model_dump()
    return _assert_evidence(tenant, agent_id, hypothesis_id, evidence, "SUPPORTS")


def attack_hypothesis(tenant: str, agent_id: str, hypothesis_id: str, evidence: dict) -> dict:
    if hasattr(evidence, "model_dump"):
        evidence = evidence.model_dump()
    return _assert_evidence(tenant, agent_id, hypothesis_id, evidence, "ATTACKS")
