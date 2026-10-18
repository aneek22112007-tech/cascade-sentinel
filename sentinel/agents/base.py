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


def dominant_in_window_stage(view: "EpisodeView") -> str | None:
    """The in-window crop stage that covers the most planted area in this district.

    Rajpur: wheat grain-fill is out of window on the forecast doy, so fodder jowar (0.30) wins.
    Kalinagar: rice reproductive (0.55) wins. Fully determined by the semantic layer.
    """
    from sentinel import config
    from sentinel.formulas import timing_factor

    doy = int(view.forecast.get("doy") or 0)
    best, best_area = None, -1.0
    for stage, area in sorted(view.area_share.items()):
        if stage not in view.windows:
            continue
        if timing_factor(doy, *view.windows[stage]) != config.TIMING_IN_WINDOW:
            continue
        if area > best_area:
            best, best_area = stage, area
    return best


class Agent:
    agent_id: str = ""

    def propose(self, view: EpisodeView) -> list[ToolCall]:
        raise NotImplementedError

    def critique(self, view: EpisodeView, rivals: list[dict[str, Any]]) -> list[ToolCall]:
        return []

    def call(self, name: str, summary: str, **kwargs: Any) -> ToolCall:
        return ToolCall(name=name, kwargs=kwargs, agent=self.agent_id, summary=summary)
