from sentinel.agents.orchestrator import run_season
from sentinel.db import delete_graph, query
from sentinel.seed.loader import load_tenant


def test_tenants_are_isolated_graphs():
    delete_graph("demo")
    delete_graph("district_b")
    load_tenant("demo")
    load_tenant("district_b")
    demo = query("demo", "MATCH (d:District) RETURN d.id").rows
    other = query("district_b", "MATCH (d:District) RETURN d.id").rows
    assert demo == [["rajpur"]]
    assert other == [["kalinagar"]]
    leak = query("demo", "MATCH (d:District {id:'kalinagar'}) RETURN d.id").rows
    assert leak == []


def test_semantic_layer_changes_top_paths():
    delete_graph("demo")
    delete_graph("district_b")
    load_tenant("demo")
    load_tenant("district_b")
    a = run_season("demo", 2024, with_llm=False)
    b = run_season("district_b", 2024, with_llm=False)
    demo_sigs = " ".join(p["signature"] for p in a["paths"])
    b_sigs = " ".join(p["signature"] for p in b["paths"])
    assert "fodder_jowar_vegetative" in demo_sigs
    assert "rice_reproductive" in b_sigs
    assert "rice_reproductive" not in demo_sigs or b_sigs != demo_sigs
