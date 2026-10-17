"""Weather agent: direct exposure + in-window stage-stress; attacks far-miss windows."""

from __future__ import annotations

from sentinel import config
from sentinel.agents.base import Agent, EpisodeView, ToolCall
from sentinel.formulas import timing_factor
from sentinel.tools.common import split_signature


class WeatherAgent(Agent):
    agent_id = "weather"

    def propose(self, view: EpisodeView) -> list[ToolCall]:
        calls: list[ToolCall] = []
        doy = int(view.forecast.get("doy") or 0)
        for path in view.paths:
            ids = path["node_ids"]
            sig = path["signature"]
            if ids == ["heatwave", "farm_laborers", "heat_stress_illness"]:
                calls.append(
                    self.call(
                        "propose_hypothesis",
                        "direct heat exposure",
                        agent_id=self.agent_id,
                        episode_id=view.episode_id,
                        path_signature=sig,
                        claim="Direct heat exposure: heatwave → farm labourers → heat-stress illness.",
                        confidence=0.90,
                    )
                )
                continue
            stages = [n for n in ids if n in view.windows]
            if not stages:
                if "dairy_households" in ids or "dairy_cattle" in ids:
                    calls.append(
                        self.call(
                            "propose_hypothesis",
                            "dairy exposure branch",
                            agent_id=self.agent_id,
                            episode_id=view.episode_id,
                            path_signature=sig,
                            claim="Heatwave exposes dairy households; livestock heat-stress branch.",
                            confidence=0.55,
                        )
                    )
                continue
            T_vals = [timing_factor(doy, *view.windows[s]) for s in stages]
            if min(T_vals) == config.TIMING_IN_WINDOW:
                calls.append(
                    self.call(
                        "propose_hypothesis",
                        f"stage-stress {stages[0]}",
                        agent_id=self.agent_id,
                        episode_id=view.episode_id,
                        path_signature=sig,
                        claim=f"In-window stage stress on {stages[0]} (doy {doy} inside window).",
                        confidence=0.95 if stages[0] == "fodder_jowar_vegetative" else 0.80,
                    )
                )
        return calls

    def critique(self, view: EpisodeView, rivals: list[dict[str, Any]]) -> list[ToolCall]:
        calls: list[ToolCall] = []
        doy = int(view.forecast.get("doy") or 0)
        for hyp in rivals:
            if hyp.get("agent_id") == self.agent_id:
                continue
            ids = split_signature(hyp["path_signature"])
            for sid in ids:
                if sid not in view.windows:
                    continue
                start, end = view.windows[sid]
                T = timing_factor(doy, start, end)
                if T == config.TIMING_FAR:
                    calls.append(
                        self.call(
                            "attack_hypothesis",
                            f"window miss {sid}",
                            agent_id=self.agent_id,
                            hypothesis_id=hyp["id"],
                            evidence={
                                "kind": "timing",
                                "statement": f"forecast doy {doy} outside stage window [{start},{end}]",
                                "value": doy,
                                "strength": config.WEATHER_WINDOW_MISS_STRENGTH,
                                "source": "src_synthetic_corridor",
                            },
                        )
                    )
                    break
        return calls
