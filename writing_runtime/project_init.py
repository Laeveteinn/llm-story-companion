from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

import yaml

from .canon import build_canon_database
from .story_state import build_state_database

ROOT = Path(__file__).resolve().parents[1]


def _safe_slug(value: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', value.strip().lower()).strip('-')
    if not slug or len(slug) > 80:
        raise ValueError('slug must contain letters/numbers and be at most 80 normalized characters')
    return slug


def _infer_ordinal(chapter_key: str) -> int | None:
    match = re.fullmatch(r'book(\d+)/ch(\d+)', chapter_key, re.I)
    if not match:
        return None
    book, chapter = map(int, match.groups())
    return book * 1_000_000 + chapter


def _dump_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='Create a sparse, isolated story project for a first deterministic writing pilot.')
    ap.add_argument('brief', help='UTF-8 premise/first-chapter brief. Copied verbatim into the project.')
    ap.add_argument('--slug', required=True)
    ap.add_argument('--title', required=True)
    ap.add_argument('--viewpoint', required=True)
    ap.add_argument('--chapter-key', default='book1/ch01')
    ap.add_argument('--at', help='Timeline key; defaults to --chapter-key')
    ap.add_argument('--ordinal', type=int, help='Required for timeline keys other than bookN/chM.')
    ap.add_argument('--branch', default='main')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args(argv)

    slug = _safe_slug(args.slug)
    title = args.title.strip()
    viewpoint = args.viewpoint.strip()
    chapter_key = args.chapter_key.strip()
    at = (args.at or chapter_key).strip()
    if not title or not viewpoint or not chapter_key or not at:
        raise SystemExit('title, viewpoint, chapter key, and timeline key must be non-empty')
    if args.branch != 'main':
        raise SystemExit('new projects must start on main; create alternate/retcon branches after initialization')
    if at != chapter_key:
        raise SystemExit('the sparse first-pilot initializer currently requires --at to equal --chapter-key')

    ordinal = args.ordinal if args.ordinal is not None else _infer_ordinal(at)
    if ordinal is None:
        raise SystemExit('cannot infer timeline ordinal; pass --ordinal for a non-bookN/chM timeline key')

    brief_source = Path(args.brief).resolve()
    if not brief_source.is_file():
        raise SystemExit(f'brief not found: {brief_source}')
    brief_text = brief_source.read_text(encoding='utf-8')
    if not brief_text.strip():
        raise SystemExit('brief is empty')

    project = ROOT / 'projects' / slug
    if project.exists():
        if not args.force:
            raise SystemExit(f'project already exists: {project}')
        shutil.rmtree(project)

    canon_source = project / 'canon_source'
    state_source = project / 'state_source'
    runtime_state = project / 'runtime_state'
    manuscript = project / 'manuscript'
    for path in (canon_source, state_source, runtime_state, manuscript):
        path.mkdir(parents=True, exist_ok=True)

    brief_path = project / 'brief.txt'
    brief_path.write_text(brief_text, encoding='utf-8')

    _dump_yaml(canon_source / 'project.yaml', {
        'timeline_points': [{
            'key': at,
            'ordinal': int(ordinal),
            'label': f'{title} — first pilot',
        }],
        'entries': [],
    })
    _dump_yaml(state_source / 'project.yaml', {
        'subjects': [],
        'events': [],
        'invariants': [],
    })

    canon_library = runtime_state / 'canon.sqlite3'
    state_library = runtime_state / 'story_state.sqlite3'
    build_canon_database(canon_source, canon_library)
    build_state_database(state_source, canon_library, state_library)

    if chapter_key.lower() == 'book1/ch01':
        plan_id = f'{slug}.book1.ch01'
        output = manuscript / 'book1-ch01.txt'
    else:
        normalized = re.sub(r'[^A-Za-z0-9]+', '.', chapter_key).strip('.')
        plan_id = f'{slug}.{normalized}'
        output = manuscript / (re.sub(r'[^A-Za-z0-9._-]+', '-', chapter_key) + '.txt')
    workdir = project / 'runtime_state' / 'pilot-first'

    def rel(path: Path) -> str:
        return path.relative_to(ROOT).as_posix()

    config = {
        'version': 1,
        'slug': slug,
        'title': title,
        'viewpoint': viewpoint,
        'chapter_key': chapter_key,
        'at': at,
        'branch': 'main',
        'plan_id': plan_id,
        'brief': rel(brief_path),
        'canon_source': rel(canon_source),
        'state_source': rel(state_source),
        'canon_library': rel(canon_library),
        'state_library': rel(state_library),
        'workdir': rel(workdir),
        'out': rel(output),
    }
    project_json = project / 'project.json'
    project_json.write_text(json.dumps(config, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    print(json.dumps({
        'status': 'initialized',
        'project': slug,
        'project_root': str(project),
        'project_config': str(project_json),
        'brief': str(brief_path),
        'canon_library': str(canon_library),
        'state_library': str(state_library),
        'next': f'writing-pilot --project {slug} --skip-setup',
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
