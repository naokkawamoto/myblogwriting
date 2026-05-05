#!/usr/bin/env python3
"""YAML front matter 付きの .md を走査し prompts/WORKFLOW_PROMPTS.generated.md を出力する（ドラフト）。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "prompts"
OUT = PROMPTS / "WORKFLOW_PROMPTS.generated.md"


def _scan(rel_path: Path, raw: str) -> tuple[list[str], list[str]]:
    work = tags = []
    m = re.match(r"^---\s*\n(.*?)\n---", raw, re.DOTALL)
    if not m:
        return [], []
    block = m.group(1)
    for line in block.splitlines():
        if line.startswith("workflows:"):
            inner = line.split(":", 1)[1].strip().strip("[]\"' ")
            work = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
        if line.startswith("tags:"):
            inner = line.split(":", 1)[1].strip().strip("[]\"' ")
            tags = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
    return work, tags


def main() -> int:
    rows_note: list[str] = []
    rows_sns: list[str] = []
    rows_other: list[str] = []

    for p in sorted(PROMPTS.rglob("*.md")):
        if "sections" in p.parts or p.name in (
            "README.md",
            "CHANGELOG.md",
            "WORKFLOW_PROMPTS.md",
            "WORKFLOW_PROMPTS.generated.md",
        ):
            continue
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        raw = p.read_text(encoding="utf-8", errors="replace")
        wf, tg = _scan(p, raw)
        wfs = ",".join(wf) if wf else "(front matter なし→手で振り分け)"
        tgs = ",".join(tg) if tg else ""
        row = f"| `{rel}` | {wfs} | {tgs} |\n"
        key = "".join(wf).lower()
        if any(w.lower() == "note" for w in wf):
            rows_note.append(row)
        elif any(w.lower() in ("sns", "social") for w in wf):
            rows_sns.append(row)
        else:
            rows_other.append(row)

    header = (
        "# WORKFLOW_PROMPTS（自動生成・ドラフト）\n\n"
        "`scripts/gen_workflow_prompts.py` がスキャンしました。**YAML は任意**。 "
        "`workflows:` に `note` / `sns` を書くと下に振り分けます。\n\n"
        "## ① note っぽい（workflows に note）\n\n"
        "| ファイル | workflows | tags |\n|----------|-----------|------|\n"
    )
    mid = (
        "\n## ② SNS っぽい（workflows に sns / social）\n\n"
        "| ファイル | workflows | tags |\n|----------|-----------|------|\n"
    )
    tail = (
        "\n## その他（front matter なし or 未分類）\n\n"
        "| ファイル | workflows | tags |\n|----------|-----------|------|\n"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        header + "".join(rows_note or ["| （該当なし） |  |  |\n"])
        + mid
        + "".join(rows_sns or ["| （該当なし） |  |  |\n"])
        + tail
        + "".join(rows_other or ["| （該当なし） |  |  |\n"]),
        encoding="utf-8",
    )
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
