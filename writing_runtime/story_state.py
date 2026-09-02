from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable
import fnmatch
import json
import sqlite3
import yaml

from .temporal import branch_lineage

STATE_SCHEMA_VERSION = 3

SCHEMA = r'''
PRAGMA foreign_keys = ON;
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE subject_registry (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('character','item','location','faction','object','concept','other')),
    writer_safe INTEGER NOT NULL DEFAULT 1 CHECK(writer_safe IN (0,1)),
    metadata_json TEXT
);
CREATE TABLE timeline_branch (
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES timeline_branch(id),
    fork_at_key TEXT,
    fork_ordinal INTEGER,
    kind TEXT NOT NULL,
    label TEXT,
    writer_safe INTEGER NOT NULL DEFAULT 1 CHECK(writer_safe IN (0,1))
);
CREATE TABLE state_event (
    id INTEGER PRIMARY KEY,
    branch_id TEXT NOT NULL DEFAULT 'main' REFERENCES timeline_branch(id),
    at_key TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    seq INTEGER NOT NULL DEFAULT 0,
    subject TEXT NOT NULL,
    state_key TEXT NOT NULL,
    op TEXT NOT NULL CHECK(op IN ('set','unset','add','remove','inc','dec')),
    value_json TEXT,
    writer_safe INTEGER NOT NULL DEFAULT 1 CHECK(writer_safe IN (0,1)),
    source TEXT,
    UNIQUE(branch_id,at_key,seq,subject,state_key,op,value_json)
);
CREATE INDEX state_event_time_idx ON state_event(branch_id,ordinal,seq,id);
CREATE INDEX state_event_subject_idx ON state_event(subject,state_key,ordinal);
CREATE TABLE state_invariant (
    id TEXT PRIMARY KEY,
    branch_pattern TEXT NOT NULL DEFAULT '*',
    subject_pattern TEXT NOT NULL DEFAULT '*',
    state_key TEXT NOT NULL,
    op TEXT NOT NULL CHECK(op IN ('eq','neq','exists','not_exists','contains','not_contains','gte','lte','gt','lt')),
    value_json TEXT,
    active_from_ordinal INTEGER,
    active_to_ordinal INTEGER,
    severity TEXT NOT NULL DEFAULT 'hard',
    writer_safe INTEGER NOT NULL DEFAULT 1 CHECK(writer_safe IN (0,1)),
    message TEXT
);
'''


@dataclass(frozen=True)
class StateIssue:
    code: str
    severity: str
    subject: str
    key: str
    message: str
    invariant_id: str | None = None
    path: str | None = None
    evidence: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _json(v: Any) -> str | None:
    return None if v is None else json.dumps(v, ensure_ascii=False, sort_keys=True)


def _load_yaml_documents(source: Path) -> list[dict[str, Any]]:
    files = [source] if source.is_file() else sorted([*source.glob('*.yaml'), *source.glob('*.yml')])
    out = []
    for file in files:
        data = yaml.safe_load(file.read_text(encoding='utf-8')) or {}
        if not isinstance(data, dict):
            raise ValueError(f'{file}: top-level state YAML must be a mapping')
        out.append(data)
    return out


