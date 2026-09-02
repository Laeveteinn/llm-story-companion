#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
CORE_ONLY="${CORE_ONLY:-0}"
SKIP_VALE="${SKIP_VALE:-0}"
REFRESH_VALE="${REFRESH_VALE:-0}"

python -m pip install -U pip
python -m pip install -e .
if [[ "$CORE_ONLY" != "1" ]]; then
  python -m pip install -e '.[nlp]'
  python -m spacy download en_core_web_sm || echo "spaCy model install failed; core remains usable" >&2
fi

if [[ "$CORE_ONLY" != "1" ]]; then
  if ! command -v node >/dev/null || ! command -v npm >/dev/null; then
    echo "Node/npm are required for the full analyzer stack." >&2; exit 2
  fi
  node -e 'const [M,m]=process.versions.node.split(".").map(Number); if (M<22 || (M===22 && m<18)) { console.error(`Node >=22.18.0 required; installed ${process.versions.node}`); process.exit(2) }'
  if [[ -f package-lock.json ]]; then
    npm ci --ignore-scripts=false
  else
    echo "WARNING: no package-lock.json yet; first full install will resolve dependencies and create one. Preserve it for reproducible future installs." >&2
    npm install --ignore-scripts=false
  fi
else
  echo "Skipping Node analyzers (CORE_ONLY=1)."
fi

if [[ "$SKIP_VALE" != "1" && "$CORE_ONLY" != "1" ]]; then
  if ! command -v vale >/dev/null 2>&1 && command -v brew >/dev/null 2>&1; then
    brew install vale || true
  fi
  if command -v vale >/dev/null 2>&1; then
    if [[ "$REFRESH_VALE" == "1" || ! -d .vale/styles ]]; then
      vale sync || echo "Vale sync failed; continue without Vale until styles are synced" >&2
    else
      echo "Using existing frozen .vale/styles (REFRESH_VALE=1 updates intentionally)."
    fi
  else
    echo "Vale not installed. Install the CLI manually, then run: vale sync" >&2
  fi
fi

python write_runtime.py canon-build canon_source --out canon/canon.sqlite3
python write_runtime.py canon-spell-dict --library canon/canon.sqlite3 --out config/canon-terms.txt
python write_runtime.py state-build state_source --library canon/canon.sqlite3 --out state/story_state.sqlite3
python write_runtime.py plan-check plans/example.json --library canon/canon.sqlite3 --state-library state/story_state.sqlite3
python write_runtime.py tool-lock --out config/toolchain.lock.json
python write_runtime.py doctor
python write_runtime.py tool-expected || echo "Tool version drift detected; exact runtime is recorded in config/toolchain.lock.json" >&2
