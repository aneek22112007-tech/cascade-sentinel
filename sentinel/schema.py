"""Idempotent indexes for every label plus status/episode_id lookups."""

from __future__ import annotations

from sentinel.db import query

LABELS = [
    "HazardType",
    "CropStage",
    "LivestockStage",
    "Commodity",
    "Market",
    "LaborGroup",
    "HealthOutcome",
    "District",
    "VulnerabilityProfile",
    "Forecast",
    "Season",
    "Episode",
    "CascadePath",
    "Agent",
    "Hypothesis",
    "Evidence",
    "Intervention",
    "Outcome",
    "Recommendation",
    "Officer",
    "Team",
    "Source",
    "Run",
]

EXTRA_INDEXES = [
    ("Episode", "status"),
    ("Hypothesis", "status"),
    ("Hypothesis", "episode_id"),
]


def _index_exists_message(exc: BaseException) -> bool:
    text = str(exc).lower()
    needles = ("already", "exists", "indexed", "equivalent")
    return any(n in text for n in needles)


def _create_index(tenant: str, label: str, prop: str) -> None:
    cypher = f"CREATE INDEX FOR (n:{label}) ON (n.{prop})"
    try:
        query(tenant, cypher)
    except Exception as exc:  # noqa: BLE001 — FalkorDB raises on duplicate index
        if not _index_exists_message(exc):
            raise


def ensure_schema(tenant: str) -> None:
    for label in LABELS:
        _create_index(tenant, label, "id")
    for label, prop in EXTRA_INDEXES:
        _create_index(tenant, label, prop)
