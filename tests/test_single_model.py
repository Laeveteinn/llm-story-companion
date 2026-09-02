from __future__ import annotations

import json
from pathlib import Path

from writing_runtime.canon import build_canon_database
from writing_runtime.cli import main
from writing_runtime.execution import make_call_manifest, verify_prompt_manifest
from writing_runtime.planning import PlanGate, load_plan, plan_rewrite_prompt
from writing_runtime.quality import QualityGate, load_policy
from writing_runtime.reinjection import slice_writer_plan_for_report
from writing_runtime.evidence import GateReport, Issue
from writing_runtime.story_state import build_state_database

ROOT=Path(__file__).parents[1]


def libs(tmp_path):
    canon=tmp_path/'canon.sqlite3'; state=tmp_path/'state.sqlite3'
    build_canon_database(ROOT/'canon_source',canon)
    build_state_database(ROOT/'state_source',canon,state)
    return canon,state


def plan_policy():
    import yaml
    return yaml.safe_load((ROOT/'config/planning_policy.yaml').read_text())


def test_same_model_fresh_call_may_see_author_truth_but_requires_context_discard(tmp_path):
    canon,state=libs(tmp_path); brief=tmp_path/'brief.txt'; brief.write_text('Plan a Sable Bind test while preserving partial revelation.')
    prompt=tmp_path/'plan.prompt'; manifest=tmp_path/'plan.manifest.json'
    rc=main(['plan-prompt',str(brief),'--plan-id','x','--chapter-key','book1/ch05','--at','book1/ch05','--viewpoint','Mara',
             '--library',str(canon),'--state-library',str(state),'--out',str(prompt),'--manifest-out',str(manifest),
             '--context-mode','fresh_call'])
    assert rc==0
    text=prompt.read_text()
    data=json.loads(manifest.read_text())
    assert 'd20 + 5' in text
    assert data['requires_fresh_context'] is True
    assert data['discard_context_after_response'] is True
    assert data['author_only_allowed'] is True
    assert data['isolation_grade']=='strong'


def test_persistent_safe_planning_never_injects_hidden_author_truth(tmp_path):
    canon,state=libs(tmp_path); brief=tmp_path/'brief.txt'; brief.write_text('Plan a Sable Bind test while preserving partial revelation.')
    prompt=tmp_path/'plan.prompt'; manifest=tmp_path/'plan.manifest.json'
    rc=main(['plan-prompt',str(brief),'--plan-id','x','--chapter-key','book1/ch05','--at','book1/ch05','--viewpoint','Mara',
             '--library',str(canon),'--state-library',str(state),'--out',str(prompt),'--manifest-out',str(manifest),
             '--context-mode','persistent_safe'])
    assert rc==0
    text=prompt.read_text().casefold(); data=json.loads(manifest.read_text())
    assert 'd20 + 5' not in text
    assert 'resistance is contested' not in text
    assert data['requires_fresh_context'] is False
    assert data['author_only_allowed'] is False
    assert data['isolation_grade']=='degraded'


def test_persistent_plan_repair_redacts_secret_from_invalid_plan(tmp_path):
    canon,state=libs(tmp_path); plan=load_plan(ROOT/'plans/example.json').model_copy(deep=True)
    plan.scenes[0].beats[1].writer_directive='Explain that resistance is contested and uses d20 + 5.'
    report=PlanGate(plan_policy()).validate(plan,canon_library=canon,state_library=state)
    prompt=plan_rewrite_prompt(plan,report,contract_id='abc123abc123abc123ab',context_mode='persistent_safe')
    assert 'd20 + 5' not in prompt
    assert 'resistance is contested' not in prompt.casefold()
    assert '[REDACTED_UNREVEALED_CANON]' in prompt


def test_plan_language_echo_is_mechanical_evidence(tmp_path):
    canon,state=libs(tmp_path); plan=ROOT/'plans/example.json'
    text=('Mara crosses the north hall with her knife still in her possession and prepares to test Sable Bind.\n\n'
          'Then she pauses, uncertain what the bind can actually prove.')
    gate=QualityGate(root=ROOT,policy=load_policy(ROOT/'config/gate_policy.yaml'))
    report=gate.analyze(text,canon_library=canon,viewpoint='Mara',at='book1/ch05',chapter_plan=plan,external=False,advanced_nlp=False)
    assert any(i.code=='plan.prose_plan_echo' for i in report.issues)


