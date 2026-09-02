from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import json
import re
import sqlite3
import yaml

from .textutil import normalize_phrase
from .temporal import branch_lineage, branch_visibility, validate_branch_definitions

SCHEMA_VERSION = 5

SCHEMA = r'''
PRAGMA foreign_keys = ON;

CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE timeline_point (
    key TEXT PRIMARY KEY,
    ordinal INTEGER NOT NULL UNIQUE,
    label TEXT,
    story_time TEXT
);

CREATE TABLE timeline_branch (
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES timeline_branch(id),
    fork_at_key TEXT REFERENCES timeline_point(key),
    fork_ordinal INTEGER,
    kind TEXT NOT NULL DEFAULT 'alternate' CHECK(kind IN ('canonical','alternate','retcon','simulation','time_travel')),
    label TEXT,
    writer_safe INTEGER NOT NULL DEFAULT 1 CHECK(writer_safe IN (0,1)),
    CHECK ((id='main' AND parent_id IS NULL AND fork_at_key IS NULL AND fork_ordinal IS NULL)
        OR (id<>'main' AND parent_id IS NOT NULL AND fork_at_key IS NOT NULL AND fork_ordinal IS NOT NULL))
);

CREATE TABLE canon_entry (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    disclosure_state TEXT NOT NULL DEFAULT 'unspecified',
    summary TEXT,
    min_trigger_hits INTEGER NOT NULL DEFAULT 1 CHECK (min_trigger_hits >= 1),
    priority INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE canon_trigger (
    entry_id TEXT NOT NULL REFERENCES canon_entry(id) ON DELETE CASCADE,
    phrase TEXT NOT NULL,
    normalized TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('trigger','alias','exclude')),
    weight INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(entry_id, normalized, kind)
);
CREATE INDEX canon_trigger_normalized_idx ON canon_trigger(normalized);

CREATE TABLE canon_fact (
    id INTEGER PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES canon_entry(id) ON DELETE CASCADE,
    branch_id TEXT NOT NULL DEFAULT 'main' REFERENCES timeline_branch(id),
    fact_key TEXT NOT NULL,
    value_json TEXT,
    status TEXT NOT NULL DEFAULT 'canon',
    valid_from TEXT REFERENCES timeline_point(key),
    valid_to TEXT REFERENCES timeline_point(key),
    critical INTEGER NOT NULL DEFAULT 1 CHECK (critical IN (0,1)),
    disclosure_state TEXT NOT NULL DEFAULT 'inherit',
    source TEXT,
    UNIQUE(entry_id, branch_id, fact_key, valid_from)
);
CREATE INDEX canon_fact_entry_idx ON canon_fact(entry_id);

CREATE TABLE canon_fact_trigger (
    fact_id INTEGER NOT NULL REFERENCES canon_fact(id) ON DELETE CASCADE,
    phrase TEXT NOT NULL,
    normalized TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('trigger','alias','exclude')),
    PRIMARY KEY(fact_id, normalized, kind)
);
CREATE INDEX canon_fact_trigger_normalized_idx ON canon_fact_trigger(normalized);

CREATE TABLE canon_knowledge (
    entry_id TEXT NOT NULL REFERENCES canon_entry(id) ON DELETE CASCADE,
    actor TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'unknown',
    notes TEXT,
    PRIMARY KEY(entry_id, actor)
);

CREATE TABLE canon_reveal (
    id INTEGER PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES canon_entry(id) ON DELETE CASCADE,
    branch_id TEXT NOT NULL DEFAULT 'main' REFERENCES timeline_branch(id),
    actor TEXT NOT NULL,
    at_key TEXT NOT NULL REFERENCES timeline_point(key),
    fact_key TEXT,
    content TEXT NOT NULL,
    disclosure_level TEXT,
    UNIQUE(entry_id, branch_id, actor, at_key, content)
);
CREATE INDEX canon_reveal_lookup_idx ON canon_reveal(entry_id, actor, at_key);

CREATE TABLE canon_event (
    id INTEGER PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES canon_entry(id) ON DELETE CASCADE,
    branch_id TEXT NOT NULL DEFAULT 'main' REFERENCES timeline_branch(id),
    at_key TEXT NOT NULL REFERENCES timeline_point(key),
    event TEXT NOT NULL,
    UNIQUE(entry_id, branch_id, at_key, event)
);

CREATE TABLE canon_mechanic (
    id INTEGER PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES canon_entry(id) ON DELETE CASCADE,
    branch_id TEXT NOT NULL DEFAULT 'main' REFERENCES timeline_branch(id),
    mechanic_key TEXT NOT NULL,
    valid_from TEXT REFERENCES timeline_point(key),
    valid_to TEXT REFERENCES timeline_point(key),
    spec_json TEXT NOT NULL
);
CREATE INDEX canon_mechanic_lookup_idx ON canon_mechanic(entry_id, mechanic_key, branch_id);

CREATE TABLE canon_relationship (
    entry_id TEXT NOT NULL REFERENCES canon_entry(id) ON DELETE CASCADE,
    relation TEXT NOT NULL,
    target_id TEXT NOT NULL,
    details_json TEXT,
    PRIMARY KEY(entry_id, relation, target_id)
);

CREATE VIRTUAL TABLE canon_fts USING fts5(
    entry_id UNINDEXED,
    title,
    summary,
    notes,
    facts,
    triggers,
    tokenize = 'unicode61 remove_diacritics 2'
);
'''


@dataclass(frozen=True)
class TriggeredEntry:
    id: str
    score: int
    matched: tuple[str, ...]
    payload: dict[str, Any]


