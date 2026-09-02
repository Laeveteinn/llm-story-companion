from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _project_args(root: Path, slug: str, *, allow_unpinned: bool = False) -> list[str]:
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
    provider = config.get('provider')
    model = config.get('model')
    if bool(provider) != bool(model):
        raise SystemExit(f'project model pin is incomplete ({slug}): provider and model must be set together')
    if not provider and not allow_unpinned:
        raise SystemExit(
            f'writing project {slug!r} has no pinned Hermes provider/model; refusing to inherit mutable '
            f'Desktop/default model state. Pin it with: writing-project-model {slug} --provider <provider> --model <model>'
        )
    result = [
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
    if provider and model:
        result += ['--provider', str(provider), '--model', str(model)]
    return result


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
    pre.add_argument('--provider')
    pre.add_argument('--model')
    known, remaining = pre.parse_known_args(raw)

    if known.project:
        explicit_pin = bool(known.provider or known.model)
        if bool(known.provider) != bool(known.model):
            raise SystemExit('explicit model override requires both --provider and --model')
        args = _project_args(root, known.project, allow_unpinned=explicit_pin) + remaining
        if explicit_pin:
            # Explicit invocation override wins over the stored project pin for
            # this run only; it does not mutate project.json.
            args += ['--provider', str(known.provider), '--model', str(known.model)]
    else:
        args = raw

    proc = subprocess.run([sys.executable, str(controller), *args], cwd=root)
    return int(proc.returncode)


if __name__ == '__main__':
    raise SystemExit(main())
