"""Pydantic models for every graph tool's input and output."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolEnvelope(BaseModel):
    result: Any
    cypher: list[str]
    ms: float


class EnumerateIn(BaseModel):
    tenant: str
    episode_id: str
    k: int = 6


class PathOut(BaseModel):
    signature: str
    node_ids: list[str]
    types: list[str]
    score: float
    lag_days: int
    intensity: float
    timing: float
    exposure: float
    base: float
    rank: int


class PrecedentIn(BaseModel):
    tenant: str
    episode_id: str
    path_signature: str
    k: int = 3


class AnalogOut(BaseModel):
    episode_id: str
    signature: str
    node_ids: list[str]
    similarity: float
    year: int | None = None


class InterventionHistoryOut(BaseModel):
    id: str
    name: str
    trials: int
    successes: int
    precedent_weight: float
    last_trial_year: int | None = None
    targets: list[str] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)
    in_analog: bool = False


class ProposeIn(BaseModel):
    tenant: str
    agent_id: str
    episode_id: str
    path_signature: str
    claim: str
    confidence: float


class EvidenceIn(BaseModel):
    kind: str = "note"
    statement: str
    value: float | str | None = None
    strength: float
    source: str = "src_synthetic_episode"


class SupportIn(BaseModel):
    tenant: str
    agent_id: str
    hypothesis_id: str
    evidence: EvidenceIn


class AttackIn(BaseModel):
    tenant: str
    agent_id: str
    hypothesis_id: str
    evidence: EvidenceIn


class HypothesisOut(BaseModel):
    id: str
    episode_id: str
    path_signature: str
    agent_id: str
    claim: str
    confidence: float
    eff_confidence: float
    status: Literal["proposed", "accepted", "defeated"]
    reason: str = ""
    support: float = 0.0
    attack: float = 0.0


class RecommendIn(BaseModel):
    tenant: str
    episode_id: str


class RecommendationOut(BaseModel):
    id: str
    episode_id: str
    path_signature: str
    kind: Literal["act", "escalate", "defeated_precedent", "weak_analog"]
    score: float
    intervention_id: str | None = None
    intervention_name: str | None = None
    message: str | None = None
    precedent_weight: float | None = None
    trials: int | None = None
    successes: int | None = None
    analog_episode_ids: list[str] = Field(default_factory=list)


class CloseIn(BaseModel):
    tenant: str
    episode_id: str


class ExplainIn(BaseModel):
    tenant: str
    recommendation_id: str


class MemoryIn(BaseModel):
    tenant: str
    layer: str


class SnapshotIn(BaseModel):
    tenant: str
    episode_id: str


class OpenEpisodeIn(BaseModel):
    tenant: str
    season_year: int
