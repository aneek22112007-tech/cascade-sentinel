"""memory_view — counts and samples of a labelled memory layer."""

from __future__ import annotations

from sentinel.tools.common import CypherBag

LAYERS = ("episodic", "semantic", "procedural", "corridor", "signal", "governance")


def memory_view(tenant: str, layer: str) -> dict:
    if layer not in LAYERS:
        raise ValueError(f"layer must be one of {LAYERS}")
    bag = CypherBag()
    counts = bag.run(
        tenant,
        """
        MATCH (n)
        WHERE n.layer = $layer
        UNWIND labels(n) AS lab
        RETURN lab, count(n)
        """,
        {"layer": layer},
    ).rows
    samples = bag.run(
        tenant,
        """
        MATCH (n)
        WHERE n.layer = $layer
        RETURN n.id, labels(n), n.layer, n.provenance
        LIMIT 20
        """,
        {"layer": layer},
    ).rows
    edges = bag.run(
        tenant,
        """
        MATCH (a)-[r]->(b)
        WHERE a.layer = $layer OR b.layer = $layer
        RETURN count(r)
        """,
        {"layer": layer},
    ).rows
    return bag.envelope(
        {
            "layer": layer,
            "label_counts": {r[0]: int(r[1]) for r in counts},
            "edge_touch_count": int(edges[0][0]) if edges else 0,
            "samples": [
                {
                    "id": s[0],
                    "labels": list(s[1]) if s[1] else [],
                    "layer": s[2],
                    "provenance": s[3],
                }
                for s in samples
            ],
        }
    )
