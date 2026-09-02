#!/usr/bin/env bash
set -euo pipefail
REPO_SLUG="${WRITING_HARNESS_REPOSITORY:-Laeveteinn/llm-story-companion}"
REF="${WRITING_HARNESS_REF:-main}"
DEST="${WRITING_HARNESS_HOME:-$HOME/WritingHarness-Deterministic}"
EXPECTED_COMMIT="${WRITING_HARNESS_EXPECTED_COMMIT:-}"
SKIP_HERMES="${WRITING_HARNESS_SKIP_HERMES_INSTALL:-0}"
SKIP_SETUP="${WRITING_HARNESS_SKIP_SETUP:-0}"

command -v curl >/dev/null 2>&1 || { echo 'curl is required' >&2; exit 2; }
if ! command -v hermes >/dev/null 2>&1 && [[ "$SKIP_HERMES" != "1" ]]; then
  printf 'Hermes CLI not found; installing with the official Nous Research installer...\n'
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
  export PATH="$HOME/.local/bin:${HERMES_HOME:-$HOME/.hermes}/hermes-agent/venv/bin:$PATH"
fi
command -v git >/dev/null 2>&1 || { echo 'git is required for the deterministic public-source install' >&2; exit 2; }

COMMIT="$(python3 - "$REPO_SLUG" "$REF" <<'PY'
import json,sys,urllib.parse,urllib.request
repo,ref=sys.argv[1:]
req=urllib.request.Request(
    f'https://api.github.com/repos/{repo}/commits/{urllib.parse.quote(ref, safe="")}',
    headers={'User-Agent':'deterministic-writing-runtime-installer'})
with urllib.request.urlopen(req) as r: data=json.load(r)
print(data['sha'])
PY
)"
COMMIT="${COMMIT,,}"
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid GitHub commit: $COMMIT" >&2; exit 2; }
[[ -z "$EXPECTED_COMMIT" || "$COMMIT" == "${EXPECTED_COMMIT,,}" ]] || { echo "commit mismatch" >&2; exit 2; }

TMP="$(mktemp)"; trap 'rm -f "$TMP"' EXIT
RAW="https://raw.githubusercontent.com/$REPO_SLUG/$COMMIT/integrations/hermes/install-from-github.sh"
curl -fsSL "$RAW" -o "$TMP"
chmod +x "$TMP"
WRITING_HARNESS_REPO="https://github.com/$REPO_SLUG.git" \
WRITING_HARNESS_REF="$COMMIT" \
WRITING_HARNESS_HOME="$DEST" \
WRITING_HARNESS_EXPECTED_COMMIT="$COMMIT" \
WRITING_HARNESS_SKIP_SETUP="$SKIP_SETUP" \
  "$TMP"
