PYTHON ?= python3
COMPOSE ?= docker compose
export PYTHONPATH := .

.PHONY: install up down logs ping seed demo backtest test bench mcp serve pages

install:
	$(PYTHON) -m pip install -e ".[dev]"

up:
	@if $(PYTHON) -c "from sentinel.db import ping; ping()" >/dev/null 2>&1; then \
	  echo "FalkorDB already reachable on :6379 (browser http://localhost:3000)"; \
	else \
	  $(COMPOSE) up -d falkordb; \
	  echo "Waiting for FalkorDB on :6379..."; \
	  i=0; \
	  until $(PYTHON) -c "from sentinel.db import ping; ping()" >/dev/null 2>&1; do \
	    i=$$((i+1)); \
	    if [ $$i -ge 40 ]; then echo "FalkorDB did not become ready"; exit 1; fi; \
	    sleep 1; \
	  done; \
	  echo "FalkorDB ready. Redis :6379  Browser http://localhost:3000"; \
	fi

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f falkordb

ping:
	$(PYTHON) -c "from sentinel.db import ping; print(ping())"

seed:
	$(PYTHON) -m sentinel.seed.loader

PORT ?= 8000

demo:
	$(PYTHON) -m uvicorn sentinel.api.main:app --host 0.0.0.0 --port $(PORT) --reload

backtest:
	$(PYTHON) -m sentinel.backtest --tenant demo --double-run

test:
	$(PYTHON) -m pytest -q

bench:
	$(PYTHON) bench/concurrency.py

mcp:
	$(PYTHON) -m sentinel.mcp_server --list

serve:
	$(PYTHON) -m sentinel.serve

pages:
	$(PYTHON) -m sentinel.build_pages --out site
