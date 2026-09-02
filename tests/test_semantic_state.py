from pathlib import Path
import copy, json

from writing_runtime.canon import build_canon_database
from writing_runtime.story_state import build_state_database, StoryStateLibrary
from writing_runtime.semantic import SemanticAction, apply_semantic_action, audit_semantic_state
from writing_runtime.planning import ChapterPlan, PlanGate

ROOT = Path(__file__).parents[1]


def _libs(tmp_path):
    canon = tmp_path/'canon.sqlite3'
    state = tmp_path/'state.sqlite3'
    build_canon_database(ROOT/'canon_source', canon)
    build_state_database(ROOT/'state_source', canon, state)
    return canon, state


def test_subject_registry_and_semantic_transfer(tmp_path):
    canon, state_path = _libs(tmp_path)
    with StoryStateLibrary.load(state_path) as lib:
        state = lib.state_at(1000005)
        registry = lib.subject_registry()
    assert registry['Mara']['kind'] == 'character'
    registry['Ilya'] = {'kind':'character'}
    state['Ilya'] = {'location':'north_hall','inventory':[],'alive':True}
    issues = apply_semantic_action(state, SemanticAction(kind='transfer', source='Mara', destination='Ilya', item='knife'), registry=registry)
    assert not [x for x in issues if x.hard]
    assert 'knife' not in state['Mara']['inventory']
    assert 'knife' in state['Ilya']['inventory']
    assert state['knife']['owner'] == 'Ilya'
    assert not [x for x in audit_semantic_state(state, registry=registry) if x.hard]


def test_semantic_resource_underflow_is_hard(tmp_path):
    canon, state_path = _libs(tmp_path)
    with StoryStateLibrary.load(state_path) as lib:
        state = lib.state_at(1000005)
        registry = lib.subject_registry()
    issues = apply_semantic_action(state, SemanticAction(kind='spend_resource', actor='Mara', resource='focus', amount=4), registry=registry)
    assert any(x.code == 'semantic.resource_underflow' and x.hard for x in issues)
    assert state['Mara']['resource:focus'] == 3


def test_plan_gate_executes_semantic_actions(tmp_path):
    canon, state_path = _libs(tmp_path)
    data = json.loads((ROOT/'plans/example.json').read_text())
    data['scenes'][0]['beats'][1]['semantic_actions'] = [
        {'kind':'spend_resource','actor':'Mara','resource':'focus','amount':1}
    ]
    plan = ChapterPlan.model_validate(data)
    report = PlanGate({}).validate(plan, canon_library=canon, state_library=state_path)
    assert report.passed
    assert report.metrics['final_state']['Mara']['resource:focus'] == 2


def test_plan_gate_blocks_semantic_resource_underflow(tmp_path):
    canon, state_path = _libs(tmp_path)
    data = json.loads((ROOT/'plans/example.json').read_text())
    data['scenes'][0]['beats'][1]['semantic_actions'] = [
        {'kind':'spend_resource','actor':'Mara','resource':'focus','amount':99}
    ]
    plan = ChapterPlan.model_validate(data)
    report = PlanGate({}).validate(plan, canon_library=canon, state_library=state_path)
    assert not report.passed
    assert any(x.code == 'semantic.resource_underflow' for x in report.issues)


def test_plan_gate_catches_blocked_dialogue(tmp_path):
    canon, state_path = _libs(tmp_path)
    data = json.loads((ROOT/'plans/example.json').read_text())
    data['scenes'][0]['beats'][0]['semantic_actions'] = [
        {'kind':'disable_capability','target':'Mara','capability':'speak'}
    ]
    data['scenes'][0]['beats'][1]['kind'] = 'dialogue'
    data['scenes'][0]['beats'][1]['actor'] = 'Mara'
    plan = ChapterPlan.model_validate(data)
    report = PlanGate({}).validate(plan, canon_library=canon, state_library=state_path)
    assert not report.passed
    assert any(x.code == 'semantic.blocked_capability' for x in report.issues)


def test_semantic_learn_fact_requires_authorization(tmp_path):
    canon, state_path = _libs(tmp_path)
    data = json.loads((ROOT/'plans/example.json').read_text())
    data['scenes'][0]['beats'][0]['semantic_actions'] = [
        {'kind':'learn_fact','actor':'Mara','fact_ref':'ability.sable_bind::resistance_model'}
    ]
    plan = ChapterPlan.model_validate(data)
    report = PlanGate({}).validate(plan, canon_library=canon, state_library=state_path)
    assert not report.passed
    assert any(x.code == 'semantic.unauthorized_knowledge' for x in report.issues)
