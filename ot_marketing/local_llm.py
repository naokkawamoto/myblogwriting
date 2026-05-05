"""OpenAI 互換のローカル HTTP API（Ollama / LM Studio 等）。`llm.py` と分離し import キャッシュ問題を避ける。"""

from __future__ import annotations


def normalize_openai_compat_base_url(base_url: str) -> str:
    """Ensure URL ends with /v1 for OpenAI-compatible servers (Ollama, LM Studio, etc.)."""
    u = base_url.strip().rstrip("/")
    if not u:
        raise ValueError("base_url is empty")
    if u.endswith("/v1"):
        return u
    return f"{u}/v1"


def complete_openai_compatible_local(
    *,
    base_url: str,
    model: str,
    system: str,
    user: str,
    api_key: str = "ollama",
) -> str:
    """Call a local OpenAI-compatible HTTP API (Ollama, LM Studio, vLLM, …). No cloud API key required."""
    from openai import OpenAI

    root = normalize_openai_compat_base_url(base_url)
    client = OpenAI(base_url=root, api_key=api_key or "ollama")
    messages: list[dict[str, str]] = []
    if system.strip():
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    resp = client.chat.completions.create(
        model=model.strip(),
        messages=messages,
    )
    choice = resp.choices[0].message
    text = (choice.content or "").strip()
    if not text:
        raise RuntimeError("Local server returned empty content.")
    return text
