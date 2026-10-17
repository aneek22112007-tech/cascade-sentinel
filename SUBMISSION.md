# Submission checklist

Hackathon: WeMakeDevs × FalkorDB Graph Hacks: Context for AI Agents.

- [x] Public GitHub repo — https://github.com/aneek22112007-tech/cascade-sentinel
- [x] README complete (quickstart, track map, math, MCP, honest limitations)
- [x] Live URL — https://ones-memo-major-aurora.trycloudflare.com (Cloudflare quick tunnel in front of local Docker FalkorDB + API; ephemeral — re-issue if it drops)
- [ ] Demo video _(placeholder for the submitter)_
- [x] Tracks entered: **1, 2, and 3**
- [ ] Blog link _(placeholder; source is BLOG_POST.md)_
- [x] FalkorDB features used: multigraph tenancy (`sentinel_<tenant>`), Cypher variable-length traversal, parameterized queries, range indexes, FalkorDB Browser on :3000
- [x] Built during the event: schema, seed, 11 graph tools, agents, double-run backtest, MCP, UI, bench

## Tracks (one line each)

1. **Agents that act on connected data.** `enumerate_cascade_paths` is a 2–5 hop traversal; `recommend_action` only fires with analog precedent, otherwise UNPRECEDENTED.
2. **Agent memory and coordination.** Episodic / semantic / procedural layers in one FalkorDB graph; agents share a hypothesis subgraph; the double-run proves write-back changes next season.
3. **Company brain.** `(:Officer)-[:OWNS]->`, approvals, escalations, every recommendation traces to `(:Source)` chips in Explain.

## What was built during the event

All FalkorDB work in this repository is new: graph model, seed, tools, tenancy, write-back, MCP, and the UI that animates paths from `graph_snapshot`.
