from __future__ import annotations

import os
from typing import Literal

Provider = Literal["openai", "anthropic"]


def complete(
    *,
    provider: Provider,
    model: str,
    system: str,
    user: str,
) -> str:
    """Return assistant text (plain string)."""
    p = provider.lower()
    if p == "openai":
        return _openai_complete(model=model, system=system, user=user)
    if p == "anthropic":
        return _anthropic_complete(model=model, system=system, user=user)
    raise ValueError(f"Unknown provider: {provider!r}. Use openai or anthropic.")


def _openai_complete(*, model: str, system: str, user: str) -> str:
    from openai import OpenAI

    client = OpenAI()
    messages: list[dict[str, str]] = []
    if system.strip():
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    choice = resp.choices[0].message
    text = (choice.content or "").strip()
    if not text:
        raise RuntimeError("OpenAI returned empty content.")
    return text


def _anthropic_complete(*, model: str, system: str, user: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    kwargs: dict = {
        "model": model,
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": user}],
    }
    if system.strip():
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    parts: list[str] = []
    for block in resp.content:
        if block.type == "text":
            parts.append(block.text)
    text = "".join(parts).strip()
    if not text:
        raise RuntimeError("Anthropic returned empty content.")
    return text


def default_model(provider: Provider) -> str:
    if provider == "openai":
        return os.environ.get("OTM_OPENAI_MODEL", "gpt-4o")
    return os.environ.get("OTM_ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
