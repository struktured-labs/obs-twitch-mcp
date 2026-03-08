#!/usr/bin/env bash
# Snapshot the current OBS scene collection into git.
# Usage: ./scripts/snapshot-scenes.sh [optional commit message]

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

MSG="${1:-Scene snapshot $(date '+%Y-%m-%d %H:%M:%S')}"

git add scenes/
if git diff --cached --quiet -- scenes/; then
    echo "No scene changes to commit."
    exit 0
fi

git commit -m "$MSG"
echo "Committed scene snapshot: $MSG"
