"""Optional LLM prose. Decisions never read this output."""

from __future__ import annotations

import json
from typing import Any

from sentinel import config


def templated_rationale(payload: dict[str, Any]) -> str:
    recs = payload.get("recommendations") or []
    acts = [r for r in recs if r.get("kind") == "act"]
    dead = [r for r in recs if r.get("kind") == "defeated_precedent"]
    weak = [r for r in recs if r.get("kind") == "weak_analog"]
    esc = [r for r in recs if r.get("kind") == "escalate"]
    bits = []
    if acts:
        names = ", ".join(sorted({r.get("intervention_name") or r.get("intervention_id") for r in acts}))
        bits.append(f"Precedent supports acting on: {names}.")
    if dead:
        names = ", ".join(sorted({r.get("intervention_name") or r.get("intervention_id") for r in dead}))
        bits.append(f"Struck through (weak precedent): {names}.")
    if weak:
        bits.append("Some paths have a weak analog (similar episodes exist) and are not acted on.")
    if esc:
        bits.append("At least one accepted or contested path is UNPRECEDENTED and is escalated to the district officer.")
    if not bits:
        bits.append("No qualifying act recommendation; the agent refuses to invent an intervention.")
    bits.append("All figures are synthetic archetype data.")
    return " ".join(bits)


def write_rationale(payload: dict[str, Any]) -> str:
    provider = (config.LLM_PROVIDER or "none").lower()
    if provider in ("", "none"):
        return templated_rationale(payload)
    try:
        if provider == "bedrock":
            return _bedrock(payload)
        if provider in ("openai_compatible", "openai", "xai"):
            return _openai_compatible(payload)
    except Exception:
        return templated_rationale(payload)
    return templated_rationale(payload)


def _user_prompt(payload: dict[str, Any]) -> str:
    clipped = {
        "hypotheses": [
            {k: h.get(k) for k in ("agent_id", "status", "reason", "path_signature")}
            for h in (payload.get("hypotheses") or [])[:12]
        ],
        "recommendations": [
            {k: r.get(k) for k in ("kind", "intervention_name", "message", "precedent_weight")}
            for r in (payload.get("recommendations") or [])[:12]
        ],
    }
    return (
        "Write one short paragraph (max 80 words) explaining these graph-adjudicated "
        "recommendations to a district officer. Do not add facts. Do not change decisions. "
        "Mention that the data are synthetic archetypes.\n\n"
        + json.dumps(clipped, sort_keys=True)
    )


def _bedrock(payload: dict[str, Any]) -> str:
    import boto3  # optional extra
    from botocore.config import Config as BotoConfig

    client = boto3.client(
        "bedrock-runtime",
        region_name=config.AWS_REGION,
        config=BotoConfig(
            read_timeout=config.LLM_TIMEOUT_S,
            connect_timeout=config.LLM_TIMEOUT_S,
            retries={"max_attempts": 1},
        ),
    )
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 200,
        "messages": [{"role": "user", "content": _user_prompt(payload)}],
    }
    resp = client.invoke_model(
        modelId=config.BEDROCK_MODEL_ID,
        body=json.dumps(body),
    )
    data = json.loads(resp["body"].read())
    text = "".join(p.get("text", "") for p in data.get("content", []) if p.get("type") == "text")
    return text.strip() or templated_rationale(payload)


def _openai_compatible(payload: dict[str, Any]) -> str:
    import httpx

    headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
    url = config.OPENAI_BASE_URL.rstrip("/") + "/chat/completions"
    with httpx.Client(timeout=config.LLM_TIMEOUT_S) as client:
        r = client.post(
            url,
            headers=headers,
            json={
                "model": config.OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": "You write a single rationale paragraph. No new facts."},
                    {"role": "user", "content": _user_prompt(payload)},
                ],
                "temperature": 0,
            },
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
    return (text or "").strip() or templated_rationale(payload)
