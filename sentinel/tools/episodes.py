"""open_episode, close_episode, runtime reset."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone

from sentinel import config
from sentinel.formulas import credibility, is_hit, jaccard, path_signature, precedent_weight
from sentinel.seed.loader import load_heldout, seed_archetype
from sentinel.tools.common import CypherBag, episode_context, episode_year, split_signature

_CLOSE_LOCKS: dict[tuple[str, str], threading.Lock] = {}
_CLOSE_LOCKS_GUARD = threading.Lock()


def _close_lock(tenant: str, episode_id: str) -> threading.Lock:
    with _CLOSE_LOCKS_GUARD:
        return _CLOSE_LOCKS.setdefault((tenant, episode_id), threading.Lock())


def open_episode(tenant: str, season_year: int) -> dict:
    bag = CypherBag()
    eid = f"ep_{season_year}_{tenant}"
    existing = bag.run(
        tenant,
        "MATCH (e:Episode {id: $eid}) RETURN e.status, e.closed_at",
        {"eid": eid},
    ).rows
    if existing:
        return bag.envelope({"id": eid, "status": existing[0][0], "reused": True})

    fid = f"fc_{season_year}_{tenant}"
    row = bag.run(
        tenant,
        """
        MATCH (f:Forecast {id: $fid})-[:FOR]->(d:District)
        RETURN f.id, d.id
        """,
        {"fid": fid},
    ).rows
    if not row:
        raise KeyError(f"no day-one forecast {fid}")
    _, district_id = row[0]
    sid = f"season_{season_year}"
    now = datetime.now(timezone.utc).isoformat()
    bag.run(
        tenant,
        """
        MERGE (s:Season {id: $sid})
        SET s.year = $year, s.provenance = 'synthetic', s.layer = 'episodic'
        MERGE (e:Episode {id: $eid})
        SET e.season_id = $sid, e.status = 'open', e.opened_at = $now,
            e.closed_at = null, e.provenance = 'synthetic', e.layer = 'episodic'
        WITH e
        MATCH (d:District {id: $did}), (f:Forecast {id: $fid})
        MERGE (e)-[:IN]->(d)
        MERGE (e)-[:TRIGGERED_BY]->(f)
        """,
        {"sid": sid, "year": season_year, "eid": eid, "now": now, "did": district_id, "fid": fid},
    )
    return bag.envelope({"id": eid, "status": "open", "forecast_id": fid, "district_id": district_id})


def reset_episode_runtime(tenant: str, episode_id: str) -> dict:
    """Delete hypotheses, evidence, recommendations, runs for an open/test episode."""
    bag = CypherBag()
    bag.run(
        tenant,
        """
        MATCH (h:Hypothesis {episode_id: $eid})<-[]-(ev:Evidence)
        DETACH DELETE ev
        """,
        {"eid": episode_id},
    )
    bag.run(
        tenant,
        """
        MATCH (h:Hypothesis {episode_id: $eid})
        DETACH DELETE h
        """,
        {"eid": episode_id},
    )
    bag.run(
        tenant,
        """
        MATCH (r:Recommendation {episode_id: $eid})
        DETACH DELETE r
        """,
        {"eid": episode_id},
    )
    bag.run(
        tenant,
        """
        MATCH (run:Run)-[s:STEP]->()
        WHERE run.tenant = $tenant AND (s.summary CONTAINS $eid OR run.id CONTAINS $eid)
        DETACH DELETE run
        """,
        {"tenant": tenant, "eid": episode_id},
    )
    bag.run(
        tenant,
        """
        MATCH (e:Episode {id: $eid})-[c:CONSIDERED]->()
        DELETE c
        """,
        {"eid": episode_id},
    )
    bag.run(
        tenant,
        """
        MATCH (e:Evidence)
        WHERE NOT (e)-[:SUPPORTS|ATTACKS]->(:Hypothesis)
        DETACH DELETE e
        """,
    )
    return bag.envelope({"reset": episode_id})


def _stored_close(bag: CypherBag, tenant: str, episode_id: str) -> dict | None:
    ctx = episode_context(bag, tenant, episode_id)
    ep = ctx["episode"]
    if not ep.get("closed_at"):
        return None
    stored = ep.get("close_result")
    if stored:
        return bag.envelope(json.loads(stored))
    return bag.envelope({"episode_id": episode_id, "status": "closed", "idempotent": True})


def _wait_stored_close(bag: CypherBag, tenant: str, episode_id: str, timeout_s: float = 15.0) -> dict | None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        found = _stored_close(bag, tenant, episode_id)
        if found is not None:
            return found
        time.sleep(0.05)
    return None


def close_episode(tenant: str, episode_id: str) -> dict:
    with _close_lock(tenant, episode_id):
        return _close_episode_locked(tenant, episode_id)


def _close_episode_locked(tenant: str, episode_id: str) -> dict:
    bag = CypherBag()
    stored = _stored_close(bag, tenant, episode_id)
    if stored is not None:
        return stored

    claimed = bag.run(
        tenant,
        """
        MATCH (e:Episode {id: $eid})
        WHERE e.closed_at IS NULL AND coalesce(e.closing, false) = false
        SET e.closing = true
        RETURN e.id
        """,
        {"eid": episode_id},
    )
    if not claimed.rows:
        waited = _wait_stored_close(bag, tenant, episode_id)
        if waited is not None:
            return waited
        raise RuntimeError(f"close_episode could not claim {episode_id}")

    try:
        return _close_episode_write(bag, tenant, episode_id)
    except Exception:
        bag.run(
            tenant,
            "MATCH (e:Episode {id: $eid}) SET e.closing = false",
            {"eid": episode_id},
        )
        raise


def _close_episode_write(bag: CypherBag, tenant: str, episode_id: str) -> dict:
    ctx = episode_context(bag, tenant, episode_id)
    year = episode_year(bag, tenant, ctx)

    held = load_heldout()["by_tenant_year"][seed_archetype(tenant)][str(year)]
    realized = list(held["realized_path"])
    also = [list(p) for p in held.get("also_realized") or []]
    realized_sets = [realized] + also
    realized_sig = path_signature(realized)

    pid = f"path_{realized_sig}"
    bag.run(
        tenant,
        """
        MERGE (p:CascadePath {id: $pid})
        SET p.signature = $sig, p.node_ids = $ids, p.realized = true,
            p.provenance = 'synthetic', p.layer = 'episodic'
        WITH p
        MATCH (e:Episode {id: $eid})
        MERGE (e)-[:FOLLOWED_PATH]->(p)
        """,
        {"pid": pid, "sig": realized_sig, "ids": realized, "eid": episode_id},
    )

    for obs in held.get("observations") or []:
        bag.run(
            tenant,
            """
            MATCH (e:Episode {id: $eid}), (n {id: $nid})
            MERGE (e)-[r:OBSERVED {date: $date}]->(n)
            SET r.value = $value, r.unit = $unit, r.source = $source,
                r.weight = 1.0, r.confidence = 1.0, r.lag_days = 0
            """,
            {
                "eid": episode_id,
                "nid": obs["node"],
                "date": obs["date"],
                "value": obs["value"],
                "unit": obs["unit"],
                "source": obs.get("source", "src_synthetic_episode"),
            },
        )

    before_iv = {
        r[0]: {
            "trials": int(r[1] or 0),
            "successes": int(r[2] or 0),
            "last_trial_year": int(r[3]) if r[3] is not None else year,
            "precedent_weight": float(r[4] or 0.0),
        }
        for r in bag.run(
            tenant,
            "MATCH (i:Intervention) RETURN i.id, i.trials, i.successes, i.last_trial_year, i.precedent_weight",
        ).rows
    }
    before_ag = {
        r[0]: {"hits": int(r[1] or 0), "misses": int(r[2] or 0), "credibility": float(r[3] or 0.0)}
        for r in bag.run(
            tenant,
            "MATCH (a:Agent) RETURN a.id, a.hits, a.misses, a.credibility",
        ).rows
    }

    iv_after = {}
    for out in held.get("outcomes") or []:
        iid = out["intervention_id"]
        success = bool(out["success"])
        oid = f"out_{episode_id}_{iid}"
        already = bag.run(
            tenant,
            """
            MATCH (:Intervention {id: $iid})-[r:HAD_OUTCOME {episode_id: $eid}]->(:Outcome)
            RETURN count(r)
            """,
            {"iid": iid, "eid": episode_id},
        ).rows
        had = already and int(already[0][0] or 0) > 0
        if not had:
            bag.run(
                tenant,
                """
                MATCH (i:Intervention {id: $iid})
                MERGE (out:Outcome {id: $oid})
                SET out.description = $desc, out.provenance = 'synthetic', out.layer = 'procedural'
                MERGE (i)-[r:HAD_OUTCOME {episode_id: $eid}]->(out)
                SET r.success = $success, r.effect_size = $effect, r.source = $src, r.year = $year,
                    r.weight = 1.0, r.confidence = 1.0, r.lag_days = 0
                SET i.trials = coalesce(i.trials, 0) + 1,
                    i.successes = coalesce(i.successes, 0) + CASE WHEN $success THEN 1 ELSE 0 END,
                    i.last_trial_year = $year
                """,
                {
                    "iid": iid,
                    "oid": oid,
                    "desc": out.get("description", ""),
                    "eid": episode_id,
                    "success": success,
                    "effect": float(out.get("effect_size") or 0.0),
                    "src": "src_synthetic_episode",
                    "year": year,
                },
            )
        row = bag.run(
            tenant,
            "MATCH (i:Intervention {id: $iid}) RETURN i.trials, i.successes, i.last_trial_year",
            {"iid": iid},
        ).rows[0]
        p = precedent_weight(int(row[1]), int(row[0]), int(row[2]), year)
        bag.run(
            tenant,
            "MATCH (i:Intervention {id: $iid}) SET i.precedent_weight = $p",
            {"iid": iid, "p": p},
        )
        iv_after[iid] = {
            "trials": int(row[0]),
            "successes": int(row[1]),
            "last_trial_year": int(row[2]),
            "precedent_weight": p,
        }

    hyps = bag.run(
        tenant,
        """
        MATCH (a:Agent)-[:PROPOSED]->(h:Hypothesis {episode_id: $eid})
        RETURN a.id, h.id, h.path_signature
        """,
        {"eid": episode_id},
    ).rows
    best_j: dict[str, float] = {}
    for aid, hid, sig in hyps:
        nodes = split_signature(sig)
        j = max(jaccard(nodes, real) for real in realized_sets)
        best_j[aid] = max(best_j.get(aid, 0.0), j)
        hit = any(is_hit(nodes, real) for real in realized_sets)
        bag.run(
            tenant,
            "MATCH (h:Hypothesis {id: $hid}) SET h.hit = $hit, h.jaccard = $j",
            {"hid": hid, "hit": hit, "j": j},
        )

    agent_delta = {}
    all_agents = list(before_ag.keys())
    proposers = {aid for aid, _, _ in hyps}
    for aid in all_agents:
        if aid not in proposers:
            continue
        hit = best_j.get(aid, 0.0) >= config.HIT_JACCARD_MIN
        hits = before_ag[aid]["hits"] + (1 if hit else 0)
        misses = before_ag[aid]["misses"] + (0 if hit else 1)
        C = credibility(hits, misses)
        bag.run(
            tenant,
            "MATCH (a:Agent {id: $id}) SET a.hits = $h, a.misses = $m, a.credibility = $c",
            {"id": aid, "h": hits, "m": misses, "c": C},
        )
        agent_delta[aid] = {
            "before": before_ag[aid],
            "after": {"hits": hits, "misses": misses, "credibility": C},
            "verdict": "hit" if hit else "miss",
            "best_jaccard": best_j.get(aid, 0.0),
        }

    top_accepted = bag.run(
        tenant,
        """
        MATCH (h:Hypothesis {episode_id: $eid, status: 'accepted'})
        RETURN h.path_signature
        ORDER BY h.eff_confidence DESC
        """,
        {"eid": episode_id},
    ).rows
    top_sig = top_accepted[0][0] if top_accepted else None
    recon = jaccard(split_signature(top_sig), realized) if top_sig else 0.0
    passed = recon >= config.HIT_JACCARD_MIN

    now = f"{year}-06-30T00:00:00+00:00"
    payload = {
        "episode_id": episode_id,
        "status": "closed",
        "closed_at": now,
        "realized_path": realized,
        "realized_signature": realized_sig,
        "reconstruction_jaccard": recon,
        "reconstruction_pass": passed,
        "interventions": {
            iid: {"before": before_iv[iid], "after": iv_after.get(iid, before_iv[iid])}
            for iid in before_iv
        },
        "agents": agent_delta,
        "year": year,
    }
    bag.run(
        tenant,
        """
        MATCH (e:Episode {id: $eid})
        SET e.status = 'closed', e.closed_at = $now, e.close_result = $payload, e.closing = false
        """,
        {"eid": episode_id, "now": now, "payload": json.dumps(payload, sort_keys=True)},
    )
    return bag.envelope(payload)
