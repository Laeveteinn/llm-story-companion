from __future__ import annotations

import json

from writing_runtime import project_init
from writing_runtime.canon import CanonLibrary
from writing_runtime.story_state import StoryStateLibrary


def test_sparse_project_initializer_builds_isolated_stores(tmp_path, monkeypatch):
    monkeypatch.setattr(project_init, 'ROOT', tmp_path)
    brief = tmp_path / 'brief.txt'
    brief.write_text('A new story with no inherited fixture canon.\n', encoding='utf-8')

    rc = project_init.main([
        str(brief), '--slug', 'my-pilot', '--title', 'My Pilot', '--viewpoint', 'Iri'
    ])
    assert rc == 0

    project = tmp_path / 'projects' / 'my-pilot'
    config = json.loads((project / 'project.json').read_text(encoding='utf-8'))
    assert config['brief'] == 'projects/my-pilot/brief.txt'
    assert config['canon_source'] == 'projects/my-pilot/canon_source'
    assert config['state_source'] == 'projects/my-pilot/state_source'
    assert config['chapter_key'] == 'book1/ch01'
    assert config['viewpoint'] == 'Iri'

    canon_db = project / 'runtime_state' / 'canon.sqlite3'
    state_db = project / 'runtime_state' / 'story_state.sqlite3'
    assert canon_db.is_file()
    assert state_db.is_file()

    canon = CanonLibrary(canon_db)
    ordinal = canon.timeline_ordinal('book1/ch01')
    assert ordinal == 1000001
    state = StoryStateLibrary(state_db)
    assert state.state_at(ordinal, branch='main') == {}
    assert state.subject_registry()['Iri']['kind'] == 'character'


def test_project_initializer_refuses_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(project_init, 'ROOT', tmp_path)
    brief = tmp_path / 'brief.txt'
    brief.write_text('First premise.\n', encoding='utf-8')
    args = [str(brief), '--slug', 'same', '--title', 'Same', '--viewpoint', 'Iri']
    assert project_init.main(args) == 0

    try:
        project_init.main(args)
    except SystemExit as exc:
        assert 'already exists' in str(exc)
    else:
        raise AssertionError('initializer must refuse to replace an existing project without --force')
