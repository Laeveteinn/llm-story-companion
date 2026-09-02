from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _config_path(slug: str) -> Path:
    return ROOT / 'projects' / slug / 'project.json'


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='Show, pin, or clear the Hermes provider/model used by one writing project.')
    ap.add_argument('slug')
    ap.add_argument('--provider')
    ap.add_argument('--model')
    ap.add_argument('--clear', action='store_true')
    ap.add_argument('--show', action='store_true')
    args = ap.parse_args(argv)

    path = _config_path(args.slug)
    if not path.is_file():
        raise SystemExit(f'unknown writing project {args.slug!r}: {path}')
    config = json.loads(path.read_text(encoding='utf-8'))

    if args.clear:
        if args.provider or args.model:
            raise SystemExit('--clear cannot be combined with --provider/--model')
        config.pop('provider', None)
        config.pop('model', None)
        action = 'cleared'
    elif args.provider or args.model:
        if not (args.provider and args.model):
            raise SystemExit('pinning requires both --provider and --model')
        config['provider'] = args.provider.strip()
        config['model'] = args.model.strip()
        if not config['provider'] or not config['model']:
            raise SystemExit('provider and model must be non-empty')
        action = 'pinned'
    else:
        action = 'shown'

    if action != 'shown':
        tmp = path.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        tmp.replace(path)

    print(json.dumps({
        'status': action,
        'project': args.slug,
        'provider': config.get('provider'),
        'model': config.get('model'),
        'config': str(path),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
