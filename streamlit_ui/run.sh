#!/usr/bin/env bash
# リポジトリルートに移動してから Streamlit を起動（cd 先の取り違え防止）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# 古い llm の .pyc で ImportError になることがあるため、起動前にキャッシュを消す
rm -rf "$ROOT/ot_marketing/__pycache__" "$ROOT/streamlit_ui/__pycache__" 2>/dev/null || true
if [[ ! -d .venv ]]; then
  echo "先に: python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[web]'" >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$ROOT/.venv/bin/activate"
exec streamlit run "$ROOT/streamlit_ui/api/streamlit_app.py"