def test_reinjection_plan_slice_only_includes_affected_beat_when_radius_zero(tmp_path):
    canon,state=libs(tmp_path); plan=load_plan(ROOT/'plans/example.json')
    from writing_runtime.planning import writer_plan_surface
    surface=writer_plan_surface(plan,canon_library=canon,state_library=state)
    issue=Issue(code='x',source='runtime',severity='warning',family='test',message='x',paragraph=2,evidence={'scene_id':'S01','beat_id':'B002'})
    report=GateReport(False,0,1,24,[issue],{2:1},[2],{},[],[])
    sliced=slice_writer_plan_for_report(surface,report,beat_radius=0)
    assert sliced is not None
    assert [b['id'] for b in sliced['scenes'][0]['beats']]==['B002']


def test_call_manifest_is_hash_bound():
    prompt='hello deterministic world'
    manifest=make_call_manifest(phase='draft_generate',prompt=prompt,context_mode='fresh_call').as_dict()
    assert verify_prompt_manifest(prompt,manifest)['ok'] is True
    assert verify_prompt_manifest(prompt+'!',manifest)['ok'] is False


def _chapter_nine_reveal_plan():
    plan=load_plan(ROOT/'plans/example.json').model_copy(deep=True)
    plan.plan_id='book1.ch09.epoch-test'
    plan.chapter_key='book1/ch09'; plan.timeline_key='book1/ch09'
    plan.scenes[0].beats[1].kind='reveal'
    plan.scenes[0].beats[1].writer_directive='Mara discovers that resistance is contested rather than fixed and recognizes the contested roll as a real rule.'
    plan.scenes[0].beats[1].reveal_facts=['ability.sable_bind::resistance_model']
    return plan


def test_plan_gate_catches_future_reveal_priming_before_reveal_beat(tmp_path):
    canon,state=libs(tmp_path); plan=_chapter_nine_reveal_plan()
    plan.scenes[0].beats[0].writer_directive='Before testing the bind, Mara wonders whether it uses a contested roll.'
    report=PlanGate(plan_policy()).validate(plan,canon_library=canon,state_library=state)
    assert any(i.code=='plan.future_reveal_priming' and i.beat_id=='B001' for i in report.issues)
    assert report.passed is False


def test_disclosure_epochs_withhold_future_fact_until_reveal(tmp_path):
    from writing_runtime.planning import compile_disclosure_epochs, epoch_draft_prompt
    canon,state=libs(tmp_path); plan=_chapter_nine_reveal_plan()
    report=PlanGate(plan_policy()).validate(plan,canon_library=canon,state_library=state)
    assert report.passed is True, report.as_dict()
    epochs=compile_disclosure_epochs(plan,canon_library=canon,state_library=state)
    assert len(epochs)==2
    assert epochs[0].scene_beats==(('S01',('B001',)),)
    assert epochs[1].scene_beats==(('S01',('B002','B003')),)
    early=epoch_draft_prompt(epochs[0],contract_id='a'*20).casefold()
    late=epoch_draft_prompt(epochs[1],contract_id='b'*20).casefold()
    assert 'd20 + 5' not in early
    assert 'resistance is contested' not in early
    assert 'contested roll' not in early
    assert 'ability.sable_bind::resistance_model' not in early
    assert 'resistance is contested' in late
    assert 'ability.sable_bind::resistance_model' in late


def test_epoch_validator_rejects_future_fact_in_early_epoch(tmp_path):
    from writing_runtime.planning import compile_disclosure_epochs, validate_epoch_draft
    canon,state=libs(tmp_path); plan=_chapter_nine_reveal_plan()
    epoch=compile_disclosure_epochs(plan,canon_library=canon,state_library=state)[0]
    cid='c'*20
    response=(f'<<<WRITING_RUNTIME_SCENE S01 {cid}>>>\n'
              f'<<<WRITING_RUNTIME_BEAT B001 {cid}>>>\n'
              'Mara crossed the hall and somehow knew resistance is contested.\n'
              '<<<END_WRITING_RUNTIME_BEAT B001>>>\n'
              '<<<END_WRITING_RUNTIME_SCENE S01>>>')
    beats,result=validate_epoch_draft(plan,epoch,response,contract_id=cid,canon_library=canon)
    assert beats is None
    assert any('later disclosure epoch' in e for e in result['errors'])
