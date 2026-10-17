from sentinel.formulas import (
    cosine,
    credibility,
    effective_confidence,
    episode_similarity,
    exposure_factor,
    intensity_factor,
    is_hit,
    jaccard,
    path_score,
    path_signature,
    precedent_weight,
    timing_factor,
)

FODDER = [
    "heatwave",
    "fodder_jowar_vegetative",
    "fodder",
    "mandi_fodder",
    "farm_laborers",
    "heat_stress_illness",
]
WHEAT = [
    "heatwave",
    "wheat_grainfill",
    "wheat_grain",
    "mandi_wheat",
    "farm_laborers",
    "heat_stress_illness",
]
DIRECT = ["heatwave", "farm_laborers", "heat_stress_illness"]


def test_intensity_caps_at_one():
    assert intensity_factor(6) == 1.0
    assert intensity_factor(3) == 0.5
    assert intensity_factor(12) == 1.0
    assert intensity_factor(0) == 0.0


def test_timing_in_near_far():
    assert timing_factor(136, 121, 175) == 1.0
    assert timing_factor(136, 70, 126) == 0.6
    assert timing_factor(136, 70, 125) == 0.2
    assert timing_factor(100, 70, 126) == 1.0
    assert timing_factor(80, None, None) == 1.0


def test_exposure():
    assert exposure_factor(0.30, 0.80) == 0.24
    assert exposure_factor(None, 0.80) == 0.80
    assert exposure_factor(0.45, None) == 0.45


def test_path_score_product():
    s = path_score(1.0, 1.0, 0.24, [(0.9, 0.9), (0.9, 0.9)])
    assert abs(s - 0.24 * 0.81 * 0.81) < 1e-12


def test_credibility_beta_smoothing():
    assert credibility(3, 1) == 4 / 6
    assert credibility(1, 1) == 0.5
    assert credibility(2, 1) == 0.6
    assert credibility(0, 0) == 0.5


def test_effective_confidence():
    assert abs(effective_confidence(0.9, 0.5) - 0.45) < 1e-12


def test_precedent_weight_table():
    assert abs(precedent_weight(3, 4, 2023, 2024) - 4 / 6) < 1e-12
    assert abs(precedent_weight(2, 3, 2023, 2024) - 0.6) < 1e-12
    assert abs(precedent_weight(3, 3, 2023, 2024) - 0.8) < 1e-12
    assert abs(precedent_weight(0, 2, 2022, 2024) - 0.25 * 0.9) < 1e-12
    assert abs(precedent_weight(0, 1, 2021, 2024) - (1 / 3) * 0.81) < 1e-12
    # after 2024 success on cool shelters, 2025 P = 0.5
    assert abs(precedent_weight(1, 2, 2024, 2025) - 0.5) < 1e-12


def test_jaccard_and_hit():
    assert jaccard(FODDER, FODDER) == 1.0
    assert is_hit(FODDER, FODDER)
    assert not is_hit(WHEAT, FODDER)
    assert abs(jaccard(DIRECT, FODDER) - 0.5) < 1e-12
    assert not is_hit(DIRECT, FODDER)


def test_cosine_and_similarity():
    v = [0.45, 0.82, 0.85, 0.78, 0.70]
    assert abs(cosine(v, v) - 1.0) < 1e-12
    sim = episode_similarity(FODDER, FODDER, True, v, v)
    assert abs(sim - 1.0) < 1e-12
    sim_w = episode_similarity(WHEAT, FODDER, False, v, v)
    assert sim_w < 0.5


def test_path_signature():
    assert path_signature(["a", "b"]) == "a>b"
