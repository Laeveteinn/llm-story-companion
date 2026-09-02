#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
export WRITING_RUNTIME_ROOT="$ROOT"
cd "$ROOT"
# Keep the installed Hermes skill synchronized with this checkout on every launch.
"$HERE/install-skill.sh"
exec hermes -s deterministic-writing-runtime "$@"
