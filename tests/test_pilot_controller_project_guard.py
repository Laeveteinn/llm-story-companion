from __future__ import annotations

from integrations.hermes import pilot_controller


def test_named_project_brief_refuses_root_fixture_defaults(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pilot_controller, 'ROOT', tmp_path)
    brief = tmp_path / 'projects' / 'story' / 'brief.txt'
    brief.parent.mkdir(parents=True)
    brief.write_text('Own story.\n', encoding='utf-8')
    (tmp_path / 'canon_source').mkdir()
    (tmp_path / 'state_source').mkdir()

    rc = pilot_controller.main([
        str(brief),
        '--plan-id', 'story.book1.ch01',
        '--chapter-key', 'book1/ch01',
        '--at', 'book1/ch01',
        '--viewpoint', 'Iri',
        '--skip-setup',
    ])
    assert rc == 2
    assert 'cannot use root fixture canon/state defaults' in capsys.readouterr().err
