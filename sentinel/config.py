"""Env, tenant naming, and the deterministic math constants from the spec."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = Path(__file__).resolve().parent / "seed"

# --- connection ---
FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
FALKORDB_PASSWORD = os.getenv("FALKORDB_PASSWORD", "") or None

DEFAULT_TENANT = os.getenv("TENANT_DEFAULT", "demo")
TENANTS = ("demo", "district_b")

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none")
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "8"))
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "grok-4")

LOG_CYPHER = os.getenv("SENTINEL_LOG_CYPHER", "0") == "1"

# Optional. If set, mutating POST routes require header X-Sentinel-Token.
SENTINEL_ADMIN_TOKEN = os.getenv("SENTINEL_ADMIN_TOKEN", "") or ""

# UI files. Override when the wheel is installed away from the repo checkout.
SENTINEL_STATIC_DIR = Path(os.getenv("SENTINEL_STATIC_DIR") or (ROOT / "static"))

# Season clock. Backtest overrides per season. Prefer episode Season.year at read time.
CURRENT_YEAR = int(os.getenv("CURRENT_YEAR", "2024"))

# --- section 6 constants ---
TOP_K_PATHS = 6
ACCEPT_THRESHOLD = 0.6
INTENSITY_ANOMALY_SCALE = 6.0
TIMING_NEAR_DAYS = 10
TIMING_IN_WINDOW = 1.0
TIMING_NEAR = 0.6
TIMING_FAR = 0.2
ADJUDICATION_MAX_ITERS = 10
DEFEAT_EFF_COEFF = 0.5
ANALOG_SIM_MIN = 0.5
PRECEDENT_ACT_MIN = 0.5
HIT_JACCARD_MIN = 0.6
PRECEDENT_DECAY_BASE = 0.9
AREA_SHARE_ATTACK_BELOW = 0.15
WEATHER_WINDOW_MISS_STRENGTH = 0.6

# TODO_REAL_VALUE fallback used only when seed JSON still has the placeholder.
SYNTHETIC_TMAX_C = 46.0
SYNTHETIC_ANOMALY_C = 7.5
SYNTHETIC_DURATION_DAYS = 8

GRAPH_PREFIX = "sentinel_"
HEALTH_GRAPH = "sentinel_health"


def graph_name(tenant: str) -> str:
    return f"{GRAPH_PREFIX}{tenant}"


def set_current_year(year: int) -> None:
    global CURRENT_YEAR
    CURRENT_YEAR = int(year)
