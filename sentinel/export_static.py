"""Record real FalkorDB runs as JSON for the static (GitHub Pages) replay demo.

    python -m sentinel.export_static [--out site/data]

For every tenant this drives the real API (FastAPI TestClient -> real FalkorDB) through the
double-run backtest flow: reset -> run 2024 -> close_episode -> run 2025. After each step it
records every read endpoint the dashboard uses (episode probes, graph_snapshot,
recommendations, explain for EVERY recommendation, all memory layers). The replay shim in
site/app answers the dashboard's fetch() calls from these files, so the UI flow is identical
to the live app, but nothing is recomputed in the browser.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from sentinel import config

LAYERS = ["episodic", "semantic", "procedural", "corridor", "signal", "governance"]


def _sse(text: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    steps, done = [], None
    for block in text.split("\n\n"):
        event, data = "message", ""
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data += line[5:].strip()
        if not data:
            continue
        payload = json.loads(data)
        if event == "step":
            steps.append(payload)
        elif event == "done":
            done = payload
    return steps, done


class Recorder:
    def __init__(self, client: TestClient, tenant: str):
        self.c = client
        self.t = tenant

    def get(self, path: str) -> dict[str, Any]:
        r = self.c.get(path)
        try:
            body = r.json()
        except Exception:  # noqa: BLE001
            body = {"detail": r.text}
        return {"status": r.status_code, "body": body}

    def snapshot_reads(self) -> dict[str, Any]:
        t = self.t
        reads: dict[str, Any] = {}
        for year in (2024, 2025):
            key = f"/api/{t}/episode/{year}"
            reads[key] = self.get(key)
            info = reads[key]["body"] if reads[key]["status"] == 200 else {}
            eid = info.get("id") if isinstance(info, dict) else None
            if not eid or info.get("status") in (None, "absent"):
                continue
            for p in (f"/api/{t}/snapshot/{eid}", f"/api/{t}/recommendations/{eid}"):
                reads[p] = self.get(p)
            recs = reads[f"/api/{t}/recommendations/{eid}"]["body"].get("recommendations", [])
            for rec in recs:
                rid = rec.get("id")
                if rid:
                    p = f"/api/{t}/explain/{rid}"
                    reads[p] = self.get(p)
        for layer in LAYERS:
            p = f"/api/{t}/memory/{layer}"
            reads[p] = self.get(p)
        return reads


def export_tenant(client: TestClient, tenant: str) -> dict[str, Any]:
    rec = Recorder(client, tenant)
    out: dict[str, Any] = {"tenant": tenant, "stages": {}, "actions": {}}

    r = client.post(f"/api/{tenant}/reset")
    r.raise_for_status()
    out["actions"]["reset"] = r.json()
    out["stages"]["fresh"] = rec.snapshot_reads()

    for year, stage in ((2024, "ran2024"), (None, "closed2024"), (2025, "ran2025")):
        if year is None:
            info = client.get(f"/api/{tenant}/episode/2024").json()
            r = client.post(f"/api/{tenant}/close/{info['id']}")
            r.raise_for_status()
            out["actions"]["close2024"] = {"episode_id": info["id"], "body": r.json()}
        else:
            r = client.post(f"/api/{tenant}/run/{year}")
            r.raise_for_status()
            steps, done = _sse(r.text)
            if done is None:
                raise RuntimeError(f"run {year} for {tenant} produced no done event")
            out["actions"][f"run{year}"] = {"steps": steps, "done": done}
        out["stages"][stage] = rec.snapshot_reads()
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="site/data")
    args = ap.parse_args(argv)

    from sentinel.api.main import app

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    client = TestClient(app)
    health = client.get("/health").json()
    tenants = client.get("/api/tenants").json()
    t0 = time.perf_counter()
    summary = {}
    for t in config.TENANTS:
        data = export_tenant(client, t)
        (outdir / f"{t}.json").write_text(json.dumps(data, separators=(",", ":"), default=str))
        close = data["actions"]["close2024"]["body"].get("result", {})
        recs25 = data["actions"]["run2025"]["done"].get("recommendations", [])
        summary[t] = {
            "reconstruction_jaccard": close.get("reconstruction_jaccard"),
            "reconstruction_pass": close.get("reconstruction_pass"),
            "recs_2025": len(recs25),
            "escalate_2025": sum(1 for x in recs25 if x.get("kind") == "escalate" or x.get("status") == "escalate"),
        }
        print(f"[export] {t}: {(outdir / f'{t}.json').stat().st_size // 1024} KB  {summary[t]}")
    meta = {
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "elapsed_s": round(time.perf_counter() - t0, 2),
        "health": health,
        "tenants": tenants,
        "summary": summary,
        "note": "Static replay of recorded FalkorDB runs. Synthetic archetype data. Run locally for the live graph.",
    }
    (outdir / "meta.json").write_text(json.dumps(meta, indent=2, default=str))
    print(f"[export] wrote {outdir}/meta.json")


if __name__ == "__main__":
    main()
