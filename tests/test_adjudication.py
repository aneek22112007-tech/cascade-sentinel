from sentinel.tools.adjudicate import compute_accepted_risk
from sentinel.tools.hypotheses import attack_hypothesis, propose_hypothesis, support_hypothesis
from sentinel.tools.paths import enumerate_cascade_paths

WHEAT = "heatwave>wheat_grainfill>wheat_grain>mandi_wheat>farm_laborers>heat_stress_illness"
DIRECT = "heatwave>farm_laborers>heat_stress_illness"


def test_accept_defeat_and_contested(episode_2024):
    tenant, eid = episode_2024
    enumerate_cascade_paths(tenant, eid, k=6)
    propose_hypothesis(
        tenant, "weather", eid, DIRECT, "Direct heat exposure dominates.", 0.9
    )
    propose_hypothesis(
        tenant, "agronomy", eid, WHEAT, "Wheat grain-price path dominates.", 0.9
    )
    propose_hypothesis(
        tenant, "health", eid, DIRECT, "Labour-heat morbidity.", 0.55
    )
    out = compute_accepted_risk(tenant, eid)["result"]
    by_id = {h["agent_id"] + ":" + h["path_signature"]: h for h in out["hypotheses"]}
    weather = by_id["weather:" + DIRECT]
    agronomy = by_id["agronomy:" + WHEAT]
    health = by_id["health:" + DIRECT]
    assert weather["status"] == "accepted"
    assert "accepted:" in weather["reason"]
    assert agronomy["status"] == "proposed"
    assert "contested:" in agronomy["reason"]
    assert health["status"] == "proposed"


def test_defeat_rule_and_ignored_attack_from_defeated_same_path(episode_2024):
    tenant, eid = episode_2024
    enumerate_cascade_paths(tenant, eid, k=6)
    a = propose_hypothesis(tenant, "agronomy", eid, WHEAT, "grain dominates", 0.9)["result"]
    h = propose_hypothesis(tenant, "health", eid, WHEAT, "grain is secondary", 0.5)["result"]
    attack_hypothesis(
        tenant,
        "health",
        a["id"],
        {"kind": "precedent", "statement": "grain rarely realizes", "strength": 1.0},
    )
    # agronomy attacks health on the same path; once agronomy is defeated this must not count
    attack_hypothesis(
        tenant,
        "agronomy",
        h["id"],
        {"kind": "area", "statement": "high area share", "strength": 1.0},
    )
    out = compute_accepted_risk(tenant, eid)["result"]
    by = {x["id"]: x for x in out["hypotheses"]}
    assert by[a["id"]]["status"] == "defeated"
    assert "defeated:" in by[a["id"]]["reason"]
    assert by[a["id"]]["attack"] >= by[a["id"]]["support"] + 0.5 * by[a["id"]]["eff_confidence"]
    # health's attacker (agronomy) is defeated on this path, so attack should be 0
    assert by[h["id"]]["attack"] == 0.0
    assert by[h["id"]]["status"] != "defeated"


def test_support_can_push_to_accepted(episode_2024):
    tenant, eid = episode_2024
    enumerate_cascade_paths(tenant, eid, k=6)
    hyp = propose_hypothesis(tenant, "agronomy", eid, WHEAT, "grain dominates", 0.9)["result"]
    support_hypothesis(
        tenant,
        "agronomy",
        hyp["id"],
        {"kind": "area_share", "statement": "wheat area_share 0.45", "strength": 0.5},
    )
    out = compute_accepted_risk(tenant, eid)["result"]
    h = next(x for x in out["hypotheses"] if x["id"] == hyp["id"])
    assert h["status"] == "accepted"
    assert h["support"] > 0
