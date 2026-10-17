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

## Phase 1

- **Extra corridor branches for the demo.** Added `zaid_pulse` / `mandi_pulse` so the moong stage has a typed path, and `rice_reproductive` / `rice_paddy` / `mandi_rice` so Kalinagar's semantic layer produces different top paths. `LivestockStage` carries the same doy window fields as `CropStage` (year-round 1–366) so timing factor is defined.
- **Wheat window ends on doy 126.** Forecast doy 136 is exactly 10 days later, so T = 0.6 (near). Weather will only attack far-miss windows (T = 0.2) — that decision is recorded here and implemented in the weather agent.
- **Library HAD_OUTCOME does not increment trials.** `interventions.json` holds the canonical trials/successes/last_trial_year. Seed writes history edges for explain(); `close_episode` is the only writer that bumps counters.
- **Held-out JSON is not loaded at seed.** `load_heldout()` exists for `close_episode` only.
- **Officer `tenant` property** filters DM nodes per graph. Domain officers use `tenant: "*"` and are copied into both graphs.
- **Indexes:** `CREATE INDEX FOR (n:Label) ON (n.prop)`, ignoring already-exists errors so `make seed` is idempotent.
- **Forecast numbers in the graph are the synthetic fallbacks**, with `tmax_placeholder` / `anomaly_placeholder` set to `TODO_REAL_VALUE` when the JSON still has the placeholder.
- **Wheat PRESSURES weight 0.95 / conf 0.90** so the grain path lands in the top-K=6 after exposure and T=0.6. The 2-hop dairy exposure path is the UNPRECEDENTED highlight in top-K; the 5-hop dairy branch stays in the corridor with no targeting intervention.
- **FalkorDB path binding:** `(h)-[rels*2..5]->` raises `Type mismatch: expected List or Null but was Path`. Enumerate uses `MATCH p = (h)-[*2..5]->(o)` plus `relationships(p)` / `nodes(p)`.

## Phase 2

- **Adjudication order.** Mutual same-path attacks have two stable models. The fixpoint is Gauss–Seidel, hypotheses judged in increasing `(proposer credibility, eff_confidence, id)` so the weaker claim falls first and its attack is dropped. Defeat of a same-path rival then cannot sink the remaining hyp.
- **Hit/miss at close.** An agent scores one hit if any of its hypotheses has Jaccard ≥ 0.6 against the primary realized path or any `also_realized` path; otherwise one miss.
