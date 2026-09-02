#!/usr/bin/env bash
set -euo pipefail
REPOSITORY="${WRITING_HARNESS_REPO:-https://github.com/Laeveteinn/llm-story-companion.git}"
REF="${WRITING_HARNESS_REF:-main}"
DESTINATION="${WRITING_HARNESS_HOME:-$HOME/WritingHarness-Deterministic}"
EXPECTED_COMMIT="${WRITING_HARNESS_EXPECTED_COMMIT:-}"
SKIP_SETUP="${WRITING_HARNESS_SKIP_SETUP:-0}"

command -v git >/dev/null || { echo 'Required command not found: git' >&2; exit 2; }
mkdir -p "$(dirname "$DESTINATION")"
if [[ -d "$DESTINATION/.git" ]]; then
  origin="$(git -C "$DESTINATION" remote get-url origin)"
  [[ "$origin" == "$REPOSITORY" ]] || { echo "Unexpected origin: $origin" >&2; exit 2; }
elif [[ -e "$DESTINATION" ]]; then
  echo "Destination exists but is not a Git repository: $DESTINATION" >&2; exit 2
else
  git clone --no-checkout "$REPOSITORY" "$DESTINATION"
fi

git -C "$DESTINATION" fetch --force --depth 1 origin "$REF"
git -C "$DESTINATION" checkout --detach --force FETCH_HEAD
commit="$(git -C "$DESTINATION" rev-parse HEAD | tr '[:upper:]' '[:lower:]')"
if [[ -n "$EXPECTED_COMMIT" && "$commit" != "${EXPECTED_COMMIT,,}" ]]; then
  echo "Resolved commit $commit does not match expected ${EXPECTED_COMMIT,,}" >&2; exit 2
fi
for rel in write_runtime.py pyproject.toml integrations/hermes/bootstrap.sh .hermes.md; do
  [[ -f "$DESTINATION/$rel" ]] || { echo "Incomplete runtime checkout; missing $rel" >&2; exit 2; }
done
mkdir -p "$DESTINATION/runtime_state"
python - "$DESTINATION/runtime_state/install-source.json" "$REPOSITORY" "$REF" "$commit" "$DESTINATION" <<'PY'
import json, sys
from datetime import datetime, timezone
path, repo, ref, commit, dest = sys.argv[1:]
with open(path, 'w', encoding='utf-8') as f:
    json.dump({'repository':repo,'requested_ref':ref,'resolved_commit':commit,
               'installed_at_utc':datetime.now(timezone.utc).isoformat(),'destination':dest}, f, indent=2)
    f.write('\n')
PY
if [[ "$SKIP_SETUP" != "1" ]]; then
  "$DESTINATION/integrations/hermes/bootstrap.sh"
fi
printf 'Installed deterministic writing runtime at %s\nResolved Git commit: %s\n' "$DESTINATION" "$commit"
