#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
cd "$ROOT"
./setup.sh
"$HERE/install-skill.sh"
printf 'Bootstrap complete. Use %s/start-project.sh\n' "$HERE"
