#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DEST="$HERMES_HOME/skills/writing/deterministic-writing-runtime"
mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
cp -R "$HERE/skill/deterministic-writing-runtime" "$DEST"
printf 'Installed Hermes skill: %s\n' "$DEST"
printf 'Launch this project with: %s/start-project.sh\n' "$HERE"
