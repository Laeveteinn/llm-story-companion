from pathlib import Path
from writing_runtime.cli import main
ROOT=Path(__file__).parents[1]
def test_gate_runs():
    code=main(['gate',str(ROOT/'examples'/'scene.txt'),'--profile',str(ROOT/'profiles'/'diagnostic_fantasy.yaml'),'--max-warnings','1'])
    assert code==0


def test_salvage_apply_rejects_stale_source(tmp_path, capsys):
    import hashlib, json
    source = tmp_path / 'chapter.txt'; source.write_text('new source\n', encoding='utf-8')
    plan = tmp_path / 'plan.json'
    plan.write_text(json.dumps({
        'source_sha256': hashlib.sha256(b'old source\n').hexdigest(),
        'gaps': [], 'template': 'old source\n', 'culled_paragraphs': [],
        'cull_fraction': 0.0, 'abort': False, 'abort_reason': None,
    }), encoding='utf-8')
    response = tmp_path / 'response.txt'; response.write_text('', encoding='utf-8')
    out = tmp_path / 'out.txt'
    code = main(['salvage-apply', '--plan', str(plan), '--source', str(source),
                 '--response', str(response), '--out', str(out), '--json'])
    assert code == 2
    assert not out.exists()
    assert 'stale' in capsys.readouterr().out.lower()
