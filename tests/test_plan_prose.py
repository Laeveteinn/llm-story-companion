from pathlib import Path
from writing_runtime.canon import build_canon_database
from writing_runtime.quality import QualityGate, load_policy

ROOT=Path(__file__).parents[1]

def test_plan_prose_literal_obligations_are_hard(tmp_path):
    canon=tmp_path/'canon.sqlite3'; build_canon_database(ROOT/'canon_source',canon)
    import json
    data=json.loads((ROOT/'plans/example.json').read_text())
    data['scenes'][0]['target_words_min']=None; data['scenes'][0]['target_words_max']=None
    data['scenes'][0]['beats'][0]['required_terms']=['north hall']
    data['scenes'][0]['beats'][1]['forbidden_terms']=['cheese tornado']
    plan=tmp_path/'plan.json'; plan.write_text(json.dumps(data))
    gate=QualityGate(root=ROOT,policy=load_policy(ROOT/'config/gate_policy.yaml'))
    report=gate.analyze('Mara crossed the corridor. A cheese tornado appeared.',canon_library=canon,viewpoint='Mara',at='book1/ch05',chapter_plan=plan,external=False,advanced_nlp=False)
    codes={i.code for i in report.issues}
    assert 'plan.prose_missing_required_term' in codes
    assert 'plan.prose_forbidden_term' in codes
    assert report.hard_failures >= 2
    assert not report.passed


def test_hash_bound_provenance_attaches_scene_and_beat_to_findings(tmp_path):
    import json
    from writing_runtime.story_state import build_state_database
    from writing_runtime.planning import load_plan, validate_scene_draft
    canon=tmp_path/'canon.sqlite3'; state=tmp_path/'state.sqlite3'
    build_canon_database(ROOT/'canon_source',canon); build_state_database(ROOT/'state_source',canon,state)
    plan=load_plan(ROOT/'plans/example.json').model_copy(deep=True)
    plan.scenes[0].target_words_min=None; plan.scenes[0].target_words_max=None
    cid='abcdef1234567890abcd'
    cheese=' '.join(['fromage']*20)
    response=(f'<<<WRITING_RUNTIME_SCENE S01 {cid}>>>\n'
              f'<<<WRITING_RUNTIME_BEAT B001 {cid}>>>\nMara crossed the north hall.\n<<<END_WRITING_RUNTIME_BEAT B001>>>\n'
              f'<<<WRITING_RUNTIME_BEAT B002 {cid}>>>\n{cheese}\n<<<END_WRITING_RUNTIME_BEAT B002>>>\n'
              f'<<<WRITING_RUNTIME_BEAT B003 {cid}>>>\nShe left uncertain.\n<<<END_WRITING_RUNTIME_BEAT B003>>>\n'
              '<<<END_WRITING_RUNTIME_SCENE S01>>>')
    chapter,result=validate_scene_draft(plan,response,contract_id=cid,canon_library=canon)
    assert result['valid'] and chapter
    prov=tmp_path/'prov.json'; prov.write_text(json.dumps(result['provenance']))
    gate=QualityGate(root=ROOT,policy=load_policy(ROOT/'config/gate_policy.yaml'))
    report=gate.analyze(chapter,canon_library=canon,viewpoint='Mara',at='book1/ch05',external=False,advanced_nlp=False,provenance_path=prov)
    bursts=[i for i in report.issues if i.code=='lexical.word_burst']
    assert bursts and bursts[0].evidence['scene_id']=='S01' and bursts[0].evidence['beat_id']=='B002'
