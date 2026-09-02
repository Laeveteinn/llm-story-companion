import json
import subprocess
from pathlib import Path

import writing_runtime.external_tools as et


def test_languagetool_json_adapter(monkeypatch, tmp_path):
    jar = tmp_path / 'languagetool-commandline.jar'; jar.write_bytes(b'x')
    text = 'This is is wrong.'
    payload = {
        'software': {'version': 'frozen-test'},
        'matches': [{
            'message': 'Possible typo: you repeated a word',
            'offset': 5, 'length': 5,
            'replacements': [{'value': 'is'}],
            'rule': {'id': 'ENGLISH_WORD_REPEAT_RULE', 'issueType': 'duplication',
                     'category': {'id': 'MISC', 'name': 'Miscellaneous'}},
        }],
    }
    monkeypatch.setattr(et, 'find_languagetool_jar', lambda root: jar)
    monkeypatch.setattr(et.shutil, 'which', lambda name: '/usr/bin/java' if name == 'java' else None)
    monkeypatch.setattr(et, '_run', lambda *a, **k: subprocess.CompletedProcess(a[0], 0, json.dumps(payload), ''))
    issues, status = et.run_languagetool(tmp_path / 'x.txt', tmp_path, text)
    assert status.available
    assert issues[0].code == 'languagetool.ENGLISH_WORD_REPEAT_RULE'
    assert issues[0].family == 'repetition'
    assert issues[0].paragraph == 1


def test_plain_english_json_adapter(monkeypatch, tmp_path):
    text = 'Moreover, this sentence is suspiciously polished.\n\nAnother paragraph.'
    payload = {
        'errorCount': 1, 'warnCount': 0,
        'files': [{'file': 'x.txt', 'findings': [{
            'severity': 'error', 'line': 1, 'column': 1,
            'match': 'Moreover', 'ruleId': 'stock-transition',
            'message': 'Stock transition phrase'
        }]}],
    }
    monkeypatch.setattr(et, '_local_bin', lambda root, name: '/tmp/plain-english' if name == 'plain-english' else None)
    monkeypatch.setattr(et, '_run', lambda *a, **k: subprocess.CompletedProcess(a[0], 0, json.dumps(payload), ''))
    issues, status = et.run_plain_english(tmp_path / 'x.txt', tmp_path, text)
    assert status.available
    assert issues[0].code == 'plain-english.stock-transition'
    assert issues[0].family == 'ai_style'
    assert issues[0].paragraph == 1
    assert not issues[0].hard


def test_slopless_textlint_json_adapter(monkeypatch, tmp_path):
    text = 'Let me be honest: everyone knows the future belongs to us.'
    payload = [{
        'filePath': 'x.txt',
        'messages': [{
            'ruleId': 'slopless/boilerplate-framing', 'severity': 2,
            'message': 'Boilerplate framing', 'line': 1, 'column': 1,
            'endLine': 1, 'endColumn': 17,
        }],
        'errorCount': 1, 'warningCount': 0,
    }]
    monkeypatch.setattr(et, '_local_bin', lambda root, name: '/tmp/slopless' if name == 'slopless' else None)
    monkeypatch.setattr(et, '_run', lambda *a, **k: subprocess.CompletedProcess(a[0], 1, json.dumps(payload), ''))
    issues, status = et.run_slopless(tmp_path / 'x.txt', tmp_path, text)
    assert status.available
    assert issues[0].code == 'slopless.boilerplate-framing'
    assert issues[0].family == 'ai_style'
    assert issues[0].paragraph == 1
    assert not issues[0].hard
