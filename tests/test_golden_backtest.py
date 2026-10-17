from __future__ import annotations

import json
from pathlib import Path

from sentinel.backtest import main
from sentinel.db import delete_graph
from sentinel.seed.loader import load_tenant

GOLDEN = Path(__file__).parent / "golden" / "backtest_demo.json"


def _run(tmp_path: Path) -> dict:
    delete_graph("demo")
    load_tenant("demo")
    out = tmp_path / "out.json"
    rc = main(["--tenant", "demo", "--double-run", "--json", str(out)])
    assert rc == 0
    return json.loads(out.read_text())


def _roles(payload: dict) -> dict[str, str]:
    recs = payload["season_2024"]["recommendations"]
    by = {}
    for r in recs:
        iid = r.get("intervention_id")
        if iid:
            by.setdefault(iid, r["kind"])
    recs_n = payload["season_2025"]["recommendations"]
    by_n = {}
    for r in recs_n:
        iid = r.get("intervention_id")
        if iid:
            by_n.setdefault(iid, r["kind"])
    return {"2024": by, "2025": by_n}


def test_double_run_roles_and_diffs(tmp_path):
    payload = _run(tmp_path)
    assert payload["close_2024"]["reconstruction_pass"] is True
    roles = _roles(payload)
    assert roles["2024"]["work_hour_shift"] == "act"
    assert roles["2024"]["fodder_bank"] == "act"
    assert roles["2024"].get("ors_chlorination") == "act"
    assert roles["2024"]["worksite_cool_shelters"] == "defeated_precedent"
    assert roles["2024"]["mandi_price_advisory"] == "defeated_precedent"
    assert roles["2025"]["worksite_cool_shelters"] == "act"
    assert roles["2025"].get("ors_chlorination") == "act"
    kinds_2024 = {r["kind"] for r in payload["season_2024"]["recommendations"]}
    kinds_2025 = {r["kind"] for r in payload["season_2025"]["recommendations"]}
    assert "escalate" in kinds_2024 and "escalate" in kinds_2025
    assert len(payload["diffs"]) >= 3
    wheat = [
        h
        for h in payload["season_2025"]["hypotheses"]
        if h["agent_id"] == "agronomy" and "wheat_grain" in h["path_signature"]
    ]
    assert wheat and wheat[0]["status"] == "defeated"


def test_golden_twice(tmp_path):
    a = _run(tmp_path)
    b = _run(tmp_path)
    assert a == b
    golden = json.loads(GOLDEN.read_text())
    assert a == golden
