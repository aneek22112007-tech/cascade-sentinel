from sentinel import config
from sentinel.formulas import precedent_weight
from sentinel.tools.hypotheses import propose_hypothesis
from sentinel.tools.paths import enumerate_cascade_paths
from sentinel.tools.precedent import query_precedent

FODDER = "heatwave>fodder_jowar_vegetative>fodder>mandi_fodder>farm_laborers>heat_stress_illness"


def test_query_precedent_uses_episode_year_not_global(episode_2024, monkeypatch):
    tenant, eid = episode_2024
    enumerate_cascade_paths(tenant, eid, k=6)
    propose_hypothesis(tenant, "weather", eid, FODDER, "Fodder cascade.", 0.9)
    monkeypatch.setattr(config, "CURRENT_YEAR", 2099)
    out = query_precedent(tenant, eid, FODDER, k=3)["result"]
    assert out["interventions"]
    for iv in out["interventions"]:
        expected = precedent_weight(
            int(iv["successes"]),
            int(iv["trials"]),
            int(iv["last_trial_year"]),
            2024,
        )
        collapsed = precedent_weight(
            int(iv["successes"]),
            int(iv["trials"]),
            int(iv["last_trial_year"]),
            2099,
        )
        assert abs(iv["precedent_weight"] - expected) < 1e-9
        assert abs(expected - collapsed) > 1e-6
