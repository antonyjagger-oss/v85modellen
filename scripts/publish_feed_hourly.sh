#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="/home/dodge/workspace/v85modellen/logs"
LOCK_FILE="/tmp/v85modellen_publish_feed.lock"
PYTHON_BIN="/home/dodge/venv312/bin/python"
PUBLISH_SCRIPT="/home/dodge/workspace/v85modellen/scripts/publish_feed.py"
LOG_FILE="$LOG_DIR/feed_publish.log"

mkdir -p "$LOG_DIR"

exec 9>"$LOCK_FILE"
/usr/bin/flock -n 9 || exit 0

echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] publish start" >> "$LOG_FILE"
if "$PYTHON_BIN" "$PUBLISH_SCRIPT" >> "$LOG_FILE" 2>&1; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] publish ok" >> "$LOG_FILE"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] publish failed" >> "$LOG_FILE"
  exit 1
fi
