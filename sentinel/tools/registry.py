"""Single tool list used by MCP, REST, and agents."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sentinel.tools.adjudicate import compute_accepted_risk
from sentinel.tools.episodes import close_episode
from sentinel.tools.explain import explain
from sentinel.tools.hypotheses import attack_hypothesis, propose_hypothesis, support_hypothesis
from sentinel.tools.memory import memory_view
from sentinel.tools.paths import enumerate_cascade_paths
from sentinel.tools.precedent import query_precedent
from sentinel.tools.recommend import recommend_action
from sentinel.tools.snapshot import graph_snapshot

ToolFn = Callable[..., dict]


TOOLS: list[dict[str, Any]] = [
    {
        "name": "enumerate_cascade_paths",
        "description": "Rank 3–5 hop cascade paths (top K) and return 1–2 hop direct-exposure paths from the episode forecast's hazard to health outcomes.",
        "fn": enumerate_cascade_paths,
        "params": ["tenant", "episode_id", "k"],
    },
    {
        "name": "query_precedent",
        "description": "Find analog closed episodes and intervention history for a cascade path.",
        "fn": query_precedent,
        "params": ["tenant", "episode_id", "path_signature", "k"],
    },
    {
        "name": "propose_hypothesis",
        "description": "Write an agent hypothesis about a path and MERGE the MAY_TRIGGER edge.",
        "fn": propose_hypothesis,
        "params": ["tenant", "agent_id", "episode_id", "path_signature", "claim", "confidence"],
    },
    {
        "name": "support_hypothesis",
        "description": "Assert supporting evidence on a hypothesis.",
        "fn": support_hypothesis,
        "params": ["tenant", "agent_id", "hypothesis_id", "evidence"],
    },
    {
        "name": "attack_hypothesis",
        "description": "Assert attacking evidence on a hypothesis.",
        "fn": attack_hypothesis,
        "params": ["tenant", "agent_id", "hypothesis_id", "evidence"],
    },
    {
        "name": "compute_accepted_risk",
        "description": "Adjudicate hypotheses to accepted / contested / defeated by the in-graph fixpoint.",
        "fn": compute_accepted_risk,
        "params": ["tenant", "episode_id"],
    },
    {
        "name": "recommend_action",
        "description": "Recommend interventions with precedent, or escalate UNPRECEDENTED paths.",
        "fn": recommend_action,
        "params": ["tenant", "episode_id"],
    },
    {
        "name": "close_episode",
        "description": "Reveal held-out outcomes, write back trials and credibility. Idempotent.",
        "fn": close_episode,
        "params": ["tenant", "episode_id"],
    },
    {
        "name": "explain",
        "description": "Explain a recommendation: path, analogs, precedents, defeated rivals, Cypher, owner.",
        "fn": explain,
        "params": ["tenant", "recommendation_id"],
    },
    {
        "name": "memory_view",
        "description": "Counts and samples of an episodic, semantic, or procedural memory layer.",
        "fn": memory_view,
        "params": ["tenant", "layer"],
    },
    {
        "name": "graph_snapshot",
        "description": "Cytoscape elements for the episode graph with status and layer classes.",
        "fn": graph_snapshot,
        "params": ["tenant", "episode_id"],
    },
]

TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}


def call_tool(name: str, **kwargs: Any) -> dict:
    spec = TOOLS_BY_NAME[name]
    return spec["fn"](**kwargs)


def list_tool_names() -> list[str]:
    return [t["name"] for t in TOOLS]