def _iter_yaml(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    yield from sorted([*path.glob('*.yaml'), *path.glob('*.yml')])


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _as_fact_rows(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Accept v0.2 facts, while importing v0.1 `state` without losing information."""
    if entry.get('facts'):
        out = []
        for fact in entry['facts']:
            if 'key' not in fact:
                raise ValueError(f"{entry.get('id')}: fact missing key")
            row = dict(fact)
            row.setdefault('status', 'canon')
            row.setdefault('critical', True)
            out.append(row)
        return out

    state = entry.get('state', {})
    out = []
    if isinstance(state, dict):
        for key, value in state.items():
            if key == 'revealed':
                continue
            if key == 'unresolved' and isinstance(value, list):
                for i, unresolved in enumerate(value, 1):
                    out.append({
                        'key': f'unresolved_{i}',
                        'value': unresolved,
                        'status': 'tbd',
                        'critical': True,
                    })
            else:
                out.append({'key': key, 'value': value, 'status': 'canon', 'critical': True})
    return out


def build_canon_database(source: str | Path, output: str | Path) -> Path:
    source = Path(source)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    docs: list[dict[str, Any]] = []
    for file in _iter_yaml(source):
        data = yaml.safe_load(file.read_text(encoding='utf-8')) or {}
        if not isinstance(data, dict):
            raise ValueError(f'{file}: top-level YAML must be a mapping')
        docs.append(data)

    timeline: dict[str, dict[str, Any]] = {}
    branch_specs: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for data in docs:
        for point in data.get('timeline_points', []):
            key = str(point['key'])
            if key in timeline and timeline[key] != point:
                raise ValueError(f'conflicting timeline point: {key}')
            timeline[key] = point
        branch_specs.extend(data.get('timeline_branches', data.get('branches', [])) or [])
        entries.extend(data.get('entries', []))

    # v0.1 compatibility: infer stable chapter ordinals only for exact bookN/chM keys.
    referenced: set[str] = set()
    for entry in entries:
        for fact in _as_fact_rows(entry):
            for key in ('valid_from', 'valid_to'):
                if fact.get(key):
                    referenced.add(str(fact[key]))
        for actor in (entry.get('knowledge') or {}).values():
            if isinstance(actor, dict):
                for reveal in actor.get('reveals', []):
                    if reveal.get('at'):
                        referenced.add(str(reveal['at']))
        for event in entry.get('timeline', []):
            if event.get('at'):
                referenced.add(str(event['at']))

    for key in sorted(referenced):
        if key in timeline:
            continue
        m = re.fullmatch(r'book(\d+)/ch(\d+)', key, re.I)
        if not m:
            raise ValueError(
                f'timeline point {key!r} is referenced but not declared; '
                'declare timeline_points with an explicit integer ordinal'
            )
        book, chapter = map(int, m.groups())
        timeline[key] = {'key': key, 'ordinal': book * 1_000_000 + chapter}

    ordinals: dict[int, str] = {}
    for key, point in timeline.items():
        if 'ordinal' not in point:
            raise ValueError(f'timeline point {key!r} requires integer ordinal')
        ordinal = int(point['ordinal'])
        if ordinal in ordinals and ordinals[ordinal] != key:
            raise ValueError(f'duplicate timeline ordinal {ordinal}: {key}, {ordinals[ordinal]}')
        ordinals[ordinal] = key

    tmp = output.with_suffix(output.suffix + '.tmp')
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    try:
        con.executescript(SCHEMA)
        con.execute('INSERT INTO meta(key,value) VALUES(?,?)', ('schema_version', str(SCHEMA_VERSION)))
        con.execute('INSERT INTO meta(key,value) VALUES(?,?)', ('source', str(source)))

        for key, point in sorted(timeline.items(), key=lambda kv: int(kv[1]['ordinal'])):
            con.execute(
                'INSERT INTO timeline_point(key,ordinal,label,story_time) VALUES(?,?,?,?)',
                (key, int(point['ordinal']), point.get('label'), point.get('story_time')),
            )

        normalized_branches = validate_branch_definitions(branch_specs, {k:int(v['ordinal']) for k,v in timeline.items()})
        # Insert root before descendants, then repeatedly insert branches whose parent exists.
        pending = {b['id']: b for b in normalized_branches}
        while pending:
            progressed = False
            for bid in sorted(list(pending)):
                b = pending[bid]
                parent = b['parent']
                if parent is not None and con.execute('SELECT 1 FROM timeline_branch WHERE id=?',(parent,)).fetchone() is None:
                    continue
                con.execute(
                    '''INSERT INTO timeline_branch(id,parent_id,fork_at_key,fork_ordinal,kind,label,writer_safe)
                       VALUES(?,?,?,?,?,?,?)''',
                    (bid,parent,b['fork_at'],b['fork_ordinal'],b['kind'],b.get('label'),1 if b.get('writer_safe',True) else 0),
                )
                del pending[bid]; progressed = True
            if not progressed:
                raise ValueError('could not topologically insert timeline branches')
        known_branches = {r[0] for r in con.execute('SELECT id FROM timeline_branch')}

        seen_ids: set[str] = set()
        for entry in entries:
            eid = str(entry['id'])
            if eid in seen_ids:
                raise ValueError(f'duplicate canon id {eid}')
            seen_ids.add(eid)
            title = str(entry['title'])
            triggers = entry.get('triggers') or []
            if not triggers:
                raise ValueError(f'{eid}: triggers must be non-empty')
            state = entry.get('state') or {}
            disclosure = entry.get('disclosure_state') or (
                state.get('revealed', 'unspecified') if isinstance(state, dict) else 'unspecified'
            )
            summary = entry.get('summary') or (state.get('summary') if isinstance(state, dict) else None)
            con.execute(
                '''INSERT INTO canon_entry
                   (id,title,status,disclosure_state,summary,min_trigger_hits,priority,notes)
                   VALUES(?,?,?,?,?,?,?,?)''',
                (
                    eid, title, entry.get('status', 'active'), disclosure, summary,
                    int(entry.get('min_trigger_hits', 1)), int(entry.get('priority', 0)),
                    entry.get('notes'),
                ),
            )

            for kind, phrases, default_weight in (
                ('trigger', triggers, 3),
                ('alias', entry.get('aliases', []), 2),
                ('exclude', entry.get('exclude_triggers', []), 0),
            ):
                for phrase in phrases:
                    norm = normalize_phrase(str(phrase))
                    if not norm:
                        continue
                    weight = default_weight + (1 if ' ' in norm and kind != 'exclude' else 0)
                    con.execute(
                        'INSERT INTO canon_trigger(entry_id,phrase,normalized,kind,weight) VALUES(?,?,?,?,?)',
                        (eid, str(phrase), norm, kind, weight),
                    )

            facts = _as_fact_rows(entry)
            for fact in facts:
                fact_branch = str(fact.get('branch','main'))
                if fact_branch not in known_branches:
                    raise ValueError(f'{eid}.{fact.get("key")}: unknown timeline branch {fact_branch}')
                cur = con.execute(
                    '''INSERT INTO canon_fact
                       (entry_id,branch_id,fact_key,value_json,status,valid_from,valid_to,critical,disclosure_state,source)
                       VALUES(?,?,?,?,?,?,?,?,?,?)''',
                    (
                        eid, str(fact.get('branch','main')), str(fact['key']), _json(fact.get('value')), fact.get('status', 'canon'),
                        fact.get('valid_from'), fact.get('valid_to'), 1 if fact.get('critical', True) else 0,
                        fact.get('disclosure_state', 'inherit'), fact.get('source'),
                    ),
                )
                fact_id = int(cur.lastrowid)
                for fact_kind, phrases in (
                    ('trigger', fact.get('triggers', [])),
                    ('alias', fact.get('aliases', [])),
                    ('exclude', fact.get('exclude_triggers', [])),
                ):
                    for phrase in phrases:
                        norm = normalize_phrase(str(phrase))
                        if norm:
                            con.execute(
                                'INSERT INTO canon_fact_trigger(fact_id,phrase,normalized,kind) VALUES(?,?,?,?)',
                                (fact_id, str(phrase), norm, fact_kind),
                            )

            for actor, info in (entry.get('knowledge') or {}).items():
                if not isinstance(info, dict):
                    info = {'level': str(info)}
                con.execute(
                    'INSERT INTO canon_knowledge(entry_id,actor,level,notes) VALUES(?,?,?,?)',
                    (eid, str(actor), info.get('level', 'unknown'), info.get('notes')),
                )
                for reveal in info.get('reveals', []):
                    at = str(reveal['at'])
                    reveal_branch = str(reveal.get('branch','main'))
                    if reveal_branch not in known_branches:
                        raise ValueError(f'{eid}/{actor}: reveal references unknown timeline branch {reveal_branch}')
                    con.execute(
                        '''INSERT INTO canon_reveal
                           (entry_id,branch_id,actor,at_key,fact_key,content,disclosure_level)
                           VALUES(?,?,?,?,?,?,?)''',
                        (
                            eid, str(reveal.get('branch','main')), str(actor), at, reveal.get('fact_key'),
                            str(reveal.get('fact') or reveal.get('content')),
                            reveal.get('level'),
                        ),
                    )

            for event in entry.get('timeline', []):
                event_branch = str(event.get('branch','main'))
                if event_branch not in known_branches:
                    raise ValueError(f'{eid}: event references unknown timeline branch {event_branch}')
                con.execute(
                    'INSERT INTO canon_event(entry_id,branch_id,at_key,event) VALUES(?,?,?,?)',
                    (eid, event_branch, str(event['at']), str(event['event'])),
                )

            mechanics = entry.get('mechanics')
            if mechanics:
                rows = list(mechanics.items()) if isinstance(mechanics, dict) else [('default', mechanics)]
                for key, value in rows:
                    con.execute(
                        'INSERT INTO canon_mechanic(entry_id,branch_id,mechanic_key,valid_from,valid_to,spec_json) VALUES(?,?,?,?,?,?)',
                        (eid, 'main', str(key), None, None, _json(value)),
                    )
            for version in entry.get('mechanic_versions', entry.get('mechanics_versions', [])) or []:
                mbranch=str(version.get('branch','main'))
                if mbranch not in known_branches:
                    raise ValueError(f'{eid}: mechanic version references unknown timeline branch {mbranch}')
                vfrom=str(version['valid_from']) if version.get('valid_from') else None
                vto=str(version['valid_to']) if version.get('valid_to') else None
                for label,key in [('valid_from',vfrom),('valid_to',vto)]:
                    if key and key not in timeline:
                        raise ValueError(f'{eid}: mechanic {label} references unknown timeline point {key}')
                if 'key' not in version:
                    raise ValueError(f'{eid}: mechanic version missing key')
                con.execute(
                    'INSERT INTO canon_mechanic(entry_id,branch_id,mechanic_key,valid_from,valid_to,spec_json) VALUES(?,?,?,?,?,?)',
                    (eid,mbranch,str(version['key']),vfrom,vto,_json(version.get('value'))),
                )

            relationships = entry.get('relationships') or []
            if isinstance(relationships, dict):
                relationships = [
                    {'relation': k, 'target': v if isinstance(v, str) else str(k), 'details': v}
                    for k, v in relationships.items()
                ]
            for rel in relationships:
                con.execute(
                    'INSERT INTO canon_relationship(entry_id,relation,target_id,details_json) VALUES(?,?,?,?)',
                    (eid, str(rel['relation']), str(rel['target']), _json(rel.get('details'))),
                )

            fact_text = ' '.join(
                str(f.get('value', '')) for f in facts if f.get('value') is not None
            )
            trigger_text = ' '.join(map(str, [*triggers, *entry.get('aliases', [])]))
            con.execute(
                'INSERT INTO canon_fts(entry_id,title,summary,notes,facts,triggers) VALUES(?,?,?,?,?,?)',
                (eid, title, summary or '', entry.get('notes') or '', fact_text, trigger_text),
            )

        con.commit()
        integrity = con.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity != 'ok':
            raise RuntimeError(f'SQLite integrity check failed: {integrity}')
    except Exception:
        con.close()
        if tmp.exists():
            tmp.unlink()
        raise
    else:
        con.close()
        output.unlink(missing_ok=True)
        tmp.replace(output)
    return output


class CanonLibrary:
    """SQLite-backed deterministic canon runtime."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        self.con = sqlite3.connect(self.path)
        self.con.row_factory = sqlite3.Row
        self.con.execute('PRAGMA foreign_keys = ON')
        version = self.con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if not version or int(version[0]) != SCHEMA_VERSION:
            raise ValueError(f'unsupported canon schema in {self.path}')

    @classmethod
    def load(cls, path: str | Path) -> 'CanonLibrary':
        p = Path(path)
        if p.is_dir():
            candidates = sorted([*p.glob('*.sqlite3'), *p.glob('*.sqlite'), *p.glob('*.db')])
            if len(candidates) != 1:
                raise ValueError(f'{p}: expected exactly one SQLite canon database, found {len(candidates)}')
            p = candidates[0]
        return cls(p)

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> 'CanonLibrary':
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def _ordinal(self, at: str | None) -> int | None:
        if at is None:
            return None
        row = self.con.execute('SELECT ordinal FROM timeline_point WHERE key=?', (at,)).fetchone()
        if not row:
            raise ValueError(f'unknown timeline point: {at}')
        return int(row['ordinal'])

    def branch_exists(self, branch: str) -> bool:
        return bool(self.con.execute('SELECT 1 FROM timeline_branch WHERE id=?', (branch,)).fetchone())

    def branch_info(self, branch: str) -> dict[str, Any]:
        row = self.con.execute('SELECT * FROM timeline_branch WHERE id=?', (branch,)).fetchone()
        if not row:
            raise ValueError(f'unknown timeline branch: {branch}')
        return dict(row)

    def branches(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.con.execute(
            'SELECT id,parent_id,fork_at_key,fork_ordinal,kind,label,writer_safe FROM timeline_branch ORDER BY id'
        )]

    def _branch_windows(self, branch: str, ordinal: int | None) -> dict[str, dict[str, Any]]:
        lineage = branch_lineage(self.con, branch)
        windows: dict[str, dict[str, Any]] = {}
        for i, b in enumerate(lineage):
            start = b.fork_ordinal
            if ordinal is not None and start is not None and ordinal < start:
                # The selected descendant does not exist yet; its ancestors still describe history.
                continue
            if i == len(lineage) - 1:
                ceiling = ordinal
            else:
                child = lineage[i + 1]
                ceiling = child.fork_ordinal if ordinal is None else min(ordinal, int(child.fork_ordinal))
            windows[b.id] = {'start': start, 'ceiling': ceiling, 'rank': i}
        if 'main' not in windows:
            windows['main'] = {'start': None, 'ceiling': ordinal, 'rank': 0}
        return windows

    @staticmethod
    def _phrase_hit(norm_text: str, phrase: str) -> bool:
        p = normalize_phrase(phrase)
        return bool(p and re.search(r'(?<!\w)' + re.escape(p) + r'(?!\w)', norm_text))

    def trigger(
        self,
        text: str,
        *,
        viewpoint: str | None = None,
        at: str | None = None,
        max_entries: int = 12,
        scope: str = 'writer',
        branch: str = 'main',
    ) -> list[TriggeredEntry]:
        if scope not in {'writer', 'pov'}:
            raise ValueError("scope must be 'writer' or 'pov'")
        norm = normalize_phrase(text)
        rows = self.con.execute(
            '''SELECT e.id,e.min_trigger_hits,e.priority,t.phrase,t.kind,t.weight
               FROM canon_entry e JOIN canon_trigger t ON t.entry_id=e.id
               WHERE e.status='active' ORDER BY e.id,t.kind,t.phrase'''
        ).fetchall()
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            bucket = grouped.setdefault(row['id'], {
                'min': int(row['min_trigger_hits']), 'priority': int(row['priority']),
                'hits': [], 'score': 0, 'excluded': False,
            })
            if not self._phrase_hit(norm, row['phrase']):
                continue
            if row['kind'] == 'exclude':
                bucket['excluded'] = True
            else:
                bucket['hits'].append(row['phrase'])
                bucket['score'] += int(row['weight'])

        out: list[TriggeredEntry] = []
        for eid, bucket in grouped.items():
            if bucket['excluded'] or len(bucket['hits']) < bucket['min']:
                continue
            payload = self._surface(eid, viewpoint=viewpoint, at=at, scope=scope, branch=branch)
            score = bucket['score'] + bucket['priority']
            out.append(TriggeredEntry(eid, score, tuple(bucket['hits']), payload))
        out.sort(key=lambda x: (-x.score, x.id))
        return out[:max_entries]

    def _surface(self, eid: str, *, viewpoint: str | None, at: str | None, scope: str, branch: str = 'main') -> dict[str, Any]:
        ordinal = self._ordinal(at)
        entry = self.con.execute('SELECT * FROM canon_entry WHERE id=?', (eid,)).fetchone()
        if not entry:
            raise KeyError(eid)

        payload: dict[str, Any] = {
            'id': eid,
            'title': entry['title'],
            'status': entry['status'],
            'disclosure_state': entry['disclosure_state'],
        }

        if scope == 'writer':
            payload['canon'] = {
                'summary': entry['summary'],
                'facts': self._facts(eid, ordinal, branch),
                'timeline': self._events(eid, ordinal, branch),
            }
            mechanics = self._mechanics(eid, ordinal, branch)
            if mechanics:
                payload['mechanics'] = mechanics
            rels = self._relationships(eid)
            if rels:
                payload['relationships'] = rels
            if entry['notes']:
                payload['notes'] = entry['notes']

        if viewpoint is not None:
            payload['knowledge'] = self._knowledge(eid, viewpoint, ordinal, branch)
            if scope == 'pov':
                # POV-safe canon surface: include only fact values already disclosed/public.
                known = []
                for fact in self._facts(eid, ordinal, branch):
                    if self.fact_disclosed_to(eid, fact['key'], viewpoint, at, branch=branch):
                        known.append(fact)
                if known:
                    payload['known_facts'] = known
        elif scope == 'pov':
            raise ValueError('pov scope requires viewpoint')

        return payload

    def _facts(self, eid: str, ordinal: int | None, branch: str = 'main') -> list[dict[str, Any]]:
        windows = self._branch_windows(branch, ordinal)
        rows = self.con.execute(
            """SELECT f.*, vf.ordinal AS from_ord, vt.ordinal AS to_ord
               FROM canon_fact f
               LEFT JOIN timeline_point vf ON vf.key=f.valid_from
               LEFT JOIN timeline_point vt ON vt.key=f.valid_to
               WHERE f.entry_id=? ORDER BY f.fact_key, f.branch_id, COALESCE(vf.ordinal,-1), f.id""",
            (eid,),
        ).fetchall()
        candidates: dict[str, tuple[int, int, sqlite3.Row]] = {}
        for row in rows:
            win = windows.get(str(row['branch_id']))
            if not win:
                continue
            eval_ord = win['ceiling']
            branch_start = win['start']
            # Branch-local timeless facts begin when the branch itself begins.
            effective_from = int(row['from_ord']) if row['from_ord'] is not None else branch_start
            if eval_ord is not None and effective_from is not None and effective_from > eval_ord:
                continue
            if row['to_ord'] is not None and eval_ord is not None and eval_ord >= int(row['to_ord']):
                continue
            if eval_ord is None and row['valid_to'] is not None:
                continue
            from_rank = effective_from if effective_from is not None else -1
            score = (int(win['rank']), int(from_rank))
            prev = candidates.get(str(row['fact_key']))
            if prev is None or score > (prev[0], prev[1]):
                candidates[str(row['fact_key'])] = (score[0], score[1], row)
        out=[]
        for key in sorted(candidates):
            row=candidates[key][2]
            out.append({
                'key': row['fact_key'],
                'value': json.loads(row['value_json']) if row['value_json'] is not None else None,
                'status': row['status'],
                'critical': bool(row['critical']),
                'disclosure_state': row['disclosure_state'],
                'branch': row['branch_id'],
                **({'valid_from': row['valid_from']} if row['valid_from'] else {}),
                **({'valid_to': row['valid_to']} if row['valid_to'] else {}),
                **({'source': row['source']} if row['source'] else {}),
            })
        return out

    def _events(self, eid: str, ordinal: int | None, branch: str = 'main') -> list[dict[str, Any]]:
        windows = self._branch_windows(branch, ordinal)
        rows = self.con.execute(
            """SELECT e.branch_id,e.at_key,e.event,t.ordinal FROM canon_event e
               JOIN timeline_point t ON t.key=e.at_key WHERE e.entry_id=?
               ORDER BY t.ordinal,e.id""",
            (eid,),
        ).fetchall()
        out=[]
        for row in rows:
            win=windows.get(str(row['branch_id']))
            if not win: continue
            ceiling=win['ceiling']
            start=win['start']
            ro=int(row['ordinal'])
            if start is not None and ro < int(start):
                continue
            if ceiling is not None and ro > int(ceiling):
                continue
            out.append({'at':row['at_key'],'event':row['event'],'branch':row['branch_id']})
        return out

    def _knowledge(self, eid: str, actor: str, ordinal: int | None, branch: str = 'main') -> dict[str, Any]:
        row = self.con.execute(
            'SELECT level,notes FROM canon_knowledge WHERE entry_id=? AND actor=?',
            (eid, actor),
        ).fetchone()
        if row is None:
            row = self.con.execute(
                'SELECT level,notes FROM canon_knowledge WHERE entry_id=? AND actor=?',
                (eid, 'default'),
            ).fetchone()
        level = row['level'] if row else 'unknown'
        notes = row['notes'] if row else None
        windows=self._branch_windows(branch, ordinal)
        reveals = self.con.execute(
            """SELECT r.branch_id,r.at_key,r.fact_key,r.content,r.disclosure_level,t.ordinal
               FROM canon_reveal r JOIN timeline_point t ON t.key=r.at_key
               WHERE r.entry_id=? AND r.actor IN (?, 'default')
               ORDER BY t.ordinal,r.id""",
            (eid, actor),
        ).fetchall()
        visible=[]
        for r in reveals:
            win=windows.get(str(r['branch_id']))
            if not win: continue
            ro=int(r['ordinal']); start=win['start']; ceiling=win['ceiling']
            if start is not None and ro < int(start): continue
            if ceiling is not None and ro > int(ceiling): continue
            visible.append(r)
        result = {
            'viewpoint': actor,
            'level': level,
            'branch': branch,
            'reveals': [
                {
                    'at': r['at_key'],
                    'branch': r['branch_id'],
                    **({'fact_key': r['fact_key']} if r['fact_key'] else {}),
                    'fact': r['content'],
                    **({'level': r['disclosure_level']} if r['disclosure_level'] else {}),
                }
                for r in visible
            ],
        }
        if notes:
            result['notes'] = notes
        return result

    def _mechanics(self, eid: str, ordinal: int | None, branch: str = 'main') -> dict[str, Any]:
        windows=self._branch_windows(branch, ordinal)
        rows=self.con.execute(
            """SELECT m.*,vf.ordinal AS from_ord,vt.ordinal AS to_ord
               FROM canon_mechanic m
               LEFT JOIN timeline_point vf ON vf.key=m.valid_from
               LEFT JOIN timeline_point vt ON vt.key=m.valid_to
               WHERE m.entry_id=? ORDER BY m.mechanic_key,m.branch_id,COALESCE(vf.ordinal,-1),m.id""",
            (eid,),
        ).fetchall()
        candidates: dict[str, tuple[int,int,sqlite3.Row]]={}
        for row in rows:
            win=windows.get(str(row['branch_id']))
            if not win: continue
            eval_ord=win['ceiling']; branch_start=win['start']
            effective_from=int(row['from_ord']) if row['from_ord'] is not None else branch_start
            if eval_ord is not None and effective_from is not None and effective_from > eval_ord: continue
            if row['to_ord'] is not None and eval_ord is not None and eval_ord >= int(row['to_ord']): continue
            if eval_ord is None and row['valid_to'] is not None: continue
            from_rank=effective_from if effective_from is not None else -1
            score=(int(win['rank']),int(from_rank))
            prev=candidates.get(str(row['mechanic_key']))
            if prev is None or score > (prev[0],prev[1]): candidates[str(row['mechanic_key'])]=(score[0],score[1],row)
        return {key:json.loads(candidates[key][2]['spec_json']) for key in sorted(candidates)}

    def _relationships(self, eid: str) -> list[dict[str, Any]]:
        rows = self.con.execute(
            'SELECT relation,target_id,details_json FROM canon_relationship WHERE entry_id=? ORDER BY relation,target_id',
            (eid,),
        ).fetchall()
        return [
            {
                'relation': r['relation'], 'target': r['target_id'],
                **({'details': json.loads(r['details_json'])} if r['details_json'] else {}),
            }
            for r in rows
        ]


    def _visible_reveal_exists(self, eid: str, actor: str, ordinal: int, *, branch: str = 'main',
                               fact_key: str | None = None, strict_before: bool = False) -> bool:
        windows=self._branch_windows(branch, ordinal)
        sql="""SELECT r.branch_id,r.fact_key,t.ordinal FROM canon_reveal r
                 JOIN timeline_point t ON t.key=r.at_key
                 WHERE r.entry_id=? AND r.actor IN (?, 'default')"""
        params: list[Any]=[eid, actor]
        if fact_key is not None:
            sql += ' AND r.fact_key=?'; params.append(fact_key)
        for r in self.con.execute(sql, params):
            win=windows.get(str(r['branch_id']))
            if not win: continue
            ro=int(r['ordinal']); start=win['start']; ceiling=win['ceiling']
            if start is not None and ro < int(start): continue
            if ceiling is not None and ro > int(ceiling): continue
            if strict_before and ro >= ordinal: continue
            return True
        return False

    def _visible_reveal_ordinals(self, eid: str, actor: str, fact_key: str, *, branch: str = 'main') -> list[int]:
        # Use each branch's own horizon rather than an arbitrary chapter horizon; callers can filter.
        lineage=branch_lineage(self.con, branch)
        # For the selected branch, there is no upper bound; ancestors stop at child forks.
        ceilings: dict[str,int|None]={}
        for i,b in enumerate(lineage):
            ceilings[b.id] = None if i == len(lineage)-1 else int(lineage[i+1].fork_ordinal)
        starts={b.id:b.fork_ordinal for b in lineage}
        out=[]
        for r in self.con.execute(
            """SELECT r.branch_id,t.ordinal FROM canon_reveal r JOIN timeline_point t ON t.key=r.at_key
               WHERE r.entry_id=? AND r.fact_key=? AND r.actor IN (?, 'default') ORDER BY t.ordinal,r.id""",
            (eid,fact_key,actor),
        ):
            bid=str(r['branch_id'])
            if bid not in ceilings: continue
            ro=int(r['ordinal']); start=starts.get(bid); ceiling=ceilings[bid]
            if start is not None and ro < int(start): continue
            if ceiling is not None and ro > int(ceiling): continue
            out.append(ro)
        return out


    def disclosure_audit(self, text: str, *, viewpoint: str, at: str, branch: str = 'main') -> list[dict[str, Any]]:
        # Deterministically flag configured entry/fact phrases unavailable to a POV.
        # Fact triggers are crucial for partial disclosure: knowing an object exists
        # does not imply knowing every critical fact or mechanic attached to it.
        ordinal = self._ordinal(at)
        safe_states = {'public', 'revealed', 'common', 'common_knowledge', 'open'}

        def matches(phrase: str) -> list[dict[str, Any]]:
            pattern = re.compile(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', re.I)
            found = []
            for m in pattern.finditer(text):
                line = text.count('\n', 0, m.start()) + 1
                col = m.start() - text.rfind('\n', 0, m.start())
                found.append({'phrase': phrase, 'line': line, 'column': col, 'start': m.start(), 'end': m.end()})
            return found

        def revealed_fact(eid: str, fact_key: str | None) -> bool:
            krow = self.con.execute(
                "SELECT level FROM canon_knowledge WHERE entry_id=? AND actor IN (?, 'default') "
                "ORDER BY CASE actor WHEN ? THEN 0 ELSE 1 END LIMIT 1",
                (eid, viewpoint, viewpoint),
            ).fetchone()
            if krow and str(krow['level']).lower() in {'full', 'complete', 'omniscient'}:
                return True
            return self._visible_reveal_exists(eid, viewpoint, ordinal, branch=branch, fact_key=fact_key)

        out: list[dict[str, Any]] = []

        # Entry-level concept access.
        rows = self.con.execute(
            """SELECT e.id,e.title,e.disclosure_state,e.min_trigger_hits,t.phrase,t.kind
               FROM canon_entry e JOIN canon_trigger t ON t.entry_id=e.id
               WHERE e.status='active' ORDER BY e.id,t.kind,t.phrase"""
        ).fetchall()
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            bucket = grouped.setdefault(row['id'], {
                'kind': 'entry', 'id': row['id'], 'title': row['title'],
                'disclosure_state': row['disclosure_state'], 'min': int(row['min_trigger_hits']),
                'matches': [], 'excluded': False,
            })
            hits = matches(str(row['phrase']))
            if not hits:
                continue
            if row['kind'] == 'exclude':
                bucket['excluded'] = True
            else:
                bucket['matches'].extend(hits)
        for eid, bucket in grouped.items():
            if bucket['excluded'] or len(bucket['matches']) < bucket['min']:
                continue
            if str(bucket['disclosure_state']).lower() in safe_states or revealed_fact(eid, None):
                continue
            bucket.update({'viewpoint': viewpoint, 'at': at, 'branch': branch})
            out.append(bucket)

        # Fact-level access. Only deliberately authored literal phrases participate.
        frows = self.con.execute(
            """SELECT f.id AS fact_id,f.entry_id,f.branch_id,f.fact_key,f.critical,f.disclosure_state,
                      e.title,e.disclosure_state AS entry_disclosure,ft.phrase,ft.kind
               FROM canon_fact f JOIN canon_entry e ON e.id=f.entry_id
               JOIN canon_fact_trigger ft ON ft.fact_id=f.id
               WHERE e.status='active' AND f.status IN ('canon','active','tbd')
               ORDER BY f.entry_id,f.fact_key,ft.kind,ft.phrase"""
        ).fetchall()
        fgroup: dict[tuple[int, str], dict[str, Any]] = {}
        active_fact_cache: dict[str, dict[str, dict[str, Any]]] = {}
        for row in frows:
            entry_active = active_fact_cache.setdefault(str(row['entry_id']), {
                f['key']: f for f in self._facts(str(row['entry_id']), ordinal, branch)
            })
            selected = entry_active.get(str(row['fact_key']))
            if not selected or str(selected.get('branch','main')) != str(row['branch_id']):
                continue
            key = (int(row['fact_id']), str(row['fact_key']))
            bucket = fgroup.setdefault(key, {
                'kind': 'fact', 'id': row['entry_id'], 'title': row['title'],
                'fact_key': row['fact_key'], 'critical': bool(row['critical']),
                'disclosure_state': row['disclosure_state'],
                'entry_disclosure_state': row['entry_disclosure'],
                'matches': [], 'excluded': False,
            })
            hits = matches(str(row['phrase']))
            if not hits:
                continue
            if row['kind'] == 'exclude':
                bucket['excluded'] = True
            else:
                bucket['matches'].extend(hits)
        for (_fact_id, fact_key), bucket in fgroup.items():
            if bucket['excluded'] or not bucket['matches']:
                continue
            state = str(bucket['disclosure_state']).lower()
            if state == 'inherit':
                state = str(bucket['entry_disclosure_state']).lower()
            if state in safe_states or revealed_fact(bucket['id'], fact_key):
                continue
            bucket.update({'viewpoint': viewpoint, 'at': at, 'branch': branch})
            out.append(bucket)
        return out


    def timeline_ordinal(self, at: str) -> int:
        value = self._ordinal(at)
        assert value is not None
        return value

    def entry_exists(self, eid: str) -> bool:
        return bool(self.con.execute("SELECT 1 FROM canon_entry WHERE id=? AND status='active'", (eid,)).fetchone())

    def fact_exists(self, eid: str, fact_key: str) -> bool:
        return bool(self.con.execute(
            'SELECT 1 FROM canon_fact WHERE entry_id=? AND fact_key=? LIMIT 1', (eid, fact_key)
        ).fetchone())

    def fact_disclosed_to(self, eid: str, fact_key: str, actor: str, at: str, *, branch: str = 'main') -> bool:
        ordinal = self._ordinal(at)
        assert ordinal is not None
        row = self.con.execute(
            "SELECT level FROM canon_knowledge WHERE entry_id=? AND actor IN (?, 'default') "
            "ORDER BY CASE actor WHEN ? THEN 0 ELSE 1 END LIMIT 1",
            (eid, actor, actor),
        ).fetchone()
        if row and str(row['level']).lower() in {'full','complete','omniscient'}:
            return True
        active = {f['key']:f for f in self._facts(eid, ordinal, branch)}.get(fact_key)
        if not active:
            return False
        state = str(active['disclosure_state']).lower()
        if state == 'inherit':
            erow = self.con.execute('SELECT disclosure_state FROM canon_entry WHERE id=?', (eid,)).fetchone()
            state = str(erow['disclosure_state']).lower() if erow else 'unspecified'
        if state in {'public','revealed','common','common_knowledge','open'}:
            return True
        return self._visible_reveal_exists(eid, actor, ordinal, branch=branch, fact_key=fact_key)

    def fact_available_before(self, eid: str, fact_key: str, actor: str, at: str, *, branch: str = 'main') -> bool:
        """Whether a fact was available strictly before a timeline point on this branch."""
        ordinal = self._ordinal(at)
        assert ordinal is not None
        row = self.con.execute(
            "SELECT level FROM canon_knowledge WHERE entry_id=? AND actor IN (?, 'default') "
            "ORDER BY CASE actor WHEN ? THEN 0 ELSE 1 END LIMIT 1",
            (eid, actor, actor),
        ).fetchone()
        if row and str(row['level']).lower() in {'full','complete','omniscient'}:
            return True
        active = {f['key']:f for f in self._facts(eid, ordinal, branch)}.get(fact_key)
        if not active:
            return False
        state = str(active['disclosure_state']).lower()
        if state == 'inherit':
            erow = self.con.execute('SELECT disclosure_state FROM canon_entry WHERE id=?', (eid,)).fetchone()
            state = str(erow['disclosure_state']).lower() if erow else 'unspecified'
        if state in {'public','revealed','common','common_knowledge','open'}:
            return True
        return self._visible_reveal_exists(eid, actor, ordinal, branch=branch, fact_key=fact_key, strict_before=True)

    def fact_first_reveal_ordinal(self, eid: str, fact_key: str, actor: str, *, branch: str = 'main') -> int | None:
        values=self._visible_reveal_ordinals(eid, actor, fact_key, branch=branch)
        return min(values) if values else None

    def fact_trigger_phrases(self, eid: str, fact_key: str, *, at: str | None = None, branch: str = 'main') -> list[str]:
        ordinal=self._ordinal(at) if at is not None else None
        active = {f['key']:f for f in self._facts(eid, ordinal, branch)}.get(fact_key)
        if not active:
            return []
        rows = self.con.execute(
            """SELECT ft.phrase FROM canon_fact f JOIN canon_fact_trigger ft ON ft.fact_id=f.id
               WHERE f.entry_id=? AND f.fact_key=? AND f.branch_id=? AND ft.kind IN ('trigger','alias')
               ORDER BY LENGTH(ft.phrase) DESC, ft.phrase""",
            (eid, fact_key, active.get('branch','main')),
        ).fetchall()
        return [str(r['phrase']) for r in rows]

    def fact_payload(self, eid: str, fact_key: str, at: str, *, branch: str = 'main') -> dict[str, Any] | None:
        ordinal = self._ordinal(at)
        assert ordinal is not None
        for fact in self._facts(eid, ordinal, branch):
            if fact['key'] == fact_key:
                return {'entry_id': eid, 'title': self.entry_title(eid), **fact}
        return None

    def entry_title(self, eid: str) -> str | None:
        row = self.con.execute('SELECT title FROM canon_entry WHERE id=?', (eid,)).fetchone()
        return str(row['title']) if row else None

    def export_spelling_terms(self) -> list[str]:
        """Return canonical surface forms suitable for a project spell dictionary."""
        values: set[str] = set()
        for row in self.con.execute('SELECT title FROM canon_entry WHERE status=\'active\''):
            values.update(re.findall(r"[A-Za-z][A-Za-z'’-]+", row['title']))
        for table in ('canon_trigger', 'canon_fact_trigger'):
            for row in self.con.execute(
                f"SELECT phrase FROM {table} WHERE kind IN ('trigger','alias')"
            ):
                values.update(re.findall(r"[A-Za-z][A-Za-z'’-]+", row['phrase']))
        return sorted(values, key=lambda x: (x.lower(), x))

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.con.execute(
            '''SELECT f.entry_id,e.title,e.status,e.disclosure_state,bm25(canon_fts) AS rank
               FROM canon_fts f JOIN canon_entry e ON e.id=f.entry_id
               WHERE canon_fts MATCH ? ORDER BY rank LIMIT ?''',
            (query, int(limit)),
        ).fetchall()
        return [dict(r) for r in rows]

    def show(self, eid: str, *, viewpoint: str | None = None, at: str | None = None, scope: str = 'writer', branch: str = 'main') -> dict[str, Any]:
        return self._surface(eid, viewpoint=viewpoint, at=at, scope=scope, branch=branch)

    @staticmethod
    def render(entries: list[TriggeredEntry]) -> str:
        blocks = []
        for hit in entries:
            blocks.append(
                f"[CANON:{hit.id} | trigger={', '.join(hit.matched)}]\n"
                + yaml.safe_dump(hit.payload, sort_keys=False, allow_unicode=True).strip()
            )
        return '\n\n'.join(blocks)

    @staticmethod
    def to_json(entries: list[TriggeredEntry]) -> str:
        return json.dumps([
            {'id': x.id, 'score': x.score, 'matched': x.matched, 'payload': x.payload}
            for x in entries
        ], indent=2, ensure_ascii=False)
