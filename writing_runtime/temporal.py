from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import sqlite3


@dataclass(frozen=True)
class TimelineBranch:
    id: str
    parent_id: str | None
    fork_at_key: str | None
    fork_ordinal: int | None
    kind: str
    label: str | None = None
    writer_safe: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def branch_map(con: sqlite3.Connection, *, table: str = 'timeline_branch') -> dict[str, TimelineBranch]:
    rows = con.execute(
        f'SELECT id,parent_id,fork_at_key,fork_ordinal,kind,label,writer_safe FROM {table} ORDER BY id'
    ).fetchall()
    out: dict[str, TimelineBranch] = {}
    for r in rows:
        out[str(r['id'])] = TimelineBranch(
            id=str(r['id']),
            parent_id=str(r['parent_id']) if r['parent_id'] is not None else None,
            fork_at_key=str(r['fork_at_key']) if r['fork_at_key'] is not None else None,
            fork_ordinal=int(r['fork_ordinal']) if r['fork_ordinal'] is not None else None,
            kind=str(r['kind']),
            label=str(r['label']) if r['label'] is not None else None,
            writer_safe=bool(r['writer_safe']),
        )
    return out


def branch_lineage(con: sqlite3.Connection, branch_id: str, *, table: str = 'timeline_branch') -> list[TimelineBranch]:
    branches = branch_map(con, table=table)
    if branch_id not in branches:
        raise ValueError(f'unknown timeline branch: {branch_id}')
    lineage: list[TimelineBranch] = []
    seen: set[str] = set()
    current = branches[branch_id]
    while True:
        if current.id in seen:
            raise ValueError(f'timeline branch cycle at {current.id}')
        seen.add(current.id)
        lineage.append(current)
        if current.parent_id is None:
            break
        if current.parent_id not in branches:
            raise ValueError(f'branch {current.id} has unknown parent {current.parent_id}')
        current = branches[current.parent_id]
    lineage.reverse()
    if lineage[0].id != 'main':
        raise ValueError(f'branch {branch_id} does not descend from main')
    return lineage


def branch_visibility(con: sqlite3.Connection, branch_id: str, query_ordinal: int | None,
                      *, table: str = 'timeline_branch') -> list[tuple[str, int | None, int]]:
    """Return (branch_id, max_visible_ordinal, precedence_rank) from root to selected branch.

    An ancestor is visible only through the fork point of its child. The selected branch is visible
    through ``query_ordinal`` (or without a ceiling when querying timeless/current canon). The rank
    increases toward the selected branch and is useful for deterministic override resolution.
    """
    lineage = branch_lineage(con, branch_id, table=table)
    result: list[tuple[str, int | None, int]] = []
    for i, branch in enumerate(lineage):
        if i == len(lineage) - 1:
            ceiling = query_ordinal
        else:
            child = lineage[i + 1]
            if child.fork_ordinal is None:
                raise ValueError(f'non-root branch {child.id} has no fork ordinal')
            ceiling = child.fork_ordinal if query_ordinal is None else min(query_ordinal, child.fork_ordinal)
        result.append((branch.id, ceiling, i))
    return result


def branch_is_visible_at(con: sqlite3.Connection, row_branch: str, selected_branch: str,
                         row_ordinal: int | None, query_ordinal: int | None,
                         *, table: str = 'timeline_branch') -> bool:
    for bid, ceiling, _rank in branch_visibility(con, selected_branch, query_ordinal, table=table):
        if bid != row_branch:
            continue
        if row_ordinal is None or ceiling is None:
            return True
        return row_ordinal <= ceiling
    return False


def validate_branch_definitions(branches: list[dict[str, Any]], timeline: dict[str, int]) -> list[dict[str, Any]]:
    """Normalize branch YAML and reject cycles/invalid forks deterministically."""
    normalized: dict[str, dict[str, Any]] = {
        'main': {
            'id': 'main', 'parent': None, 'fork_at': None, 'fork_ordinal': None,
            'kind': 'canonical', 'label': 'Main timeline', 'writer_safe': True,
        }
    }
    for raw in branches:
        bid = str(raw['id'])
        if bid == 'main':
            # Allow metadata override but never a parent/fork on main.
            if raw.get('parent') not in (None, '') or raw.get('fork_at') not in (None, ''):
                raise ValueError('main timeline branch cannot have parent/fork_at')
            normalized['main'].update({
                'kind': str(raw.get('kind', 'canonical')),
                'label': raw.get('label') or 'Main timeline',
                'writer_safe': bool(raw.get('writer_safe', True)),
            })
            continue
        if bid in normalized:
            raise ValueError(f'duplicate timeline branch {bid}')
        parent = str(raw.get('parent') or 'main')
        fork_at = str(raw['fork_at']) if raw.get('fork_at') is not None else None
        if not fork_at or fork_at not in timeline:
            raise ValueError(f'branch {bid} requires known fork_at timeline point')
        normalized[bid] = {
            'id': bid,
            'parent': parent,
            'fork_at': fork_at,
            'fork_ordinal': int(timeline[fork_at]),
            'kind': str(raw.get('kind', 'alternate')),
            'label': raw.get('label'),
            'writer_safe': bool(raw.get('writer_safe', True)),
        }

    # Parent existence and cycle check independent of declaration order.
    for bid, row in normalized.items():
        parent = row['parent']
        if parent is not None and parent not in normalized:
            raise ValueError(f'branch {bid} has unknown parent {parent}')
    for bid in normalized:
        seen: set[str] = set()
        cur = bid
        while cur is not None:
            if cur in seen:
                raise ValueError(f'timeline branch cycle involving {cur}')
            seen.add(cur)
            parent = normalized[cur]['parent']
            cur = parent
        if 'main' not in seen:
            raise ValueError(f'branch {bid} does not descend from main')

    # A nested branch cannot fork before its parent came into existence.
    for bid, row in normalized.items():
        parent = row['parent']
        if parent and parent != 'main':
            parent_fork = normalized[parent]['fork_ordinal']
            if parent_fork is not None and int(row['fork_ordinal']) < int(parent_fork):
                raise ValueError(f'branch {bid} forks before parent {parent} exists')
    return [normalized[k] for k in sorted(normalized, key=lambda x: (0 if x == 'main' else 1, x))]
