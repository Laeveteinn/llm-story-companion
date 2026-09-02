from pathlib import Path

from writing_runtime.canon import build_canon_database
from writing_runtime.quality import QualityGate, load_policy
from writing_runtime.repair import apply_gap_response, make_salvage_plan, repair_state_transition, salvage_prompt
from writing_runtime.contracts import GAP_END_TEMPLATE

ROOT = Path(__file__).parents[1]


def _bad_chapter():
    paras = [
        'Rain threaded the glass while Mara listened to the hall.',
        'The lamps had gone low, but the house remained quiet.',
        'She crossed to the cabinet and checked the latch twice.',
        ('Resistance is a contested roll; resistance is contested, using d20 + 5. '
         + ' '.join(['fromage'] * 20) + '.'),
        'A board creaked beyond the door, close enough to stop her hand.',
        'Mara waited until the footsteps passed beneath the eastern window.',
        'Only then did she let the room breathe again.'
    ]
    return '\n\n'.join(paras)


def _report(tmp_path):
    db = tmp_path / 'canon.sqlite3'
    build_canon_database(ROOT / 'canon_source', db)
    policy = load_policy(ROOT / 'config' / 'gate_policy.yaml')
    report = QualityGate(root=ROOT, policy=policy).analyze(
        _bad_chapter(), canon_library=db, viewpoint='Mara', at='book1/ch05',
        external=False, advanced_nlp=False,
    )
    return report, policy


def test_quality_gate_combines_secret_leaks_and_pathological_burst(tmp_path):
    report, _ = _report(tmp_path)
    secret = [i for i in report.issues if i.code == 'canon.unrevealed_reference']
    bursts = [i for i in report.issues if i.code == 'lexical.word_burst' and i.evidence.get('token') == 'fromage']
    assert report.hard_failures >= 3
    assert secret and bursts
    assert bursts[0].weight >= 7
    assert 4 in report.contaminated_paragraphs
    assert not report.passed


def test_salvage_culls_situation_but_preserves_good_anchors(tmp_path):
    report, policy = _report(tmp_path)
    source = _bad_chapter()
    plan = make_salvage_plan(source, report, policy)
    assert not plan.abort
    assert plan.culled_paragraphs == [3, 4, 5]  # radius=1 repairs the marred situation
    prompt = salvage_prompt(plan)
    assert 'Repair causality, continuity, character intent' in prompt
    assert 'contested roll' not in prompt
    assert '[REDACTED_UNREVEALED_CANON]' in prompt
    assert 'd20 + 5' not in prompt

    gap = plan.gaps[0]
    response = (
        f'<<<WRITING_RUNTIME_GAP {gap.id}>>>\n'
        'Mara checked the latch. A board creaked outside, and she froze until the sound receded.\n'
        f'{GAP_END_TEMPLATE.format(gap_id=gap.id)}'
    )
    rebuilt, contract = apply_gap_response(plan, response)
    assert contract['valid'] and rebuilt
    assert 'Rain threaded the glass' in rebuilt
    assert 'Only then did she let the room breathe again.' in rebuilt
    assert 'fromage' not in rebuilt
    assert 'contested roll' not in rebuilt


def test_repair_loop_is_bounded_and_escalates_on_no_progress(tmp_path):
    report, policy = _report(tmp_path)
    source = _bad_chapter()
    s1 = repair_state_transition(None, report=report, candidate_text=source, policy=policy)
    assert s1['action'] == 'rewrite' and not s1['done']
    s2 = repair_state_transition(s1, report=report, candidate_text=source, policy=policy)
    assert s2['action'] == 'salvage' and not s2['done']
    s3 = repair_state_transition(s2, report=report, candidate_text=source, policy=policy)
    assert s3['action'] == 'human_review' and s3['done']
