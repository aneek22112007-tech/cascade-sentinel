from sentinel.formulas import path_signature
from sentinel.tools.paths import enumerate_cascade_paths

FODDER = path_signature(
    [
        "heatwave",
        "fodder_jowar_vegetative",
        "fodder",
        "mandi_fodder",
        "farm_laborers",
        "heat_stress_illness",
    ]
)
WHEAT = path_signature(
    [
        "heatwave",
        "wheat_grainfill",
        "wheat_grain",
        "mandi_wheat",
        "farm_laborers",
        "heat_stress_illness",
    ]
)
DIRECT = path_signature(["heatwave", "farm_laborers", "heat_stress_illness"])
DAIRY_SHORT = path_signature(["heatwave", "dairy_households", "livestock_heat_stress"])


def test_enumerate_top_k_and_hops(episode_2024):
    tenant, eid = episode_2024
    out = enumerate_cascade_paths(tenant, eid, k=6)
    paths = out["result"]["paths"]
    direct = out["result"]["direct_exposure"]
    assert 1 <= len(paths) <= 6
    assert "cypher" in out and out["cypher"]
    assert out["ms"] >= 0
    sigs = {p["signature"] for p in paths}
    dsigs = {p["signature"] for p in direct}
    assert FODDER in sigs
    assert WHEAT in sigs
    assert DIRECT not in sigs
    assert DAIRY_SHORT not in sigs
    assert DIRECT in dsigs
    assert DAIRY_SHORT in dsigs
    for p in paths:
        hops = len(p["types"])
        assert 3 <= hops <= 5
        assert len(p["node_ids"]) == hops + 1
        assert p["score"] >= 0
        assert p["lag_days"] >= 0
        assert p["rank"] >= 1
        assert p["signature"].startswith("heatwave>")
    for p in direct:
        hops = len(p["types"])
        assert 1 <= hops <= 2
        assert p["signature"].startswith("heatwave>")


def test_enumerate_deterministic(episode_2024):
    tenant, eid = episode_2024
    a = enumerate_cascade_paths(tenant, eid, k=6)["result"]["paths"]
    b = enumerate_cascade_paths(tenant, eid, k=6)["result"]["paths"]
    assert [p["signature"] for p in a] == [p["signature"] for p in b]
    assert [round(p["score"], 10) for p in a] == [round(p["score"], 10) for p in b]


def test_fodder_lag_about_three_weeks(episode_2024):
    tenant, eid = episode_2024
    paths = enumerate_cascade_paths(tenant, eid, k=6)["result"]["paths"]
    fodder = next(p for p in paths if p["signature"] == FODDER)
    assert 15 <= fodder["lag_days"] <= 45
    assert fodder["timing"] == 1.0
