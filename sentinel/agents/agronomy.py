"""Agronomy agent: overconfident on wheat grain; attacks fodder and tiny crops."""

from __future__ import annotations

from sentinel import config
from sentinel.agents.base import Agent, EpisodeView, ToolCall
from sentinel.tools.common import split_signature


class AgronomyAgent(Agent):
    agent_id = "agronomy"

    def propose(self, view: EpisodeView) -> list[ToolCall]:
        calls: list[ToolCall] = []
        ranked = []
        for path in view.paths:
            ids = path["node_ids"]
            crops = [n for n in ids if n in view.crop_ids]
            if not crops:
                continue
            area = view.area_share.get(crops[0], 0.0)
            ranked.append((area, path, crops[0]))
        ranked.sort(key=lambda t: -t[0])
        for area, path, crop in ranked:
            sig = path["signature"]
            if crop == "wheat_grainfill":
                conf = 0.90
                claim = "Wheat grain-price path dominates given area_share."
            elif area < config.AREA_SHARE_ATTACK_BELOW:
                continue
            else:
                # Designed overconfidence: propose wheat, skip fodder (it will be attacked).
                if crop == "fodder_jowar_vegetative":
                    continue
                conf = 0.55
                claim = f"Yield-price cascade through {crop} (area_share={area:.2f})."
            calls.append(
                self.call(
                    "propose_hypothesis",
                    f"yield-price {crop}",
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
            crops = [n for n in ids if n in view.crop_ids]
            crop = crops[0] if crops else None
            area = view.area_share.get(crop, 0.0) if crop else 0.0
            if hyp.get("agent_id") == self.agent_id and crop == "wheat_grainfill":
                calls.append(
                    self.call(
                        "support_hypothesis",
                        "support own wheat claim",
                        agent_id=self.agent_id,
                        hypothesis_id=hyp["id"],
                        evidence={
                            "kind": "area_share",
                            "statement": f"wheat area_share {area:.2f} is the largest planted stage",
                            "value": area,
                            "strength": 0.40,
                            "source": "src_synthetic_archetype",
                        },
                    )
                )
                continue
            if hyp.get("agent_id") == self.agent_id:
                continue
            if crop == "fodder_jowar_vegetative":
                calls.append(
                    self.call(
                        "attack_hypothesis",
                        "attack fodder path",
                        agent_id=self.agent_id,
                        hypothesis_id=hyp["id"],
                        evidence={
                            "kind": "overconfidence",
                            "statement": "Fodder path is secondary; wheat grain-price path dominates.",
                            "value": area,
                            "strength": 0.50,
                            "source": "src_synthetic_archetype",
                        },
                    )
                )
            elif crop and area < config.AREA_SHARE_ATTACK_BELOW:
                calls.append(
                    self.call(
                        "attack_hypothesis",
                        f"tiny crop {crop}",
                        agent_id=self.agent_id,
                        hypothesis_id=hyp["id"],
                        evidence={
                            "kind": "area_share",
                            "statement": f"area_share {area:.2f} < 0.15 for {crop}",
                            "value": area,
                            "strength": 0.60,
                            "source": "src_synthetic_archetype",
                        },
                    )
                )
        return calls
