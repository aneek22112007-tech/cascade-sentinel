from __future__ import annotations

import sys
import types

from sentinel import config
from sentinel.agents import llm


def test_bedrock_client_uses_llm_timeout(monkeypatch):
    captured: dict = {}

    class FakeConfig:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeBody:
        def read(self):
            return b'{"content":[{"type":"text","text":"ok synthetic"}]}'

    class FakeClient:
        def invoke_model(self, **kwargs):
            return {"body": FakeBody()}

    boto3_mod = types.ModuleType("boto3")

    def fake_client(service, region_name=None, config=None):
        captured["service"] = service
        captured["region"] = region_name
        captured["client_config"] = config
        return FakeClient()

    boto3_mod.client = fake_client
    botocore_mod = types.ModuleType("botocore")
    botocore_config = types.ModuleType("botocore.config")
    botocore_config.Config = FakeConfig
    monkeypatch.setitem(sys.modules, "boto3", boto3_mod)
    monkeypatch.setitem(sys.modules, "botocore", botocore_mod)
    monkeypatch.setitem(sys.modules, "botocore.config", botocore_config)
    monkeypatch.setattr(config, "LLM_TIMEOUT_S", 8.0)
    monkeypatch.setattr(config, "AWS_REGION", "us-east-1")

    text = llm._bedrock({"recommendations": []})
    assert "synthetic" in text or text == "ok synthetic"
    assert captured["service"] == "bedrock-runtime"
    assert captured["read_timeout"] == 8.0
    assert captured["connect_timeout"] == 8.0
    assert captured["retries"] == {"max_attempts": 1}
    assert captured["client_config"] is not None
