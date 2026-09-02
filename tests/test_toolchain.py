import json
from pathlib import Path
from writing_runtime.toolchain import verify_lock, write_lock


def test_tool_lock_detects_configuration_drift(tmp_path):
    (tmp_path / 'config').mkdir()
    (tmp_path / 'package.json').write_text('{"dependencies": {}}', encoding='utf-8')
    (tmp_path / 'cspell.json').write_text('{"version":"0.2"}', encoding='utf-8')
    lock = tmp_path / 'config' / 'toolchain.lock.json'
    write_lock(tmp_path, lock)
    assert verify_lock(tmp_path, lock)['ok']
    (tmp_path / 'cspell.json').write_text('{"version":"changed"}', encoding='utf-8')
    assert not verify_lock(tmp_path, lock)['ok']
