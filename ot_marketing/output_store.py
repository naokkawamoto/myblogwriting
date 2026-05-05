from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ot_marketing.paths import outputs_dir


def write_markdown_output(
    *,
    basename: str,
    body: str,
    extra_header: str = "",
    source: str = "otm",
) -> Path:
    """Write UTF-8 markdown under outputs/YYYY-MM-DD/. Returns absolute path."""
    root = outputs_dir()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = root / day
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in basename.strip())[:120]
    out_path = out_dir / f"{safe}.md"
    header_lines = [
        f"<!-- ot-marketing {source} -->",
        f"<!-- generated_at_utc: {datetime.now(timezone.utc).isoformat()} -->",
    ]
    if extra_header:
        header_lines.append(f"<!-- {extra_header} -->")
    content = "\n".join(header_lines) + "\n\n" + body + "\n"
    out_path.write_text(content, encoding="utf-8")
    return out_path