def build_state_database(source: str | Path, canon_library: str | Path, output: str | Path) -> Path:
    """Compile replayable narrative state against canon's typed timeline."""
    source = Path(source)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ccon = sqlite3.connect(canon_library)
    ccon.row_factory = sqlite3.Row
    timeline = {r['key']: int(r['ordinal']) for r in ccon.execute('SELECT key,ordinal FROM timeline_point')}
    canon_branches = [dict(r) for r in ccon.execute(
        'SELECT id,parent_id,fork_at_key,fork_ordinal,kind,label,writer_safe FROM timeline_branch ORDER BY id'
    )]
    ccon.close()

    docs = _load_yaml_documents(source)
    subjects: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = []
    for doc in docs:
        subjects.extend(doc.get('subjects', []) or [])
        events.extend(doc.get('events', []) or [])
        invariants.extend(doc.get('invariants', []) or [])

    tmp = output.with_suffix(output.suffix + '.tmp')
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    try:
        con.executescript(SCHEMA)
        con.execute('INSERT INTO meta(key,value) VALUES(?,?)', ('schema_version', str(STATE_SCHEMA_VERSION)))
        con.execute('INSERT INTO meta(key,value) VALUES(?,?)', ('canon_library', str(canon_library)))
        pending={str(r['id']):r for r in canon_branches}
        while pending:
            progressed=False
            for bid in sorted(list(pending)):
                r=pending[bid]; parent=r['parent_id']
                if parent is not None and con.execute('SELECT 1 FROM timeline_branch WHERE id=?',(parent,)).fetchone() is None:
                    continue
                con.execute('''INSERT INTO timeline_branch(id,parent_id,fork_at_key,fork_ordinal,kind,label,writer_safe)
                               VALUES(?,?,?,?,?,?,?)''',
                            (bid,parent,r['fork_at_key'],r['fork_ordinal'],r['kind'],r['label'],r['writer_safe']))
                del pending[bid]; progressed=True
            if not progressed: raise ValueError('could not import canon timeline branches into story-state database')
        known_branches={r[0] for r in con.execute('SELECT id FROM timeline_branch')}
        branch_forks={r['id']:r['fork_ordinal'] for r in canon_branches}
        seen_subjects: set[str] = set()
        for sub in subjects:
            sid = str(sub['id'])
            if sid in seen_subjects:
                raise ValueError(f'duplicate state subject id {sid}')
            seen_subjects.add(sid)
            kind = str(sub.get('kind','other'))
            metadata = {k:v for k,v in sub.items() if k not in {'id','kind','writer_safe'}}
            con.execute('INSERT INTO subject_registry(id,kind,writer_safe,metadata_json) VALUES(?,?,?,?)',
                        (sid, kind, 1 if sub.get('writer_safe', False) else 0, _json(metadata)))
        for ev in events:
            at = str(ev['at'])
            if at not in timeline:
                raise ValueError(f"state event references unknown timeline point {at!r}")
            branch=str(ev.get('branch','main'))
            if branch not in known_branches:
                raise ValueError(f"state event references unknown timeline branch {branch!r}")
            fork=branch_forks.get(branch)
            if fork is not None and timeline[at] < int(fork):
                raise ValueError(f"state event on branch {branch!r} occurs before its fork point")
            con.execute(
                '''INSERT INTO state_event(branch_id,at_key,ordinal,seq,subject,state_key,op,value_json,writer_safe,source)
                   VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (branch, at, timeline[at], int(ev.get('seq', 0)), str(ev['subject']), str(ev['key']),
                 str(ev.get('op', 'set')), _json(ev.get('value')), 1 if ev.get('writer_safe', False) else 0,
                 ev.get('source')),
            )
        seen: set[str] = set()
        for inv in invariants:
            iid = str(inv['id'])
            if iid in seen:
                raise ValueError(f'duplicate state invariant id {iid}')
            seen.add(iid)
            af = inv.get('active_from')
            at = inv.get('active_to')
            if af is not None and str(af) not in timeline:
                raise ValueError(f"invariant {iid}: unknown active_from {af!r}")
            if at is not None and str(at) not in timeline:
                raise ValueError(f"invariant {iid}: unknown active_to {at!r}")
            con.execute(
                '''INSERT INTO state_invariant(id,branch_pattern,subject_pattern,state_key,op,value_json,active_from_ordinal,
                                               active_to_ordinal,severity,writer_safe,message)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                (iid, str(inv.get('branch','*')), str(inv.get('subject', '*')), str(inv['key']), str(inv['op']), _json(inv.get('value')),
                 timeline[str(af)] if af is not None else None, timeline[str(at)] if at is not None else None,
                 str(inv.get('severity', 'hard')), 1 if inv.get('writer_safe', False) else 0, inv.get('message')),
            )
        con.commit()
        if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('state SQLite integrity check failed')
    except Exception:
        con.close(); tmp.unlink(missing_ok=True); raise
    else:
        con.close(); output.unlink(missing_ok=True); tmp.replace(output)
    return output


