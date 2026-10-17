"""Health agent: labour-morbidity and water-borne paths; season N attacks grain."""

from __future__ import annotations

from typing import Any

from sentinel.agents.base import Agent, EpisodeView, ToolCall
from sentinel.tools.common import split_signature

LOW_OUTDOOR = 6.0
HIGH_WATER = 0.6


class HealthAgent(Agent):
    agent_id = "health"

    def propose(self, view: EpisodeView) -> list[ToolCall]:
        calls: list[ToolCall] = []
        seen = set()
        for path in view.paths:
            ids = path["node_ids"]
            sig = path["signature"]
            has_labor = any(n in view.outdoor_hours for n in ids)
            has_health = any(
                n in ("heat_stress_illness", "waterborne_diarrhoea", "livestock_heat_stress")
                for n in ids
            )
            if not (has_labor and has_health):
                continue
            if sig in seen:
                continue
            seen.add(sig)
            if "waterborne_diarrhoea" in ids:
                if view.water_stress < HIGH_WATER:
                    continue
                claim = (
                    f"Water-stress {view.water_stress:.2f} plus heat drives water-borne diarrhoea."
                )
                conf = 0.75
            elif "livestock_heat_stress" in ids:
                continue
            elif "heat_stress_illness" in ids and "farm_laborers" in ids:
                claim = "Labour-heat morbidity along the farm-labour chain."
                conf = 0.80 if ids[:3] == ["heatwave", "farm_laborers", "heat_stress_illness"] else 0.70
            else:
                continue
            calls.append(
                self.call(
                    "propose_hypothesis",
                    "labour-morbidity",
                    agent_id=self.agent_id,
                    episode_id=view.episode_id,
                    path_signature=sig,
                    claim=claim,
                    confidence=conf,
                )
            )
        return calls

    def critique(self, view: EpisodeView, rivals: list[dict[str, Any]]) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for hyp in rivals:
            ids = split_signature(hyp["path_signature"])
            labors = [n for n in ids if n in view.outdoor_hours]
            hours = min((view.outdoor_hours[n] for n in labors), default=9.0)
            if hyp.get("agent_id") != self.agent_id and hours < LOW_OUTDOOR:
                calls.append(
                    self.call(
                        "attack_hypothesis",
                        "low outdoor hours",
                        agent_id=self.agent_id,
                        hypothesis_id=hyp["id"],
                        evidence={
                            "kind": "exposure",
                            "statement": f"labour group outdoor_hours {hours:.1f} is low",
                            "value": hours,
                            "strength": 0.25,
                            "source": "src_synthetic_archetype",
                        },
                    )
                )
            if (
                hyp.get("agent_id") != self.agent_id
                and "heat_stress_illness" in ids
                and "farm_laborers" in ids
                and "fodder" in ids
            ):
                calls.append(
                    self.call(
                        "support_hypothesis",
                        "support fodder-labour-heat",
                        agent_id=self.agent_id,
                        hypothesis_id=hyp["id"],
                        evidence={
                            "kind": "morbidity",
                            "statement": "Fodder shock lengthens outdoor hours; heat-stress follows.",
                            "strength": 0.40,
                            "source": "src_synthetic_episode",
                        },
                    )
                )
            if (
                view.season_year >= 2025
                and hyp.get("agent_id") != self.agent_id
                and "wheat_grain" in ids
            ):
                calls.append(
                    self.call(
                        "attack_hypothesis",
                        "grain path lacks analog under fodder-dominant profiles",
                        agent_id=self.agent_id,
                        hypothesis_id=hyp["id"],
                        evidence={
                            "kind": "precedent",
                            "statement": "no analog where the grain path realized under fodder-dominant profiles",
                            "strength": 0.70,
                            "source": "src_synthetic_episode",
                        },
                    )
                )
        return calls
