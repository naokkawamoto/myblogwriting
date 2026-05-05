from __future__ import annotations

import os
from pathlib import Path

import tomli
from dotenv import load_dotenv

from ot_marketing.paths import repo_root

_STREAMLIT_SECRETS = Path(".streamlit") / "secrets.toml"
_API_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")


def secrets_toml_path() -> Path:
    return repo_root() / _STREAMLIT_SECRETS


def bootstrap_env() -> None:
    """Load `.env` then `.streamlit/secrets.toml` (secrets override env)."""
    root = repo_root()
    load_dotenv(root / ".env")
    load_dotenv()
    _apply_secrets_toml(secrets_toml_path())


def _apply_secrets_toml(path: Path) -> None:
    if not path.is_file():
        return
    try:
        data = tomli.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    for k in _API_KEYS:
        v = data.get(k)
        if v is not None and str(v).strip():
            os.environ[k] = str(v).strip()


def _toml_double_quoted(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_api_secrets_toml(
    *,
    openai_key: str | None = None,
    anthropic_key: str | None = None,
) -> Path:
    """Merge into `.streamlit/secrets.toml` (only non-empty args update). Returns path."""
    path = secrets_toml_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, str] = {}
    if path.is_file():
        try:
            raw = tomli.loads(path.read_text(encoding="utf-8"))
            for k in _API_KEYS:
                v = raw.get(k)
                if isinstance(v, str) and v.strip():
                    data[k] = v.strip()
        except Exception:
            data = {}
    if openai_key is not None and openai_key.strip():
        data["OPENAI_API_KEY"] = openai_key.strip()
    if anthropic_key is not None and anthropic_key.strip():
        data["ANTHROPIC_API_KEY"] = anthropic_key.strip()

    lines = [
        "# ot-marketing: ローカルのみ。Git にコミットしないこと。",
        "# Streamlit / CLI 両方が読み込みます。",
        "",
    ]
    for k in _API_KEYS:
        if k in data:
            lines.append(f"{k} = {_toml_double_quoted(data[k])}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    _apply_secrets_toml(path)
    return path
