from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _project_args(root: Path, slug: str) -> list[str]:
    config_path = root / 'projects' / slug / 'project.json'
    if not config_path.is_file():
        raise SystemExit(f'unknown writing project {slug!r}: {config_path}')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    required = {
        'brief', 'plan_id', 'chapter_key', 'at', 'branch', 'viewpoint',
        'canon_source', 'state_source', 'canon_library', 'state_library', 'workdir', 'out',
    }
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit(f'project config is incomplete ({slug}): missing {", ".join(missing)}')
    return [
        str(config['brief']),
        '--plan-id', str(config['plan_id']),
        '--chapter-key', str(config['chapter_key']),
        '--at', str(config['at']),
        '--branch', str(config['branch']),
        '--viewpoint', str(config['viewpoint']),
        '--canon-source', str(config['canon_source']),
        '--state-source', str(config['state_source']),
        '--canon-library', str(config['canon_library']),
        '--state-library', str(config['state_library']),
        '--workdir', str(config['workdir']),
        '--out', str(config['out']),
    ]


def main(argv: list[str] | None = None) -> int:
    """CWD-independent entry point for Hermes Desktop / GUI operators."""
    root = _root()
    controller = root / 'integrations' / 'hermes' / 'pilot_controller.py'
    runtime = root / 'write_runtime.py'
    if not runtime.is_file() or not controller.is_file():
        print(f'deterministic writing runtime checkout is incomplete: {root}', file=sys.stderr)
        return 2

    raw = list(sys.argv[1:] if argv is None else argv)
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument('--project')
    known, remaining = pre.parse_known_args(raw)
    args = _project_args(root, known.project) + remaining if known.project else raw
    proc = subprocess.run([sys.executable, str(controller), *args], cwd=root)
    return int(proc.returncode)


if __name__ == '__main__':
    raise SystemExit(main())
