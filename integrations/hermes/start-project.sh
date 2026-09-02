#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export WRITING_RUNTIME_ROOT="$ROOT"
cd "$ROOT"
exec hermes -s deterministic-writing-runtime "$@"
