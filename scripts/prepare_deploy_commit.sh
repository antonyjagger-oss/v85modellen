#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/dodge/workspace/v85modellen"
BUILD_SCRIPT="$REPO_ROOT/scripts/build_feed.py"
FEED_PATH="$REPO_ROOT/public/data/feed.json"
PYTHON_BIN="/home/dodge/venv312/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  echo "python3 not found" >&2
  exit 1
fi

cd "$REPO_ROOT"

echo "[prepare] rebuilding feed snapshot"
"$PYTHON_BIN" "$BUILD_SCRIPT"

echo "[prepare] staging fresh feed snapshot"
git add "$FEED_PATH"

if [[ "$#" -gt 0 ]]; then
  echo "[prepare] staging requested paths"
  git add "$@"
fi

echo
echo "[prepare] staged changes:"
git diff --cached --name-only
echo
echo "[prepare] next:"
echo "  git commit -m \"<message>\""
echo "  git push origin main"
