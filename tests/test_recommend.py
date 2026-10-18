from sentinel.tools.hypotheses import propose_hypothesis, support_hypothesis
from sentinel.tools.paths import enumerate_cascade_paths
from sentinel.tools.recommend import recommend_action

FODDER = "heatwave>fodder_jowar_vegetative>fodder>mandi_fodder>farm_laborers>heat_stress_illness"
WHEAT = "heatwave>wheat_grainfill>wheat_grain>mandi_wheat>farm_laborers>heat_stress_illness"
DAIRY = "heatwave>dairy_households>livestock_heat_stress"
DAIRY_LONG = "heatwave>dairy_cattle>milk>dairy_collection>dairy_households>livestock_heat_stress"
DIRECT = "heatwave>farm_laborers>heat_stress_illness"


def _setup(episode_2024):
    tenant, eid = episode_2024
    enumerate_cascade_paths(tenant, eid, k=6)
    propose_hypothesis(tenant, "weather", eid, FODDER, "Fodder cascade.", 0.95)
    propose_hypothesis(tenant, "weather", eid, DIRECT, "Direct exposure.", 0.9)
    propose_hypothesis(tenant, "weather", eid, DAIRY, "Dairy branch.", 0.55)
    propose_hypothesis(tenant, "weather", eid, DAIRY_LONG, "Five-hop dairy cascade.", 0.55)
    wheat = propose_hypothesis(tenant, "agronomy", eid, WHEAT, "Wheat grain path.", 0.9)["result"]
    support_hypothesis(
        tenant,
        "agronomy",
        wheat["id"],
        {"kind": "area", "statement": "wheat area 0.45", "strength": 0.5},
    )
    return tenant, eid


def test_act_defeated_precedent_and_escalate(episode_2024):
    tenant, eid = _setup(episode_2024)
    recs = recommend_action(tenant, eid)["result"]["recommendations"]
    by_iv = {r.get("intervention_id"): r for r in recs if r.get("intervention_id")}
    kinds = {r["kind"] for r in recs}

    assert "act" in kinds
    assert "defeated_precedent" in kinds
    assert "escalate" in kinds

    assert by_iv["work_hour_shift"]["kind"] == "act"
    assert by_iv["work_hour_shift"]["precedent_weight"] >= 0.5
    assert by_iv["fodder_bank"]["kind"] == "act"
    assert by_iv["worksite_cool_shelters"]["kind"] == "defeated_precedent"
    assert by_iv["worksite_cool_shelters"]["precedent_weight"] < 0.5
    assert by_iv["mandi_price_advisory"]["kind"] == "defeated_precedent"

    escalates = [r for r in recs if r["kind"] == "escalate"]
    assert {r["path_signature"] for r in escalates} == {DAIRY}
    assert all("UNPRECEDENTED" in (r.get("message") or "") for r in escalates)

    weak = [r for r in recs if r["kind"] == "weak_analog"]
    assert any(r["path_signature"] == DAIRY_LONG for r in weak)
    assert all("WEAK ANALOG" in (r.get("message") or "") for r in weak)
    assert all(r.get("analog_episode_ids") for r in weak)


def test_never_invents_action_on_dairy(episode_2024):
    tenant, eid = _setup(episode_2024)
    recs = recommend_action(tenant, eid)["result"]["recommendations"]
    dairy_recs = [r for r in recs if r["path_signature"] == DAIRY]
    assert dairy_recs
    assert all(r["kind"] == "escalate" for r in dairy_recs)
    assert all(r.get("intervention_id") is None for r in dairy_recs)


def test_stale_recommendations_pruned_unless_approved(episode_2024):
    from sentinel.db import query

    tenant, eid = _setup(episode_2024)
    first = recommend_action(tenant, eid)["result"]["recommendations"]
    keep = {r["id"] for r in first}
    query(
        tenant,
        """
        MERGE (r:Recommendation {id: $id})
        SET r.episode_id = $eid, r.kind = 'act', r.score = 0, r.superseded = false,
            r.provenance = 'synthetic', r.layer = 'procedural'
        """,
        {"id": "rec_stale_unapproved", "eid": eid},
    )
    query(
        tenant,
        """
        MERGE (r:Recommendation {id: $id})
        SET r.episode_id = $eid, r.kind = 'act', r.score = 0, r.superseded = false,
            r.provenance = 'synthetic', r.layer = 'procedural'
        WITH r
        MATCH (o:Officer)
        WITH r, o LIMIT 1
        MERGE (o)-[:APPROVED {at: timestamp()}]->(r)
        """,
        {"id": "rec_stale_approved", "eid": eid},
    )
    second = recommend_action(tenant, eid)["result"]["recommendations"]
    returned = {r["id"] for r in second}
    assert "rec_stale_unapproved" not in returned
    assert "rec_stale_approved" not in returned
    assert keep <= returned
    gone = query(
        tenant, "MATCH (r:Recommendation {id: 'rec_stale_unapproved'}) RETURN r.id"
    ).rows
    assert gone == []
    kept = query(
        tenant,
        "MATCH (r:Recommendation {id: 'rec_stale_approved'}) RETURN r.superseded",
    ).rows
    assert kept and kept[0][0] is True
    live = query(
        tenant,
        """
        MATCH (r:Recommendation {episode_id: $eid})
        WHERE coalesce(r.superseded, false) = false
        RETURN r.id
        """,
        {"eid": eid},
    ).rows
    live_ids = {r[0] for r in live}
    assert "rec_stale_approved" not in live_ids
    assert live_ids == returned
