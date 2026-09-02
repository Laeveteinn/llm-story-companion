from __future__ import annotations

import json
from pathlib import Path

from writing_runtime.canon import build_canon_database
from writing_runtime.story_state import build_state_database, StoryStateLibrary
from writing_runtime.planning import (
    ChapterPlan, PlanGate, load_plan, make_plan_salvage, plan_salvage_prompt,
    apply_plan_salvage, writer_plan_surface, validate_scene_draft,
)

ROOT=Path(__file__).parents[1]


def libs(tmp_path):
    canon=tmp_path/'canon.sqlite3'; state=tmp_path/'state.sqlite3'
    build_canon_database(ROOT/'canon_source',canon)
    build_state_database(ROOT/'state_source',canon,state)
    return canon,state


def policy():
    import yaml
    return yaml.safe_load((ROOT/'config/planning_policy.yaml').read_text())


def test_story_state_replay(tmp_path):
    canon,state=libs(tmp_path)
    from writing_runtime.canon import CanonLibrary
    with CanonLibrary.load(canon) as c: ord_=c.timeline_ordinal('book1/ch05')
    with StoryStateLibrary.load(state) as s:
        snap=s.state_at(ord_)
    assert snap['Mara']['location']=='north_hall'
    assert 'knife' in snap['Mara']['inventory']


def test_valid_plan_and_writer_firewall(tmp_path):
    canon,state=libs(tmp_path); plan=load_plan(ROOT/'plans/example.json')
    report=PlanGate(policy()).validate(plan,canon_library=canon,state_library=state)
    assert report.passed, report.as_dict()
    surface=writer_plan_surface(plan,canon_library=canon,state_library=state)
    text=json.dumps(surface,ensure_ascii=False).lower()
    assert 'author_intent' not in text
    assert 'd20 + 5' not in text
    assert 'resistance is contested' not in text
    assert 'knife' in text


def test_plan_secret_leak_is_hard(tmp_path):
    canon,state=libs(tmp_path); plan=load_plan(ROOT/'plans/example.json').model_copy(deep=True)
    plan.scenes[0].beats[1].writer_directive='Explain that resistance is contested and uses d20 + 5.'
    report=PlanGate(policy()).validate(plan,canon_library=canon,state_library=state)
    assert not report.passed
    assert any(i.code=='plan.writer_secret_leak' and i.hard for i in report.issues)


def test_unauthorized_reveal_is_hard(tmp_path):
    canon,state=libs(tmp_path); plan=load_plan(ROOT/'plans/example.json').model_copy(deep=True)
    plan.scenes[0].beats[1].reveal_facts=['ability.sable_bind::resistance_model']
    report=PlanGate(policy()).validate(plan,canon_library=canon,state_library=state)
    assert any(i.code=='plan.unauthorized_reveal' for i in report.issues)


def test_state_precondition_and_dependency_cycle(tmp_path):
    canon,state=libs(tmp_path); plan=load_plan(ROOT/'plans/example.json').model_copy(deep=True)
    plan.scenes[0].beats[0].preconditions[0].value='moon'
    plan.scenes[0].beats[0].depends_on=['B003']
    report=PlanGate(policy()).validate(plan,canon_library=canon,state_library=state)
    codes={i.code for i in report.issues}
    assert 'plan.precondition_unsatisfied' in codes
    assert 'plan.beat_dependency.cycle' in codes


def test_plan_salvage_is_local_and_request_bound(tmp_path):
    canon,state=libs(tmp_path); plan=load_plan(ROOT/'plans/example.json').model_copy(deep=True)
    plan.scenes[0].beats[1].writer_directive='Explain that resistance is contested and uses d20 + 5.'
    report=PlanGate(policy()).validate(plan,canon_library=canon,state_library=state)
    salvage=make_plan_salvage(plan,report,policy())
    assert not salvage.abort
    prompt=plan_salvage_prompt(salvage)
    # Exact protected phrase is intentionally not echoed by deterministic directive text.
    assert 'd20 + 5' in prompt  # present only in removed author-side plan context, never a writer packet
    gap=salvage.gaps[0]
    replacement=[]
    for raw in gap.removed_beats:
        b=dict(raw)
        if b['id']=='B002': b['writer_directive']='Show only the already-known visible restraint effect and leave the reason uncertain.'
        replacement.append(b)
    response=(f'<<<WRITING_RUNTIME_PLAN_GAP {gap.id} {salvage.contract_id}>>>\n'
              +json.dumps(replacement,ensure_ascii=False)+'\n'
              +f'<<<END_WRITING_RUNTIME_PLAN_GAP {gap.id}>>>')
    rebuilt,result=apply_plan_salvage(plan,salvage,response)
    assert result['valid'] and rebuilt is not None
    report2=PlanGate(policy()).validate(rebuilt,canon_library=canon,state_library=state)
    assert report2.passed, report2.as_dict()