def _contains(container: Any, value: Any) -> bool:
    if isinstance(container, (list, tuple, set, str, dict)):
        try:
            return value in container
        except TypeError:
            return False
    return False


def condition_holds(state: dict[str, dict[str, Any]], subject: str, key: str, op: str, value: Any = None) -> bool:
    exists = subject in state and key in state[subject]
    current = state.get(subject, {}).get(key)
    if op == 'exists': return exists
    if op == 'not_exists': return not exists
    if op == 'eq': return exists and current == value
    if op == 'neq': return (not exists) or current != value
    if op == 'contains': return exists and _contains(current, value)
    if op == 'not_contains': return (not exists) or not _contains(current, value)
    try:
        if op == 'gte': return exists and current >= value
        if op == 'lte': return exists and current <= value
        if op == 'gt': return exists and current > value
        if op == 'lt': return exists and current < value
    except TypeError:
        return False
    raise ValueError(f'unknown state condition op {op!r}')


def apply_effect(state: dict[str, dict[str, Any]], subject: str, key: str, op: str, value: Any = None) -> None:
    bucket = state.setdefault(subject, {})
    if op == 'set': bucket[key] = value; return
    if op == 'unset': bucket.pop(key, None); return
    if op == 'add':
        cur = bucket.setdefault(key, [])
        if not isinstance(cur, list):
            raise TypeError(f'{subject}.{key} is not a list; cannot add')
        if value not in cur: cur.append(value)
        return
    if op == 'remove':
        cur = bucket.get(key, [])
        if isinstance(cur, list) and value in cur: cur.remove(value)
        return
    if op in {'inc','dec'}:
        cur = bucket.get(key, 0)
        if not isinstance(cur, (int, float)) or not isinstance(value, (int, float)):
            raise TypeError(f'{subject}.{key} is not numeric; cannot {op}')
        bucket[key] = cur + value if op == 'inc' else cur - value
        return
    raise ValueError(f'unknown state effect op {op!r}')


