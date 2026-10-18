"""Load seed JSON into sentinel_<tenant> graphs with MERGE (idempotent)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sentinel import config
from sentinel.db import query
from sentinel.formulas import credibility, path_signature, precedent_weight
from sentinel.schema import ensure_schema

SEED_DIR = Path(__file__).resolve().parent

# District files load before officers so OWNS edges can MATCH the district node.
SHARED_BEFORE_DISTRICT = [
    "sources.json",
    "corridor.json",
    "agents.json",
    "interventions.json",
]
SHARED_AFTER_DISTRICT = [
    "officers.json",
]

DISTRICT_FILE = {
    "demo": "district_rajpur.json",
    "district_b": "district_kalinagar.json",
}


def seed_archetype(tenant: str) -> str:
    """Map a graph tenant to the seed JSON it clones. `test_*` graphs clone demo."""
    if tenant in DISTRICT_FILE:
        return tenant
    if tenant.startswith("test_"):
        return "demo"
    raise ValueError(f"unknown tenant {tenant!r}")

TODO = "TODO_REAL_VALUE"


def _load_json(name: str) -> dict[str, Any]:
    return json.loads((SEED_DIR / name).read_text())


def load_heldout() -> dict[str, Any]:
    """Held-out outcomes. Tools other than close_episode must not call this."""
    return _load_json("backtest_heldout.json")


def resolve_todo(value: Any, fallback: Any) -> Any:
    if value == TODO:
        return fallback
    return value


def _set_clause(props: dict[str, Any], skip: set[str] | None = None) -> tuple[str, dict[str, Any]]:
    skip = skip or set()
    parts: list[str] = []
    params: dict[str, Any] = {}
    for i, (key, val) in enumerate(props.items()):
        if key in skip or val is None:
            continue
        if not key.replace("_", "").isalnum():
            raise ValueError(f"illegal property name {key!r}")
        pk = f"p{i}"
        parts.append(f"n.{key} = ${pk}")
        params[pk] = val
    return ", ".join(parts), params


def merge_node(tenant: str, item: dict[str, Any]) -> None:
    labels: list[str] = list(item["labels"])
    nid = item["id"]
    props = dict(item.get("properties") or {})
    props["id"] = nid

    if "hits" in props and "misses" in props:
        props["credibility"] = credibility(int(props["hits"]), int(props["misses"]))

    if "trials" in props and "successes" in props and "last_trial_year" in props:
        props["precedent_weight"] = precedent_weight(
            int(props["successes"]),
            int(props["trials"]),
            int(props["last_trial_year"]),
            current_year=2024,
        )

    label = labels[0]
    set_sql, params = _set_clause(props, skip={"id"})
    params["id"] = nid
    extra = "".join(f" SET n:{lab}" for lab in labels[1:])
    if set_sql:
        cypher = f"MERGE (n:{label} {{id: $id}}) SET {set_sql}" + extra
    else:
        cypher = f"MERGE (n:{label} {{id: $id}})" + extra
    query(tenant, cypher, params)

    src = props.get("source")
    if isinstance(src, str) and src.startswith("src_"):
        merge_edge(
            tenant,
            nid,
            src,
            "CITES",
            {"weight": 1.0, "confidence": 1.0, "lag_days": 0, "source": src},
        )


def merge_edge(tenant: str, src: str, dst: str, rel_type: str, props: dict[str, Any] | None = None) -> None:
    props = dict(props or {})
    set_parts: list[str] = []
    params: dict[str, Any] = {"src": src, "dst": dst}
    for i, (key, val) in enumerate(props.items()):
        if val is None:
            continue
        if not key.replace("_", "").isalnum():
            raise ValueError(f"illegal property name {key!r}")
        pk = f"e{i}"
        set_parts.append(f"r.{key} = ${pk}")
        params[pk] = val
    set_sql = f" SET {', '.join(set_parts)}" if set_parts else ""
    cypher = (
        f"MATCH (a {{id: $src}}), (b {{id: $dst}}) "
        f"MERGE (a)-[r:{rel_type}]->(b)"
        f"{set_sql}"
    )
    query(tenant, cypher, params)


def _keep_node(item: dict[str, Any], tenant: str) -> bool:
    t = (item.get("properties") or {}).get("tenant")
    if t is None or t == "*":
        return True
    return t == tenant


def load_graph_file(tenant: str, filename: str, *, seed_as: str | None = None) -> None:
    keep = seed_as or tenant
    data = _load_json(filename)
    for node in data.get("nodes") or []:
        if _keep_node(node, keep):
            merge_node(tenant, node)
    for edge in data.get("edges") or []:
        merge_edge(tenant, edge["from"], edge["to"], edge["type"], edge.get("properties") or {})


def _ensure_season(tenant: str, year: int) -> str:
    sid = f"season_{year}"
    merge_node(
        tenant,
        {
            "id": sid,
            "labels": ["Season"],
            "properties": {
                "year": year,
                "provenance": "synthetic",
                "layer": "episodic",
            },
        },
    )
    return sid


def _ensure_forecast(
    tenant: str,
    spec: dict[str, Any],
    district_id: str,
    hazard_id: str = "heatwave",
) -> str:
    fid = spec["id"]
    tmax = resolve_todo(spec.get("tmax_c"), spec.get("tmax_c_synthetic_fallback", config.SYNTHETIC_TMAX_C))
    anomaly = resolve_todo(
        spec.get("anomaly_c"), spec.get("anomaly_c_synthetic_fallback", config.SYNTHETIC_ANOMALY_C)
    )
    merge_node(
        tenant,
        {
            "id": fid,
            "labels": ["Forecast"],
            "properties": {
                "tenant": tenant,
                "issued_date": spec["issued_date"],
                "valid_from": spec["valid_from"],
                "valid_to": spec["valid_to"],
                "doy": int(spec["doy"]),
                "tmax_c": float(tmax),
                "anomaly_c": float(anomaly),
                "duration_days": int(spec.get("duration_days", config.SYNTHETIC_DURATION_DAYS)),
                "tmax_placeholder": spec["tmax_c"] if spec.get("tmax_c") == TODO else None,
                "anomaly_placeholder": spec["anomaly_c"] if spec.get("anomaly_c") == TODO else None,
                "source": spec.get("source", "src_synthetic_episode"),
                "provenance": "synthetic",
                "layer": "signal",
            },
        },
    )
    merge_edge(
        tenant,
        fid,
        hazard_id,
        "INSTANCE_OF",
        {"weight": 1.0, "confidence": 1.0, "lag_days": 0, "source": spec.get("source", "src_synthetic_episode")},
    )
    merge_edge(
        tenant,
        fid,
        district_id,
        "FOR",
        {"weight": 1.0, "confidence": 1.0, "lag_days": 0, "source": spec.get("source", "src_synthetic_episode")},
    )
    return fid


def load_episode_library(tenant: str, *, seed_as: str | None = None) -> None:
    seed_as = seed_as or seed_archetype(tenant)
    data = _load_json("episodes_library.json")
    aliases: dict[str, list[str]] = data["path_aliases"]
    for ep in data["episodes"]:
        if ep["tenant"] != seed_as:
            continue
        year = int(ep["season_year"])
        sid = _ensure_season(tenant, year)
        fid = _ensure_forecast(tenant, ep["forecast"], ep["district"])
        merge_node(
            tenant,
            {
                "id": ep["id"],
                "labels": ["Episode"],
                "properties": {
                    "season_id": sid,
                    "status": "closed",
                    "opened_at": ep["opened_at"],
                    "closed_at": ep["closed_at"],
                    "provenance": "synthetic",
                    "layer": "episodic",
                    "source": "src_synthetic_episode",
                },
            },
        )
        merge_edge(
            tenant,
            ep["id"],
            ep["district"],
            "IN",
            {"weight": 1.0, "confidence": 1.0, "lag_days": 0, "source": "src_synthetic_episode"},
        )
        merge_edge(
            tenant,
            ep["id"],
            fid,
            "TRIGGERED_BY",
            {"weight": 1.0, "confidence": 1.0, "lag_days": 0, "source": "src_synthetic_episode"},
        )
        path_ids = aliases[ep["realized_path"]] if isinstance(ep["realized_path"], str) else list(ep["realized_path"])
        sig = path_signature(path_ids)
        merge_node(
            tenant,
            {
                "id": f"path_{sig}",
                "labels": ["CascadePath"],
                "properties": {
                    "signature": sig,
                    "node_ids": path_ids,
                    "score": 0.0,
                    "realized": True,
                    "provenance": "synthetic",
                    "layer": "episodic",
                },
            },
        )
        merge_edge(
            tenant,
            ep["id"],
            f"path_{sig}",
            "FOLLOWED_PATH",
            {"weight": 1.0, "confidence": 1.0, "lag_days": 0, "source": "src_synthetic_episode"},
        )
        for obs in ep.get("observations") or []:
            merge_edge(
                tenant,
                ep["id"],
                obs["node"],
                "OBSERVED",
                {
                    "date": obs["date"],
                    "value": obs["value"],
                    "unit": obs["unit"],
                    "source": obs.get("source", "src_synthetic_episode"),
                    "weight": 1.0,
                    "confidence": 1.0,
                    "lag_days": 0,
                },
            )
        for out in ep.get("outcomes") or []:
            oid = f"out_{ep['id']}_{out['intervention_id']}"
            merge_node(
                tenant,
                {
                    "id": oid,
                    "labels": ["Outcome"],
                    "properties": {
                        "description": out["description"],
                        "provenance": "synthetic",
                        "layer": "procedural",
                    },
                },
            )
            merge_edge(
                tenant,
                out["intervention_id"],
                oid,
                "HAD_OUTCOME",
                {
                    "episode_id": ep["id"],
                    "success": bool(out["success"]),
                    "effect_size": float(out["effect_size"]),
                    "source": "src_synthetic_episode",
                    "year": year,
                    "weight": 1.0,
                    "confidence": 1.0,
                    "lag_days": 0,
                },
            )


def load_day1_forecasts(tenant: str, *, seed_as: str | None = None) -> None:
    seed_as = seed_as or seed_archetype(tenant)
    data = _load_json("backtest_day1.json")
    for spec in data["forecasts"]:
        if spec["tenant"] != seed_as:
            continue
        spec = dict(spec)
        spec["id"] = f"fc_{int(spec['season_year'])}_{tenant}"
        _ensure_season(tenant, int(spec["season_year"]))
        _ensure_forecast(tenant, spec, spec["district"], spec.get("hazard", "heatwave"))


def label_counts(tenant: str) -> dict[str, int]:
    result = query(
        tenant,
        "MATCH (n) UNWIND labels(n) AS label RETURN label, count(n) AS c",
        header=["label", "c"],
    )
    out: dict[str, int] = {}
    for row in result.rows:
        out[str(row[0])] = int(row[1])
    return out


def rel_counts(tenant: str) -> dict[str, int]:
    result = query(
        tenant,
        "MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c",
        header=["t", "c"],
    )
    out: dict[str, int] = {}
    for row in result.rows:
        out[str(row[0])] = int(row[1])
    return out


def print_counts(tenant: str) -> dict[str, Any]:
    labels = label_counts(tenant)
    rels = rel_counts(tenant)
    n_nodes = sum(labels.values())
    n_edges = sum(rels.values())
    print(f"=== seed tenant={tenant} graph={config.graph_name(tenant)} ===")
    print("labels:")
    for k in sorted(labels):
        print(f"  {k:<24} {labels[k]:>5}")
    print("relationships:")
    for k in sorted(rels):
        print(f"  {k:<24} {rels[k]:>5}")
    print(f"nodes={n_nodes} edges={n_edges}")
    return {"tenant": tenant, "labels": labels, "relationships": rels, "nodes": n_nodes, "edges": n_edges}


def load_tenant(tenant: str) -> dict[str, Any]:
    seed_as = seed_archetype(tenant)
    ensure_schema(tenant)
    for name in SHARED_BEFORE_DISTRICT:
        load_graph_file(tenant, name, seed_as=seed_as)
    load_graph_file(tenant, DISTRICT_FILE[seed_as], seed_as=seed_as)
    for name in SHARED_AFTER_DISTRICT:
        load_graph_file(tenant, name, seed_as=seed_as)
    load_episode_library(tenant, seed_as=seed_as)
    load_day1_forecasts(tenant, seed_as=seed_as)
    return print_counts(tenant)


def load_all() -> list[dict[str, Any]]:
    return [load_tenant(t) for t in config.TENANTS]


def main() -> None:
    from sentinel.db import delete_graph

    for t in config.TENANTS:
        delete_graph(t)
        load_tenant(t)


if __name__ == "__main__":
    main()
