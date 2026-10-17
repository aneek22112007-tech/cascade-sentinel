"""compute_accepted_risk — in-graph adjudication fixpoint."""

from __future__ import annotations

from sentinel import config
from sentinel.formulas import credibility, effective_confidence
from sentinel.tools.common import CypherBag


def compute_accepted_risk(tenant: str, episode_id: str) -> dict:
    bag = CypherBag()
    hyps_rows = bag.run(
        tenant,
        """
        MATCH (a:Agent)-[:PROPOSED]->(h:Hypothesis {episode_id: $eid})-[:ABOUT]->(p:CascadePath)
        RETURN h.id, h.path_signature, h.claim, h.confidence, h.status,
               a.id, a.hits, a.misses, a.credibility, p.score
        """,
        {"eid": episode_id},
    ).rows

    hyps: list[dict] = []
    cred: dict[str, float] = {}
    by_agent_path: dict[tuple[str, str], str] = {}
    for hid, sig, claim, conf, status, aid, hits, misses, stored_c, pscore in hyps_rows:
        C = float(stored_c if stored_c is not None else credibility(int(hits), int(misses)))
        cred[aid] = C
        hyps.append(
            {
                "id": hid,
                "path_signature": sig,
                "claim": claim,
                "confidence": float(conf),
                "status": status or "proposed",
                "agent_id": aid,
                "path_score": float(pscore or 0.0),
            }
        )
        by_agent_path[(aid, sig)] = hid

    ev_rows = bag.run(
        tenant,
        """
        MATCH (a:Agent)-[:ASSERTED]->(e:Evidence)-[r:SUPPORTS|ATTACKS]->(h:Hypothesis {episode_id: $eid})
        RETURN h.id, type(r), coalesce(r.strength, e.strength), a.id
        """,
        {"eid": episode_id},
    ).rows
    supports: dict[str, list[tuple[str, float]]] = {h["id"]: [] for h in hyps}
    attacks: dict[str, list[tuple[str, float]]] = {h["id"]: [] for h in hyps}
    for hid, typ, strength, aid in ev_rows:
        if hid not in supports:
            supports[hid] = []
            attacks[hid] = []
        if typ == "SUPPORTS":
            supports[hid].append((aid, float(strength)))
        else:
            attacks[hid].append((aid, float(strength)))

    statuses = {h["id"]: h["status"] or "proposed" for h in hyps}
    reasons: dict[str, str] = {}
    numbers: dict[str, dict[str, float]] = {}

    # Gauss–Seidel in increasing (credibility, eff, id) order so a weaker
    # rival falls first and its same-path attack is dropped. Mutual-attack
    # maps otherwise oscillate and never hit a unique fixpoint.
    def _sort_key(h: dict) -> tuple:
        C_prop = cred[h["agent_id"]]
        eff = effective_confidence(h["confidence"], C_prop)
        return (C_prop, eff, h["id"])

    ordered = sorted(hyps, key=_sort_key)

    for _ in range(config.ADJUDICATION_MAX_ITERS):
        changed = False
        nxt = dict(statuses)
        for h in ordered:
            hid = h["id"]
            sig = h["path_signature"]
            C_prop = cred[h["agent_id"]]
            eff = effective_confidence(h["confidence"], C_prop)
            sup = 0.0
            for aid, st in supports.get(hid, []):
                sup += st * cred.get(aid, credibility(0, 0))
            att = 0.0
            for aid, st in attacks.get(hid, []):
                other = by_agent_path.get((aid, sig))
                if other and nxt.get(other) == "defeated":
                    continue
                att += st * cred.get(aid, credibility(0, 0))
            if att >= sup + config.DEFEAT_EFF_COEFF * eff:
                status = "defeated"
                reason = (
                    f"defeated: attack {att:.2f} ≥ support {sup:.2f} + "
                    f"{config.DEFEAT_EFF_COEFF}·eff {eff:.2f} "
                    f"({h['agent_id']} credibility {C_prop:.2f})"
                )
            elif eff + sup - att >= config.ACCEPT_THRESHOLD:
                status = "accepted"
                reason = (
                    f"accepted: eff {eff:.2f} + support {sup:.2f} − attack {att:.2f} "
                    f"≥ {config.ACCEPT_THRESHOLD}"
                )
            else:
                status = "proposed"
                reason = (
                    f"contested: eff {eff:.2f} + support {sup:.2f} − attack {att:.2f} "
                    f"< {config.ACCEPT_THRESHOLD}"
                )
            if status != statuses.get(hid):
                changed = True
            nxt[hid] = status
            reasons[hid] = reason
            numbers[hid] = {"support": sup, "attack": att, "eff": eff, "credibility": C_prop}
        statuses = nxt
        if not changed:
            break

    out_hyps = []
    for h in hyps:
        hid = h["id"]
        nums = numbers.get(hid, {"support": 0.0, "attack": 0.0, "eff": 0.0})
        bag.run(
            tenant,
            """
            MATCH (h:Hypothesis {id: $hid})
            SET h.status = $status, h.reason = $reason,
                h.eff_confidence = $eff, h.support = $sup, h.attack = $att
            """,
            {
                "hid": hid,
                "status": statuses[hid],
                "reason": reasons.get(hid, ""),
                "eff": nums["eff"],
                "sup": nums["support"],
                "att": nums["attack"],
            },
        )
        display = "contested" if statuses[hid] == "proposed" else statuses[hid]
        out_hyps.append(
            {
                "id": hid,
                "episode_id": episode_id,
                "path_signature": h["path_signature"],
                "agent_id": h["agent_id"],
                "claim": h["claim"],
                "confidence": h["confidence"],
                "eff_confidence": nums["eff"],
                "status": statuses[hid],
                "display_status": display,
                "reason": reasons.get(hid, ""),
                "support": nums["support"],
                "attack": nums["attack"],
                "path_score": h["path_score"],
            }
        )

    path_status: dict[str, str] = {}
    for h in out_hyps:
        sig = h["path_signature"]
        cur = path_status.get(sig, "defeated")
        st = h["status"]
        rank = {"accepted": 3, "proposed": 2, "defeated": 1}
        if rank.get(st, 0) > rank.get(cur, 0):
            path_status[sig] = st

    return bag.envelope(
        {
            "episode_id": episode_id,
            "hypotheses": out_hyps,
            "path_status": path_status,
            "accepted_paths": [s for s, st in path_status.items() if st == "accepted"],
            "contested_paths": [s for s, st in path_status.items() if st == "proposed"],
            "defeated_paths": [s for s, st in path_status.items() if st == "defeated"],
        }
    )
