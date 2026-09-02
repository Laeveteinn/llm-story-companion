from writing_runtime.contracts import (
    REWRITE_BEGIN, REWRITE_END, GAP_END_TEMPLATE,
    parse_gap_response, validate_rewrite_response,
)


def test_rewrite_contract_accepts_only_prose_payload():
    source = 'Mara crossed the room and shut the door. ' * 20
    response = f'{REWRITE_BEGIN}\n{source}\n{REWRITE_END}'
    result = validate_rewrite_response(response, source_text=source)
    assert result.valid and result.payload


def test_rewrite_contract_rejects_plan_even_inside_sentinels():
    source = 'Mara crossed the room and shut the door. ' * 20
    payload = 'Plan: I will rewrite this chapter carefully. ' + source
    result = validate_rewrite_response(f'{REWRITE_BEGIN}\n{payload}\n{REWRITE_END}', source_text=source)
    assert not result.valid
    assert any('plan/meta-response' in x for x in result.errors)


def test_gap_contract_requires_exact_ids_and_no_commentary():
    ok = (
        '<<<WRITING_RUNTIME_GAP G001>>>\nReplacement one.\n'
        + GAP_END_TEMPLATE.format(gap_id='G001') + '\n'
        + '<<<WRITING_RUNTIME_GAP G002>>>\nReplacement two.\n'
        + GAP_END_TEMPLATE.format(gap_id='G002')
    )
    assert parse_gap_response(ok, ['G001', 'G002']).valid
    bad = 'Here is the plan.\n' + ok
    assert not parse_gap_response(bad, ['G001', 'G002']).valid


def test_gap_contract_rejects_plan_inside_gap():
    response = (
        '<<<WRITING_RUNTIME_GAP G001>>>\n'
        'Plan: I will fix the transition and remove the secret.\n'
        + GAP_END_TEMPLATE.format(gap_id='G001')
    )
    result = parse_gap_response(response, ['G001'])
    assert not result.valid
    assert any('plan/meta-response' in x for x in result.errors)
