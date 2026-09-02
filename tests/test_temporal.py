from __future__ import annotations

import json
from pathlib import Path

from writing_runtime.canon import CanonLibrary, build_canon_database
from writing_runtime.story_state import StoryStateLibrary, build_state_database
from writing_runtime.planning import ChapterPlan, PlanGate, load_plan, writer_plan_surface
from writing_runtime.temporal import validate_branch_definitions

ROOT = Path(__file__).parents[1]
BRANCH = 'retcon.bind_fixed_dc'


def _libs(tmp_path):
    canon = tmp_path / 'canon.sqlite3'
    state = tmp_path / 'state.sqlite3'
    build_canon_database(ROOT / 'canon_source', canon)
    build_state_database(ROOT / 'state_source', canon, state)
    return canon, state


def _policy():
    import yaml
    return yaml.safe_load((ROOT / 'config' / 'planning_policy.yaml').read_text())


def test_child_branch_inherits_parent_only_through_fork(tmp_path):
    canon, state = _libs(tmp_path)
    with CanonLibrary.load(canon) as lib:
        # Main reveals contested resistance only at ch09.
        main = lib.show('ability.sable_bind', viewpoint='Mara', at='book1/ch09', branch='main', scope='pov')
        child = lib.show('ability.sable_bind', viewpoint='Mara', at='book1/ch09', branch=BRANCH, scope='pov')
    main_text = json.dumps(main, ensure_ascii=False).lower()
    child_text = json.dumps(child, ensure_ascii=False).lower()
    assert 'resistance is contested' in main_text
    assert 'fixed at dc 17' in child_text
    # The parent's post-fork ch09 reveal must not leak into the child.
    assert 'resistance is contested' not in child_text


def test_branch_specific_fact_triggers_do_not_cross_timelines(tmp_path):
    canon, _state = _libs(tmp_path)
    with CanonLibrary.load(canon) as lib:
        assert lib.disclosure_audit('The fixed DC 17 is obvious.', viewpoint='Mara', at='book1/ch09', branch='main') == []
        assert lib.disclosure_audit('It is a contested roll.', viewpoint='Mara', at='book1/ch09', branch=BRANCH) == []
        payload_main = lib.fact_payload('ability.sable_bind', 'resistance_model', 'book1/ch09', branch='main')
        payload_child = lib.fact_payload('ability.sable_bind', 'resistance_model', 'book1/ch09', branch=BRANCH)
    assert 'contested' in str(payload_main['value']).lower()
    assert 'fixed dc 17' in str(payload_child['value']).lower()


def test_chronobreak_replays_parent_then_child_state(tmp_path):
    canon, state = _libs(tmp_path)
    with CanonLibrary.load(canon) as c:
        ch05 = c.timeline_ordinal('book1/ch05')
        ch09 = c.timeline_ordinal('book1/ch09')
    with StoryStateLibrary.load(state) as s:
        main = s.state_at(ch09, branch='main')
        child = s.state_at(ch09, branch=BRANCH)
        diff = s.diff(left_branch='main', right_branch=BRANCH, ordinal=ch09)
        history = s.history(branch=BRANCH, through_ordinal=ch09, subject='Mara')
    assert 'knife' in main['Mara']['inventory']
    assert 'knife' not in child['Mara']['inventory']
    assert any(x['subject'] == 'Mara' and x['key'] == 'inventory' for x in diff['changes'])
    # Parent event at the fork plus the branch-local correction are both visible.
    assert any(x['branch_id'] == 'main' and x['ordinal'] == ch05 for x in history)
    assert any(x['branch_id'] == BRANCH and x['ordinal'] == ch05 for x in history)


def test_querying_child_before_its_fork_is_parent_history(tmp_path):
    canon, state = _libs(tmp_path)
    with CanonLibrary.load(canon) as c:
        ch03 = c.timeline_ordinal('book1/ch03')
        main = c.show('ability.sable_bind', viewpoint='Mara', at='book1/ch03', branch='main', scope='pov')
        child = c.show('ability.sable_bind', viewpoint='Mara', at='book1/ch03', branch=BRANCH, scope='pov')
    with StoryStateLibrary.load(state) as s:
        assert s.state_at(ch03, branch='main') == s.state_at(ch03, branch=BRANCH)
    assert main['known_facts'] == child['known_facts']
    assert main['knowledge']['reveals'] == child['knowledge']['reveals']


def test_stale_main_plan_is_rejected_after_chronobreak(tmp_path):
    canon, state = _libs(tmp_path)
    plan = load_plan(ROOT / 'plans' / 'example.json').model_copy(deep=True)
    plan.timeline_branch = BRANCH
    report = PlanGate(_policy()).validate(plan, canon_library=canon, state_library=state)
    assert not report.passed
    assert any(i.code == 'plan.precondition_unsatisfied' and i.beat_id == 'B001' for i in report.issues)


def test_branch_valid_plan_carries_branch_into_writer_surface(tmp_path):
    canon, state = _libs(tmp_path)
    plan = load_plan(ROOT / 'plans' / 'example.json').model_copy(deep=True)
    plan.timeline_branch = BRANCH
    plan.scenes[0].beats[0].writer_directive = 'Mara crosses the north hall and prepares to test Sable Bind.'
    plan.scenes[0].beats[0].preconditions = [p for p in plan.scenes[0].beats[0].preconditions if p.key != 'inventory']
    report = PlanGate(_policy()).validate(plan, canon_library=canon, state_library=state)
    assert report.passed, report.as_dict()
    surface = writer_plan_surface(plan, canon_library=canon, state_library=state)
    assert surface['timeline_branch'] == BRANCH


def test_nested_branch_cannot_fork_before_parent_exists():
    timeline = {'book1/ch03': 3, 'book1/ch05': 5, 'book1/ch09': 9}
    bad = [
        {'id': 'retcon.a', 'parent': 'main', 'fork_at': 'book1/ch05'},
        {'id': 'retcon.b', 'parent': 'retcon.a', 'fork_at': 'book1/ch03'},
    ]
    try:
        validate_branch_definitions(bad, timeline)
    except ValueError as exc:
        assert 'forks before parent' in str(exc)
    else:
        raise AssertionError('nested branch fork before parent should fail')


def test_chronobreak_cli_writes_non_destructive_overlay(tmp_path):
    from writing_runtime.cli import main
    canon, _state = _libs(tmp_path)
    out = tmp_path / 'branch.yaml'
    code = main(['chronobreak', '--id', 'retcon.cli', '--at', 'book1/ch05', '--library', str(canon), '--out', str(out), '--json'])
    assert code == 0
    import yaml
    data = yaml.safe_load(out.read_text())
    row = data['timeline_branches'][0]
    assert row['id'] == 'retcon.cli'
    assert row['parent'] == 'main'
    assert row['fork_at'] == 'book1/ch05'
    # It refuses to mutate/overwrite the source artifact silently.
    assert main(['chronobreak', '--id', 'retcon.cli2', '--at', 'book1/ch05', '--library', str(canon), '--out', str(out)]) == 2


def test_mechanics_are_branch_and_time_versioned(tmp_path):
    canon, _state = _libs(tmp_path)
    with CanonLibrary.load(canon) as lib:
        main = lib.show('ability.sable_bind', viewpoint='Mara', at='book1/ch09', branch='main', scope='writer')
        child = lib.show('ability.sable_bind', viewpoint='Mara', at='book1/ch09', branch=BRANCH, scope='writer')
    assert main['mechanics']['resolution']['defender'] == 'd20'
    assert child['mechanics']['resolution']['target'] == 'DC 17'
    assert 'defender' not in child['mechanics']['resolution']