def test_scene_draft_contract_and_required_terms(tmp_path):
    canon,state=libs(tmp_path); plan=load_plan(ROOT/'plans/example.json').model_copy(deep=True)
    plan.scenes[0].target_words_min=None; plan.scenes[0].target_words_max=None
    plan.scenes[0].beats[0].required_terms=['north hall']
    cid='abcdef1234567890abcd'
    response=(f'<<<WRITING_RUNTIME_SCENE S01 {cid}>>>\n'
              f'<<<WRITING_RUNTIME_BEAT B001 {cid}>>>\nMara crossed the north hall with the knife tucked close.\n<<<END_WRITING_RUNTIME_BEAT B001>>>\n'
              f'<<<WRITING_RUNTIME_BEAT B002 {cid}>>>\nShe tested Sable Bind against movement, seeing only that it could restrain a moving target when it caught.\n<<<END_WRITING_RUNTIME_BEAT B002>>>\n'
              f'<<<WRITING_RUNTIME_BEAT B003 {cid}>>>\nThe reason it sometimes failed remained uncertain.\n<<<END_WRITING_RUNTIME_BEAT B003>>>\n'
              '<<<END_WRITING_RUNTIME_SCENE S01>>>')
    chapter,result=validate_scene_draft(plan,response,contract_id=cid,canon_library=canon)
    assert result['valid'], result
    assert 'WRITING_RUNTIME' not in chapter
    assert result['provenance']['scenes'][0]['beats'][0]['beat_id']=='B001'



def test_chapter_and_scene_writer_goals_are_disclosure_firewalled(tmp_path):
    canon,state=libs(tmp_path); plan=load_plan(ROOT/'plans/example.json').model_copy(deep=True)
    plan.writer_goal='Mara learns that resistance is contested.'
    plan.scenes[0].writer_goal='Frame the d20 + 5 rule as a revelation.'
    report=PlanGate(policy()).validate(plan,canon_library=canon,state_library=state)
    leaks=[i for i in report.issues if i.code=='plan.writer_secret_leak']
    assert len(leaks) >= 2
    assert all(i.hard for i in leaks)


def test_plan_smells_forward_scene_duplicate_directive_and_missing_viewpoint(tmp_path):
    canon,state=libs(tmp_path); plan=load_plan(ROOT/'plans/example.json').model_copy(deep=True)
    from writing_runtime.planning import Scene
    first=plan.scenes[0]
    first.participants=[]
    duplicate=first.model_copy(deep=True)
    duplicate.id='S02'
    duplicate.depends_on=[]
    duplicate.beats[0].id='B004'; duplicate.beats[1].id='B005'; duplicate.beats[2].id='B006'
    duplicate.beats[0].depends_on=[]; duplicate.beats[1].depends_on=['B004']; duplicate.beats[2].depends_on=['B005']
    duplicate.beats[0].writer_directive=first.beats[0].writer_directive
    first.depends_on=['S02']
    plan.scenes.append(duplicate)
    report=PlanGate(policy()).validate(plan,canon_library=canon,state_library=state)
    codes={i.code for i in report.issues}
    assert 'plan.scene_dependency.forward_reference' in codes
    assert 'plan.viewpoint_absent' in codes
    assert 'plan.duplicate_beat_directive' in codes


def test_plan_prompt_can_receive_author_truth_but_writer_surface_cannot(tmp_path):
    canon,state=libs(tmp_path)
    from writing_runtime.canon import CanonLibrary
    from writing_runtime.planning import plan_generation_prompt
    brief='Plan a Sable Bind test while preserving partial revelation.'
    with CanonLibrary.load(canon) as c:
        ord_=c.timeline_ordinal('book1/ch05')
        hits=c.trigger(brief,viewpoint='Mara',at='book1/ch05',scope='writer')
        author=[{'id':h.id,'payload':h.payload} for h in hits]
    with StoryStateLibrary.load(state) as ss:
        snap=ss.state_at(ord_,writer_safe_only=False)
    prompt=plan_generation_prompt(brief=brief,plan_id='x',chapter_key='book1/ch05',timeline_key='book1/ch05',viewpoint='Mara',contract_id='abc',canon_inventory=[],author_canon_context=author,author_state=snap)
    assert 'd20 + 5' in prompt  # architect receives author truth
    surface=writer_plan_surface(load_plan(ROOT/'plans/example.json'),canon_library=canon,state_library=state)
    assert 'd20 + 5' not in json.dumps(surface,ensure_ascii=False)


def test_nonlocal_plan_failure_gets_one_bounded_full_recompile(tmp_path):
    canon,state=libs(tmp_path); plan=load_plan(ROOT/'plans/example.json').model_copy(deep=True)
    plan.writer_goal='Explain that resistance is contested.'
    report=PlanGate(policy()).validate(plan,canon_library=canon,state_library=state)
    from writing_runtime.planning import plan_repair_transition, plan_rewrite_prompt
    st=plan_repair_transition(None,report,plan,policy())
    assert st['action']=='rewrite_plan'
    prompt=plan_rewrite_prompt(plan,report,contract_id='abc123abc123abc123ab')
    assert 'DETERMINISTIC REPAIR DIRECTIVES' in prompt
    assert 'writer-facing planning' in prompt or 'premature disclosure' in prompt
    # Same unchanged failure consumes the only full-plan recompile budget and stops.
    st2=plan_repair_transition(st,report,plan,policy())
    assert st2['action']=='human_review'
