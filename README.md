# Cascade Sentinel

**The climate-crisis agent that refuses to act without precedent.**

> Existing science models how cascades could unfold. Sentinel remembers how they actually unfolded, which interventions actually worked, and refuses to act without precedent.

![demo screenshot placeholder](docs/screenshots/.gitkeep)

**Live demo:** _coming in Phase 9_ · **Video:** _placeholder_

## Quickstart

```bash
git clone <repo> && cd cascade-sentinel
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
make up
python -c "from sentinel.db import ping; print(ping())"   # prints 1
```

FalkorDB Browser: [http://localhost:3000](http://localhost:3000)

Further setup (`make seed`, `make demo`, backtest, MCP, tracks) lands in later phases. This commit is Phase 0 scaffold: the database is reachable.
