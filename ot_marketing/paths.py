from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """Workspace root (contains prompts/note/assemble.sh)."""
    here = Path(__file__).resolve().parent
    root = here.parent
    marker = root / "prompts" / "note" / "assemble.sh"
    if marker.is_file():
        return root
    raise RuntimeError(
        f"Could not resolve repo root from {here}. "
        "Run from the onetech-marketing-workspace clone."
    )


def outputs_dir() -> Path:
    d = repo_root() / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d
