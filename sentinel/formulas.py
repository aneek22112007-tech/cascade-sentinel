"""Deterministic math from section 6. One implementation, used by tools and seed."""

from __future__ import annotations

import math

from sentinel import config


def intensity_factor(anomaly_c: float) -> float:
    return min(1.0, float(anomaly_c) / config.INTENSITY_ANOMALY_SCALE)


def timing_factor(doy: int, window_start_doy: int | None, window_end_doy: int | None) -> float:
    if window_start_doy is None or window_end_doy is None:
        return 1.0
    doy = int(doy)
    start, end = int(window_start_doy), int(window_end_doy)
    if start <= doy <= end:
        return config.TIMING_IN_WINDOW
    dist = min(abs(doy - start), abs(doy - end))
    if dist <= config.TIMING_NEAR_DAYS:
        return config.TIMING_NEAR
    return config.TIMING_FAR


def exposure_factor(area_share: float | None, size_estimate: float | None) -> float:
    area = 1.0 if area_share is None else float(area_share)
    size = 1.0 if size_estimate is None else float(size_estimate)
    return area * size


def path_score(
    intensity: float,
    timing: float,
    exposure: float,
    edge_weight_conf: list[tuple[float, float]],
) -> float:
    prod = 1.0
    for weight, confidence in edge_weight_conf:
        prod *= float(weight) * float(confidence)
    return float(intensity) * float(timing) * float(exposure) * prod


def credibility(hits: int, misses: int) -> float:
    return (int(hits) + 1) / (int(hits) + int(misses) + 2)


def effective_confidence(hypothesis_confidence: float, proposer_credibility: float) -> float:
    return float(hypothesis_confidence) * float(proposer_credibility)


def precedent_weight(
    successes: int,
    trials: int,
    last_trial_year: int,
    current_year: int,
) -> float:
    base = (int(successes) + 1) / (int(trials) + 2)
    decay_years = max(0, int(current_year) - int(last_trial_year) - 1)
    return base * (config.PRECEDENT_DECAY_BASE ** decay_years)


def jaccard(a: list | set, b: list | set) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def cosine(u: list[float], v: list[float]) -> float:
    if not u or not v or len(u) != len(v):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(u, v))
    nu = math.sqrt(sum(float(a) * float(a) for a in u))
    nv = math.sqrt(sum(float(b) * float(b) for b in v))
    if nu == 0.0 or nv == 0.0:
        return 0.0
    return dot / (nu * nv)


def episode_similarity(
    path_nodes: list[str],
    analog_nodes: list[str],
    same_crop_stage: bool,
    profile_a: list[float],
    profile_b: list[float],
) -> float:
    return (
        0.5 * jaccard(path_nodes, analog_nodes)
        + 0.3 * (1.0 if same_crop_stage else 0.0)
        + 0.2 * cosine(profile_a, profile_b)
    )


def path_signature(node_ids: list[str]) -> str:
    return ">".join(node_ids)


def is_hit(hyp_nodes: list[str], realized_nodes: list[str]) -> bool:
    return jaccard(hyp_nodes, realized_nodes) >= config.HIT_JACCARD_MIN
