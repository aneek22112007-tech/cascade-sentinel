"""3 agents × N parallel proposals. Assert no lost writes."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from sentinel.db import delete_graph, query
from sentinel.seed.loader import load_tenant
from sentinel.tools.episodes import open_episode, reset_episode_runtime
from sentinel.tools.hypotheses import propose_hypothesis
from sentinel.tools.paths import enumerate_cascade_paths

AGENTS = ("weather", "agronomy", "health")
N = 25


def one_write(tenant: str, eid: str, agent: str, i: int) -> str:
    sig = f"bench>{agent}>{i}"
    out = propose_hypothesis(
        tenant,
        agent,
        eid,
        sig,
        f"concurrent proposal {agent} {i}",
        0.5,
    )
    return out["result"]["id"]


def main() -> None:
    tenant = f"test_{uuid.uuid4().hex}"
    delete_graph(tenant)
    try:
        load_tenant(tenant)
        eid = open_episode(tenant, 2024)["result"]["id"]
        reset_episode_runtime(tenant, eid)
        enumerate_cascade_paths(tenant, eid, k=6)

        jobs = [(agent, i) for i in range(N) for agent in AGENTS]
        t0 = time.perf_counter()
        ids = []
        with ThreadPoolExecutor(max_workers=12) as pool:
            futs = [pool.submit(one_write, tenant, eid, a, i) for a, i in jobs]
            for f in as_completed(futs):
                ids.append(f.result())
        elapsed = time.perf_counter() - t0
        expected = len(jobs)
        stored = query(tenant, "MATCH (h:Hypothesis {episode_id: $e}) RETURN count(h)", {"e": eid}).rows[0][0]
        unique_ids = len(set(ids))
        ops = expected / elapsed if elapsed else 0
        lost = expected - int(stored)
        print(f"agents={len(AGENTS)}  N={N}  proposed={expected}")
        print(f"returned_ids={len(ids)} unique={unique_ids} stored={stored}")
        print(f"lost_writes={lost}")
        print(f"elapsed_s={elapsed:.3f}  ops_per_s={ops:.1f}")
        if lost != 0 or unique_ids != expected:
            raise SystemExit("LOST WRITES")
        print("OK: zero lost writes")
    finally:
        delete_graph(tenant)


if __name__ == "__main__":
    main()
