"""MCP server: 11 graph tools over stdio or streamable HTTP."""

from __future__ import annotations

import argparse
import json
import sys

from mcp.server.fastmcp import FastMCP

from sentinel.tools.registry import TOOLS, call_tool, list_tool_names


INSTRUCTIONS = (
    "Cascade Sentinel graph tools. Every tool is a FalkorDB operation: "
    "traversal, precedent matching, adjudication, refusal, or write-back. "
    "All figures are synthetic archetype data unless a Source node says provenance=real. "
    "Do not invent interventions. If recommend_action returns escalate, the path is UNPRECEDENTED."
)


def build_server(host: str = "127.0.0.1", port: int = 8765) -> FastMCP:
    mcp = FastMCP(
        "cascade-sentinel",
        instructions=INSTRUCTIONS,
        host=host,
        port=port,
    )

    @mcp.tool(description=TOOLS[0]["description"])
    def enumerate_cascade_paths(tenant: str, episode_id: str, k: int = 6) -> dict:
        return call_tool("enumerate_cascade_paths", tenant=tenant, episode_id=episode_id, k=k)

    @mcp.tool(description=TOOLS[1]["description"])
    def query_precedent(tenant: str, episode_id: str, path_signature: str, k: int = 3) -> dict:
        return call_tool(
            "query_precedent",
            tenant=tenant,
            episode_id=episode_id,
            path_signature=path_signature,
            k=k,
        )

    @mcp.tool(description=TOOLS[2]["description"])
    def propose_hypothesis(
        tenant: str,
        agent_id: str,
        episode_id: str,
        path_signature: str,
        claim: str,
        confidence: float,
    ) -> dict:
        return call_tool(
            "propose_hypothesis",
            tenant=tenant,
            agent_id=agent_id,
            episode_id=episode_id,
            path_signature=path_signature,
            claim=claim,
            confidence=confidence,
        )

    @mcp.tool(description=TOOLS[3]["description"])
    def support_hypothesis(tenant: str, agent_id: str, hypothesis_id: str, evidence: dict) -> dict:
        return call_tool(
            "support_hypothesis",
            tenant=tenant,
            agent_id=agent_id,
            hypothesis_id=hypothesis_id,
            evidence=evidence,
        )

    @mcp.tool(description=TOOLS[4]["description"])
    def attack_hypothesis(tenant: str, agent_id: str, hypothesis_id: str, evidence: dict) -> dict:
        return call_tool(
            "attack_hypothesis",
            tenant=tenant,
            agent_id=agent_id,
            hypothesis_id=hypothesis_id,
            evidence=evidence,
        )

    @mcp.tool(description=TOOLS[5]["description"])
    def compute_accepted_risk(tenant: str, episode_id: str) -> dict:
        return call_tool("compute_accepted_risk", tenant=tenant, episode_id=episode_id)

    @mcp.tool(description=TOOLS[6]["description"])
    def recommend_action(tenant: str, episode_id: str) -> dict:
        return call_tool("recommend_action", tenant=tenant, episode_id=episode_id)

    @mcp.tool(description=TOOLS[7]["description"])
    def close_episode(tenant: str, episode_id: str) -> dict:
        return call_tool("close_episode", tenant=tenant, episode_id=episode_id)

    @mcp.tool(description=TOOLS[8]["description"])
    def explain(tenant: str, recommendation_id: str) -> dict:
        return call_tool("explain", tenant=tenant, recommendation_id=recommendation_id)

    @mcp.tool(description=TOOLS[9]["description"])
    def memory_view(tenant: str, layer: str) -> dict:
        return call_tool("memory_view", tenant=tenant, layer=layer)

    @mcp.tool(description=TOOLS[10]["description"])
    def graph_snapshot(tenant: str, episode_id: str) -> dict:
        return call_tool("graph_snapshot", tenant=tenant, episode_id=episode_id)

    return mcp


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cascade Sentinel MCP server")
    p.add_argument("--list", action="store_true", help="print the 11 graph tools and exit")
    p.add_argument("--http", type=int, nargs="?", const=8765, default=None, help="streamable HTTP port")
    p.add_argument("--host", default="127.0.0.1")
    args = p.parse_args(argv)

    if args.list:
        names = list_tool_names()
        print(f"{len(names)} tools:")
        for n in names:
            print(f"  - {n}")
        return 0

    if args.http:
        mcp = build_server(host=args.host, port=int(args.http))
        mcp.run(transport="streamable-http")
        return 0

    mcp = build_server()
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
