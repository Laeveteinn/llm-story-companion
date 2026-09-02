from __future__ import annotations

import json

from writing_runtime import operator, project_model


def test_project_model_pin_and_operator_args(tmp_path, monkeypatch):
    monkeypatch.setattr(project_model, 'ROOT', tmp_path)
    project = tmp_path / 'projects' / 'story'
    project.mkdir(parents=True)
    config = {
        'brief': 'projects/story/brief.txt',
        'plan_id': 'story.book1.ch01',
        'chapter_key': 'book1/ch01',
        'at': 'book1/ch01',
        'branch': 'main',
        'viewpoint': 'Iri',
        'canon_source': 'projects/story/canon_source',
        'state_source': 'projects/story/state_source',
        'canon_library': 'projects/story/runtime_state/canon.sqlite3',
        'state_library': 'projects/story/runtime_state/story_state.sqlite3',
        'workdir': 'projects/story/runtime_state/pilot-first',
        'out': 'projects/story/manuscript/book1-ch01.txt',
    }
    path = project / 'project.json'
    path.write_text(json.dumps(config), encoding='utf-8')

    assert project_model.main(['story', '--provider', 'custom:writer', '--model', 'writer-model']) == 0
    pinned = json.loads(path.read_text(encoding='utf-8'))
    assert pinned['provider'] == 'custom:writer'
    assert pinned['model'] == 'writer-model'

    args = operator._project_args(tmp_path, 'story')
    assert args[-4:] == ['--provider', 'custom:writer', '--model', 'writer-model']

    assert project_model.main(['story', '--clear']) == 0
    cleared = json.loads(path.read_text(encoding='utf-8'))
    assert 'provider' not in cleared
    assert 'model' not in cleared


def test_operator_rejects_half_model_pin(tmp_path):
    project = tmp_path / 'projects' / 'story'
    project.mkdir(parents=True)
    config = {
        'brief': 'brief.txt', 'plan_id': 'p', 'chapter_key': 'book1/ch01',
        'at': 'book1/ch01', 'branch': 'main', 'viewpoint': 'Iri',
        'canon_source': 'canon', 'state_source': 'state',
        'canon_library': 'canon.sqlite3', 'state_library': 'state.sqlite3',
        'workdir': 'work', 'out': 'out.txt', 'model': 'writer-model',
    }
    (project / 'project.json').write_text(json.dumps(config), encoding='utf-8')

    try:
        operator._project_args(tmp_path, 'story')
    except SystemExit as exc:
        assert 'provider and model must be set together' in str(exc)
    else:
        raise AssertionError('half-configured model pin must fail closed')
