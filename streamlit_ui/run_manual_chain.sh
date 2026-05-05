#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
rm -rf "$ROOT/streamlit_ui/__pycache__" 2>/dev/null || true
if [[ ! -d .venv ]]; then
  echo "先に: python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[web]'" >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$ROOT/.venv/bin/activate"
exec streamlit run "$ROOT/streamlit_ui/manual_home.py"
