# Decisions

Simple, demo-strong choices made while building. Update this file whenever something is unclear.

## Phase 0

- **Local FalkorDB has no password.** Demo day friction is worse than an open local port. Production target (README) uses auth.
- **`make up` starts only FalkorDB.** The API runs on the host via `make demo` so `python -c "from sentinel.db import ping"` works without dockerizing the client. `docker compose --profile full up` builds the API container.
- **Python 3.11 in Docker, `requires-python >= 3.11` locally.** This machine has 3.13; that is accepted.
- **`ping()` runs `RETURN 1` on graph `sentinel_health`.** Returns the integer 1 so the acceptance command prints `1`.
- **Query helper keeps an in-process log** of every Cypher string, params, and elapsed ms. The backtest footer reads it. Debug printing is opt-in via `SENTINEL_LOG_CYPHER=1`.
- **Browser UI on host port 3000** (FalkorDB image default). Linked from the app header.

## Seed / data honesty

- All district names are fictional. Every data node carries `provenance: 'synthetic'` except `(:Source)` nodes that point at real public portals (no numeric figures copied from those portals).
- Day-one forecast fields that would be IMD values are stored as `"tmax_c": "TODO_REAL_VALUE"` with a synthetic fallback used at runtime. The README states the shipped numbers are synthetic.
