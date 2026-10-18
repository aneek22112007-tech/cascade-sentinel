"""Kalinagar (district_b): rice-dominant archetype must reconstruct its own corridor.

Regression for a seed-design bug where the agents' evidence was hard-wired to fodder
(Rajpur's dominant in-window stage), so Kalinagar's realized rice path was never accepted
(Jaccard 0.33 FAIL) and every tiny-crop path was escalated.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from sentinel.backtest import main
from sentinel.db import delete_graph
from sentinel.seed.loader import load_tenant


def _run(tmp_path: Path) -> dict:
    tenant = f"testb_{uuid.uuid4().hex}"
    delete_graph(tenant)
    try:
        load_tenant(tenant)
        out = tmp_path / "b.json"
        assert main(["--tenant", tenant, "--double-run", "--json", str(out)]) == 0
        return json.loads(out.read_text())
    finally:
        delete_graph(tenant)


def test_kalinagar_rice_reconstruction_and_refusals(tmp_path):
    p = _run(tmp_path)
    close = p["close_2024"]
    assert close["reconstruction_pass"] is True
    assert close["reconstruction_jaccard"] == 1.0
    assert "rice_reproductive" in close["realized_signature"]
    for season in ("season_2024", "season_2025"):
        esc = [r for r in p[season]["recommendations"] if r["kind"] == "escalate"]
        assert esc, "dairy must still be refused"
        assert all("dairy" in r["path_signature"] for r in esc), [r["path_signature"] for r in esc]
    kinds25 = {(r.get("intervention_id"), r["kind"]) for r in p["season_2025"]["recommendations"]}
    assert ("worksite_cool_shelters", "act") in kinds25  # memory write-back flips shelters
    assert ("work_hour_shift", "act") in kinds25