class StoryStateLibrary:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists(): raise FileNotFoundError(self.path)
        self.con = sqlite3.connect(self.path)
        self.con.row_factory = sqlite3.Row
        row = self.con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if not row or int(row[0]) != STATE_SCHEMA_VERSION:
            raise ValueError(f'unsupported story-state schema in {self.path}')

    @classmethod
    def load(cls, path: str | Path) -> 'StoryStateLibrary': return cls(path)
    def close(self) -> None: self.con.close()
    def __enter__(self): return self
    def __exit__(self, *_exc): self.close()

    def subject_registry(self, *, writer_safe_only: bool = False) -> dict[str, dict[str, Any]]:
        sql = 'SELECT id,kind,writer_safe,metadata_json FROM subject_registry'
        if writer_safe_only:
            sql += ' WHERE writer_safe=1'
        sql += ' ORDER BY id'
        out: dict[str, dict[str, Any]] = {}
        for row in self.con.execute(sql):
            meta = json.loads(row['metadata_json']) if row['metadata_json'] else {}
            out[row['id']] = {'kind': row['kind'], 'writer_safe': bool(row['writer_safe']), **meta}
        return out

    def branches(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.con.execute(
            'SELECT id,parent_id,fork_at_key,fork_ordinal,kind,label,writer_safe FROM timeline_branch ORDER BY id'
        )]

    def branch_exists(self, branch: str) -> bool:
        return bool(self.con.execute('SELECT 1 FROM timeline_branch WHERE id=?',(branch,)).fetchone())

    def _branch_windows(self, branch: str, ordinal: int) -> list[tuple[str,int|None,int]]:
        lineage=branch_lineage(self.con,branch)
        out=[]
        for i,b in enumerate(lineage):
            start=b.fork_ordinal
            if start is not None and ordinal < int(start):
                continue
            ceiling=ordinal if i==len(lineage)-1 else min(ordinal,int(lineage[i+1].fork_ordinal))
            out.append((b.id,start,ceiling))
        if not out:
            out=[('main',None,ordinal)]
        return out

    def state_at(self, ordinal: int, *, branch: str = 'main', writer_safe_only: bool = False) -> dict[str, dict[str, Any]]:
        windows=self._branch_windows(branch,int(ordinal))
        state: dict[str, dict[str, Any]] = {}
        for bid,start,ceiling in windows:
            sql='SELECT subject,state_key,op,value_json FROM state_event WHERE branch_id=? AND ordinal<=?'
            params: list[Any]=[bid,int(ceiling)]
            if start is not None:
                sql += ' AND ordinal>=?'; params.append(int(start))
            if writer_safe_only:
                sql += ' AND writer_safe=1'
            sql += ' ORDER BY ordinal,seq,id'
            for row in self.con.execute(sql,params):
                apply_effect(state,row['subject'],row['state_key'],row['op'],
                             json.loads(row['value_json']) if row['value_json'] is not None else None)
        return state

    def history(self, *, branch: str = 'main', through_ordinal: int, subject: str | None = None,
                writer_safe_only: bool = False) -> list[dict[str, Any]]:
        out=[]
        for bid,start,ceiling in self._branch_windows(branch,int(through_ordinal)):
            sql='SELECT * FROM state_event WHERE branch_id=? AND ordinal<=?'
            params: list[Any]=[bid,int(ceiling)]
            if start is not None:
                sql += ' AND ordinal>=?'; params.append(int(start))
            if subject is not None:
                sql += ' AND subject=?'; params.append(subject)
            if writer_safe_only: sql += ' AND writer_safe=1'
            sql += ' ORDER BY ordinal,seq,id'
            for r in self.con.execute(sql,params):
                d=dict(r); raw=d.pop('value_json'); d['value']=json.loads(raw) if raw is not None else None
                out.append(d)
        return out

    def diff(self, *, left_branch: str, right_branch: str, ordinal: int) -> dict[str, Any]:
        left=self.state_at(ordinal,branch=left_branch)
        right=self.state_at(ordinal,branch=right_branch)
        changes=[]
        for subject in sorted(set(left)|set(right)):
            keys=set(left.get(subject,{}))|set(right.get(subject,{}))
            for key in sorted(keys):
                lv=left.get(subject,{}).get(key); rv=right.get(subject,{}).get(key)
                if lv != rv:
                    changes.append({'subject':subject,'key':key,'left':lv,'right':rv})
        return {'left_branch':left_branch,'right_branch':right_branch,'ordinal':int(ordinal),'changes':changes}

    def active_invariants(self, ordinal: int, *, branch: str = 'main', writer_safe_only: bool = False) -> list[dict[str, Any]]:
        sql = '''SELECT * FROM state_invariant
                 WHERE (active_from_ordinal IS NULL OR active_from_ordinal<=?)
                   AND (active_to_ordinal IS NULL OR ?<active_to_ordinal)'''
        params: list[Any] = [int(ordinal), int(ordinal)]
        if writer_safe_only: sql += ' AND writer_safe=1'
        sql += ' ORDER BY id'
        rows = self.con.execute(sql, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if not fnmatch.fnmatch(branch, str(d.get('branch_pattern','*'))):
                continue
            raw=d.pop('value_json')
            d['value'] = json.loads(raw) if raw is not None else None
            out.append(d)
        return out

    def check_invariants(self, state: dict[str, dict[str, Any]], ordinal: int, *, branch: str = 'main', path: str | None = None) -> list[StateIssue]:
        issues: list[StateIssue] = []
        for inv in self.active_invariants(ordinal, branch=branch):
            subjects = sorted(s for s in state if fnmatch.fnmatch(s, inv['subject_pattern']))
            if not subjects and '*' not in inv['subject_pattern']:
                subjects = [inv['subject_pattern']]
            for subject in subjects:
                if condition_holds(state, subject, inv['state_key'], inv['op'], inv['value']):
                    continue
                msg = inv['message'] or f"state invariant {inv['id']} failed for {subject}.{inv['state_key']}"
                issues.append(StateIssue('state.invariant', inv['severity'], subject, inv['state_key'], msg,
                                         invariant_id=inv['id'], path=path,
                                         evidence={'op': inv['op'], 'expected': inv['value'],
                                                   'actual': state.get(subject, {}).get(inv['state_key'])}))
        return issues
