"""手動ハンドオフ UI 共通（パス・一覧・読込・保存ヘルパ）。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ot_marketing.paths import repo_root

_EVAL_REPO_REL = "prompts/review/evaluator_scored_generic.md"


def prompts_dir() -> Path:
    return repo_root() / "prompts"


def list_selectable_prompt_files() -> list[str]:
    root = prompts_dir()
    if not root.is_dir():
        return [""]
    found: set[str] = set()
    for p in root.rglob("*.md"):
        if "sections" in p.parts:
            continue
        if p.name in ("README.md", "CHANGELOG.md"):
            continue
        found.add(str(p.relative_to(repo_root())).replace("\\", "/"))
    ordered = sorted(found, key=str.lower)
    return [""] + ordered


def read_repo_prompt(rel: str) -> str:
    if not (rel or "").strip():
        return ""
    path = repo_root() / rel.replace("\\", "/")
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return ""


def read_prompt_body_for_copy(rel: str) -> str:
    """リポジトリの .md を読み、あれば先頭 YAML front matter を除いた本文だけ返す（Claude/ChatGPT へ貼る用）。"""
    raw = read_repo_prompt(rel)
    if not raw:
        return ""
    _, body = parse_front_matter(raw)
    return body


def slug(s: str) -> str:
    s = (s or "session").strip()
    out = "".join(c if c.isalnum() or c in "-_" else "-" for c in s)[:60].strip("-")
    return out or "session"


def render_for_step(template: str, responses_all: list[str], step_index: int) -> str:
    text = template
    for j in range(len(responses_all)):
        n = j + 1
        text = text.replace(f"{{{{STEP{n}}}}}", responses_all[j] or "")
    prev = responses_all[step_index - 1] if step_index > 0 else ""
    text = text.replace("{{前の出力}}", prev)
    return text


def eval_repo_rel() -> str:
    return _EVAL_REPO_REL


def parse_front_matter(md: str) -> tuple[dict[str, object], str]:
    """先頭の YAML front matter があればパースし、(dict, 本文) を返す。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", md, re.DOTALL)
    if not m:
        return {}, md
    body = md[m.end() :]
    raw = m.group(1)
    meta: dict[str, object] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if k in ("workflows", "tags"):
            inner = v.strip("[]\"' ")
            meta[k] = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
        else:
            meta[k] = v
    return meta, body


def save_sns_session(*, title: str, prompt_text: str, response_text: str, evaluation: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    base = repo_root() / "outputs" / "handoff-sessions" / f"{ts}_{slug(title)}_sns"
    base.mkdir(parents=True, exist_ok=True)
    meta = {
        "title": title,
        "workflow": "sns",
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "eval_scores_percent": {},
    }
    (base / "00-meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (base / "sns-prompt-for-claude.md").write_text(prompt_text, encoding="utf-8")
    (base / "sns-response-from-claude.md").write_text(response_text, encoding="utf-8")
    (base / "99-evaluation.md").write_text(evaluation, encoding="utf-8")
    (base / "README.txt").write_text(
        "② SNS シェア文案フロー（評価なし・Claude）。\n",
        encoding="utf-8",
    )
    return base
