"""Agent base: propose / critique return tool calls for the orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    name: str
    kwargs: dict[str, Any]
    agent: str = ""
    summary: str = ""


@dataclass
class EpisodeView:
    tenant: str
    episode_id: str
    season_year: int
    forecast: dict[str, Any]
    district: dict[str, Any]
    profile: dict[str, Any]
    paths: list[dict[str, Any]]
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    water_stress: float = 0.0
    area_share: dict[str, float] = field(default_factory=dict)
    outdoor_hours: dict[str, float] = field(default_factory=dict)
    crop_ids: set[str] = field(default_factory=set)
    windows: dict[str, tuple] = field(default_factory=dict)


class Agent:
    agent_id: str = ""

    def propose(self, view: EpisodeView) -> list[ToolCall]:
        raise NotImplementedError

    def critique(self, view: EpisodeView, rivals: list[dict[str, Any]]) -> list[ToolCall]:
        return []

    def call(self, name: str, summary: str, **kwargs: Any) -> ToolCall:
        return ToolCall(name=name, kwargs=kwargs, agent=self.agent_id, summary=summary)
