from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def test_seed_json_is_package_data():
    seed = files("sentinel") / "seed" / "sources.json"
    assert seed.is_file()
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text()
    assert 'sentinel = ["seed/*.json", "seed/*.md"]' in text
    assert "include-package-data" in text
