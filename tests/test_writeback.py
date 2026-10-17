from sentinel.agents.orchestrator import run_season
from sentinel.db import delete_graph, query
from sentinel.formulas import precedent_weight
from sentinel.seed.loader import load_tenant
from sentinel.tools.episodes import close_episode


def test_close_writeback_and_idempotent():
    delete_graph("demo")
    load_tenant("demo")
    bundle = run_season("demo", 2024, with_llm=False)
    eid = bundle["episode_id"]
    first = close_episode("demo", eid)["result"]
    assert first["reconstruction_pass"] is True
    assert first["reconstruction_jaccard"] >= 0.6
    assert first["agents"]["agronomy"]["verdict"] == "miss"
    assert first["agents"]["weather"]["verdict"] == "hit"
    assert first["agents"]["health"]["verdict"] == "hit"
    cool = first["interventions"]["worksite_cool_shelters"]
    assert cool["after"]["successes"] == cool["before"]["successes"] + 1
    assert cool["after"]["trials"] == cool["before"]["trials"] + 1
    p = precedent_weight(
        cool["after"]["successes"],
        cool["after"]["trials"],
        cool["after"]["last_trial_year"],
        2025,
    )
    assert abs(p - 0.5) < 1e-9
    mandi = first["interventions"]["mandi_price_advisory"]
    assert mandi["after"]["trials"] == mandi["before"]["trials"]
    second = close_episode("demo", eid)["result"]
    assert second["reconstruction_jaccard"] == first["reconstruction_jaccard"]
    assert second["agents"] == first["agents"]
    row = query("demo", "MATCH (e:Episode {id:$id}) RETURN e.status", {"id": eid}).rows[0]
    assert row[0] == "closed"
