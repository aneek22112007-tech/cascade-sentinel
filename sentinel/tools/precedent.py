"""query_precedent — analog episodes and intervention history for a path."""

from __future__ import annotations

from sentinel import config
from sentinel.formulas import episode_similarity, precedent_weight
from sentinel.tools.common import CypherBag, episode_context, split_signature


def query_precedent(tenant: str, episode_id: str, path_signature: str, k: int = 3) -> dict:
    bag = CypherBag()
    ctx = episode_context(bag, tenant, episode_id)
    path_ids = split_signature(path_signature)
    crop_on = {n for n in path_ids if n}  # compared below via crop labels

    crop_ids = {r[0] for r in bag.run(tenant, "MATCH (c:CropStage) RETURN c.id").rows}
    current_crops = set(path_ids) & crop_ids
    profile_a = [float(x) for x in (ctx["vector"] or [])]

    analogs_raw = bag.run(
        tenant,
        """
        MATCH (e:Episode {status: 'closed'})-[:FOLLOWED_PATH]->(p:CascadePath)
        WHERE e.id <> $eid
        OPTIONAL MATCH (e)-[:IN]->(:District)-[:HAS_PROFILE]->(v:VulnerabilityProfile)
        OPTIONAL MATCH (s:Season {id: e.season_id})
        RETURN e.id, p.signature, p.node_ids, v.vector, s.year
        """,
        {"eid": episode_id},
    ).rows

    analogs: list[dict] = []
    for eid, sig, nodes, vec, year in analogs_raw:
        nodes = list(nodes or [])
        vec = [float(x) for x in (vec or [])]
        analog_crops = set(nodes) & crop_ids
        same_stage = bool(current_crops & analog_crops) if current_crops else False
        sim = episode_similarity(path_ids, nodes, same_stage, profile_a, vec)
        if sim >= config.ANALOG_SIM_MIN:
            analogs.append(
                {
                    "episode_id": eid,
                    "signature": sig,
                    "node_ids": nodes,
                    "similarity": float(sim),
                    "year": int(year) if year is not None else None,
                }
            )
    analogs.sort(key=lambda a: (-a["similarity"], a["episode_id"]))
    analogs = analogs[: int(k or 3)]
    analog_ids = [a["episode_id"] for a in analogs]

    hist = bag.run(
        tenant,
        """
        MATCH (i:Intervention)-[:TARGETS]->(n)
        WHERE n.id IN $path_ids
        OPTIONAL MATCH (i)-[o:HAD_OUTCOME]->(:Outcome)
        RETURN i.id, i.name, i.trials, i.successes, i.precedent_weight, i.last_trial_year,
               collect({episode: o.episode_id, success: o.success, year: o.year}) AS history,
               collect(DISTINCT n.id) AS targets
        """,
        {"path_ids": path_ids},
    ).rows

    year = config.CURRENT_YEAR
    interventions = []
    seen = set()
    for row in hist:
        iid, name, trials, successes, p_stored, last_year, history, targets = row
        if iid in seen:
            continue
        seen.add(iid)
        trials = int(trials or 0)
        successes = int(successes or 0)
        last_year = int(last_year) if last_year is not None else year
        p = precedent_weight(successes, trials, last_year, year)
        history = [h for h in (history or []) if h and h.get("episode")]
        in_analog = any(h.get("episode") in analog_ids for h in history)
        interventions.append(
            {
                "id": iid,
                "name": name,
                "trials": trials,
                "successes": successes,
                "precedent_weight": float(p),
                "last_trial_year": last_year,
                "targets": list(targets or []),
                "history": history,
                "in_analog": in_analog,
            }
        )

    return bag.envelope(
        {
            "path_signature": path_signature,
            "path_ids": path_ids,
            "analogs": analogs,
            "interventions": interventions,
        }
    )
