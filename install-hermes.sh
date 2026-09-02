#!/usr/bin/env bash
set -euo pipefail
REPO_SLUG="${WRITING_HARNESS_REPOSITORY:-Laeveteinn/llm-story-companion}"
REF="${WRITING_HARNESS_REF:-main}"
DEST="${WRITING_HARNESS_HOME:-$HOME/WritingHarness-Deterministic}"
EXPECTED_COMMIT="${WRITING_HARNESS_EXPECTED_COMMIT:-}"
EXPECTED_ARCHIVE="${WRITING_HARNESS_EXPECTED_ARCHIVE_SHA256:-}"
SKIP_HERMES="${WRITING_HARNESS_SKIP_HERMES_INSTALL:-0}"
SKIP_SETUP="${WRITING_HARNESS_SKIP_SETUP:-0}"

command -v curl >/dev/null 2>&1 || { echo 'curl is required' >&2; exit 2; }
if ! command -v hermes >/dev/null 2>&1 && [[ "$SKIP_HERMES" != "1" ]]; then
  printf 'Hermes CLI not found; installing with the official Nous Research installer...\n'
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
  export PATH="$HOME/.local/bin:${HERMES_HOME:-$HOME/.hermes}/hermes-agent/venv/bin:$PATH"
fi
PYTHON="$(command -v python3 || command -v python || true)"
[[ -n "$PYTHON" ]] || { echo 'python3/python is required to decode the distribution manifest' >&2; exit 2; }
[[ ! -e "$DEST" ]] || { echo "Destination exists: $DEST" >&2; exit 2; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

COMMIT="$($PYTHON - "$REPO_SLUG" "$REF" <<'PY'
import json,sys,urllib.request,urllib.parse
repo,ref=sys.argv[1:]
req=urllib.request.Request(f'https://api.github.com/repos/{repo}/commits/{urllib.parse.quote(ref, safe="")}',headers={'User-Agent':'deterministic-writing-runtime-installer'})
with urllib.request.urlopen(req) as r: data=json.load(r)
print(data['sha'])
PY
)"
COMMIT="${COMMIT,,}"
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid GitHub commit: $COMMIT" >&2; exit 2; }
[[ -z "$EXPECTED_COMMIT" || "$COMMIT" == "${EXPECTED_COMMIT,,}" ]] || { echo "commit mismatch" >&2; exit 2; }
RAW="https://raw.githubusercontent.com/$REPO_SLUG/$COMMIT"
curl -fsSL "$RAW/dist/current.json" -o "$TMP/current.json"
mapfile -t INFO < <($PYTHON - "$TMP/current.json" "$RAW" "$TMP" <<'PY'
import base64,hashlib,json,pathlib,sys,urllib.request
m=json.load(open(sys.argv[1],encoding='utf-8')); raw,tmp=sys.argv[2:]
if m.get('encoding') != 'base64-parts': raise SystemExit('unsupported distribution encoding')
if m.get('format') != 'tar.xz': raise SystemExit('unsupported distribution format')
encoded=[]
for part in m['parts']:
    with urllib.request.urlopen(f"{raw}/{m['part_dir']}/{part}") as r: encoded.append(r.read().decode().strip())
data=base64.b64decode(''.join(encoded),validate=True); actual=hashlib.sha256(data).hexdigest()
path=pathlib.Path(tmp)/m['archive']; path.write_bytes(data)
print(path); print(actual); print(m['version'])
PY
)
ARCHIVE="${INFO[0]}"; ACTUAL="${INFO[1]}"; VERSION="${INFO[2]}"
[[ -z "$EXPECTED_ARCHIVE" || "$ACTUAL" == "${EXPECTED_ARCHIVE,,}" ]] || { echo 'archive hash mismatch against expected' >&2; exit 2; }
$PYTHON - "$ARCHIVE" "$TMP/unpacked" <<'PY'
import pathlib,sys,tarfile
archive,out=sys.argv[1:]
root=pathlib.Path(out).resolve(); root.mkdir()
with tarfile.open(archive,'r:xz') as tf:
    members=tf.getmembers()
    for member in members:
        if member.issym() or member.islnk(): raise SystemExit(f'refusing archive link: {member.name}')
        target=(root/member.name).resolve()
        if target != root and root not in target.parents: raise SystemExit(f'unsafe archive path: {member.name}')
    tf.extractall(root)
PY
EXPANDED="$(find "$TMP/unpacked" -mindepth 1 -maxdepth 1 -type d | head -1)"
for rel in write_runtime.py pyproject.toml .hermes.md SNAPSHOT_MANIFEST.json writing_runtime/temporal.py writing_runtime/semantic.py integrations/hermes/pilot_controller.py tests/test_temporal.py; do
  [[ -f "$EXPANDED/$rel" ]] || { echo "Incomplete archive; missing $rel" >&2; exit 2; }
done
mkdir -p "$(dirname "$DEST")"; mv "$EXPANDED" "$DEST"
mkdir -p "$DEST/runtime_state"
printf '{"repository":"https://github.com/%s","requested_ref":"%s","resolved_commit":"%s","distribution_version":"%s","archive_sha256":"%s"}\n' "$REPO_SLUG" "$REF" "$COMMIT" "$VERSION" "$ACTUAL" > "$DEST/runtime_state/install-source.json"
[[ "$SKIP_SETUP" == "1" ]] || "$DEST/integrations/hermes/bootstrap.sh"
printf 'Installed deterministic writing runtime %s at %s\nPinned GitHub commit: %s\nArchive SHA-256: %s\n' "$VERSION" "$DEST" "$COMMIT" "$ACTUAL"
