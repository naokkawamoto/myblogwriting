#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="$ROOT/dist"
OUT_FILE="$OUT_DIR/note_writer_prompt.md"

mkdir -p "$OUT_DIR"

{
  echo "<!-- AUTO-GENERATED: do not edit. Edit sections/*.md and run assemble.sh -->"
  echo ""
  echo "# note 用・書き手プロンプト（結合版）"
  echo ""
  echo "生成: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo ""
  echo "---"
  echo ""

  shopt -s nullglob
  for f in "$ROOT/sections/"*.md; do
    cat "$f"
    echo ""
    echo "---"
    echo ""
  done
} > "$OUT_FILE"

echo "Wrote: $OUT_FILE"
