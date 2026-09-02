from __future__ import annotations

import json

from writing_runtime import operator


def _config():
    return {
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
        'provider': 'lmstudio',
        'model': 'writer-model',
    }


def test_dead_managed_job_becomes_orphaned(tmp_path, monkeypatch):
    project = tmp_path / 'projects' / 'story'
    project.mkdir(parents=True)
    (project / 'project.json').write_text(json.dumps(_config()), encoding='utf-8')
    job_path, _ = operator._paths(tmp_path, 'story')
    operator._save(job_path, {
        'state': 'running', 'project': 'story', 'run_id': 'r1',
        'worker_pid': 111, 'controller_pid': 222,
    })
    monkeypatch.setattr(operator, '_alive', lambda _pid: False)

    refreshed = operator._refresh(tmp_path, 'story', json.loads(job_path.read_text(encoding='utf-8')))
    assert refreshed['state'] == 'orphaned'
    persisted = json.loads(job_path.read_text(encoding='utf-8'))
    assert persisted['state'] == 'orphaned'


def test_managed_job_does_not_consider_project_files_harness_dirt(tmp_path):
    project = tmp_path / 'projects' / 'story'
    project.mkdir(parents=True)
    (project / 'project.json').write_text(json.dumps(_config()), encoding='utf-8')
    head, dirty = operator._git_state(tmp_path)
    assert head is None
    assert dirty == []


def test_existing_running_job_is_structured_state_not_retry_signal(tmp_path, monkeypatch, capsys):
    project = tmp_path / 'projects' / 'story'
    project.mkdir(parents=True)
    (project / 'project.json').write_text(json.dumps(_config()), encoding='utf-8')
    job_path, _ = operator._paths(tmp_path, 'story')
    operator._save(job_path, {
        'state': 'running', 'project': 'story', 'run_id': 'r1',
        'worker_pid': 111, 'controller_pid': None,
    })
    monkeypatch.setattr(operator, '_alive', lambda _pid: True)

    assert operator._start(tmp_path, 'story', ['--skip-setup'], None, None) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['status'] == 'already_running'
    assert payload['run_id'] == 'r1'
