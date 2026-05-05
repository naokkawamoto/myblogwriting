#!/usr/bin/env bash
# Teacher／個人用ブログリポを teacher/myblogwriting にクローンする（冪等）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$ROOT/teacher/myblogwriting"
REPO="${TEACHER_BLOG_REPO_URL:-https://github.com/naokkawamoto/myblogwriting.git}"

mkdir -p "$ROOT/teacher"

if [[ -d "$TARGET/.git" ]]; then
  echo "Already cloned: $TARGET"
  exit 0
fi

if [[ -e "$TARGET" ]]; then
  echo "Error: path exists but is not a git repo: $TARGET" >&2
  exit 1
fi

git clone "$REPO" "$TARGET"
echo "Cloned: $TARGET"
