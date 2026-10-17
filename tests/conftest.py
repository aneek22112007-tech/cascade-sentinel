from __future__ import annotations

import pytest

from sentinel.db import delete_graph
from sentinel.seed.loader import load_tenant
from sentinel.tools.episodes import open_episode, reset_episode_runtime


@pytest.fixture(scope="session")
def seeded_demo():
    delete_graph("demo")
    load_tenant("demo")
    return "demo"


@pytest.fixture
def episode_2024(seeded_demo):
    tenant = seeded_demo
    opened = open_episode(tenant, 2024)
    eid = opened["result"]["id"]
    reset_episode_runtime(tenant, eid)
    return tenant, eid
