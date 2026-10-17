from sentinel.tools.hypotheses import propose_hypothesis, support_hypothesis
from sentinel.tools.paths import enumerate_cascade_paths
from sentinel.tools.recommend import recommend_action

FODDER = "heatwave>fodder_jowar_vegetative>fodder>mandi_fodder>farm_laborers>heat_stress_illness"
WHEAT = "heatwave>wheat_grainfill>wheat_grain>mandi_wheat>farm_laborers>heat_stress_illness"
DAIRY = "heatwave>dairy_households>livestock_heat_stress"
DIRECT = "heatwave>farm_laborers>heat_stress_illness"


def _setup(episode_2024):
    tenant, eid = episode_2024
    enumerate_cascade_paths(tenant, eid, k=6)
    propose_hypothesis(tenant, "weather", eid, FODDER, "Fodder cascade.", 0.95)
    propose_hypothesis(tenant, "weather", eid, DIRECT, "Direct exposure.", 0.9)
    propose_hypothesis(tenant, "weather", eid, DAIRY, "Dairy branch.", 0.55)
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
    assert escalates
    assert any(r["path_signature"] == DAIRY for r in escalates)
    assert all("UNPRECEDENTED" in (r.get("message") or "") for r in escalates)


def test_never_invents_action_on_dairy(episode_2024):
    tenant, eid = _setup(episode_2024)
    recs = recommend_action(tenant, eid)["result"]["recommendations"]
    dairy_recs = [r for r in recs if r["path_signature"] == DAIRY]
    assert dairy_recs
    assert all(r["kind"] == "escalate" for r in dairy_recs)
    assert all(r.get("intervention_id") is None for r in dairy_recs)
