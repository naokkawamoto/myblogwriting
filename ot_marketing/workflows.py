from __future__ import annotations

from pathlib import Path

from ot_marketing.paths import repo_root


def _read(rel: str) -> str:
    p = repo_root() / rel
    if not p.is_file():
        raise FileNotFoundError(str(p))
    return p.read_text(encoding="utf-8")


def build_note_user_message(task_text: str) -> str:
    dist = _read("prompts/note/dist/note_writer_prompt.md")
    return dist + "\n\n---\n\n" + task_text.strip()


def build_share_user_message(filled_text: str) -> str:
    tmpl = _read("prompts/ops/share_short_from_company.md")
    return (
        tmpl
        + "\n\n---\n\n## 依頼者記入（この実行で渡す内容）\n\n"
        + filled_text.strip()
    )


def dist_note_exists() -> bool:
    return (repo_root() / "prompts/note/dist/note_writer_prompt.md").is_file()
