from pathlib import Path
import json, os, subprocess, sys

ROOT = Path(__file__).parents[1]
WRAPPER = ROOT/'integrations/hermes/hermes_fresh_call.py'


def test_fresh_call_wrapper_pins_cwd_and_never_resumes(tmp_path):
    fake = tmp_path/'hermes'
    fake.write_text('#!/usr/bin/env python3\nimport os,sys\nprint("CWD="+os.getcwd())\nprint("ARGS="+" ".join(sys.argv[1:-1]))\nprint("RESPONSE")\n', encoding='utf-8')
    fake.chmod(0o755)
    prompt = tmp_path/'p.txt'; prompt.write_text('hello', encoding='utf-8')
    out = tmp_path/'out.txt'
    env={**os.environ,'PATH':str(tmp_path)+os.pathsep+os.environ.get('PATH','')}
    proc=subprocess.run([sys.executable,str(WRAPPER),'--prompt',str(prompt),'--out',str(out),'--project-root',str(ROOT)],env=env,text=True,capture_output=True)
    assert proc.returncode == 0, proc.stderr
    text=out.read_text()
    assert f'CWD={ROOT}' in text
    assert '--ignore-rules' in text
    assert '--resume' not in text and '--continue' not in text
    meta=json.loads((tmp_path/'out.txt.meta.json').read_text())
    assert meta['mode']=='fresh_hermes_process'
    assert meta['session_resume_flags_allowed'] is False


def test_fresh_call_wrapper_rejects_stale_manifest(tmp_path):
    prompt=tmp_path/'p.txt'; prompt.write_text('hello',encoding='utf-8')
    manifest=tmp_path/'m.json'; manifest.write_text(json.dumps({'prompt_sha256':'deadbeef','context_mode':'fresh_call'}))
    proc=subprocess.run([sys.executable,str(WRAPPER),'--prompt',str(prompt),'--out',str(tmp_path/'o.txt'),'--manifest',str(manifest),'--project-root',str(ROOT)],text=True,capture_output=True)
    # Manifest validation occurs before Hermes executable resolution.
    assert proc.returncode == 2
    assert 'does not match prompt bytes' in proc.stderr


def test_temporal_pilot_controller_prepare_only(tmp_path):
    import subprocess, sys, json
    brief = tmp_path / 'brief.txt'
    brief.write_text('Plan a cautious Sable Bind test without revealing hidden resistance rules.\n', encoding='utf-8')
    work = tmp_path / 'pilot'
    ctl = ROOT / 'integrations' / 'hermes' / 'pilot_controller.py'
    proc = subprocess.run([
        sys.executable, str(ctl), str(brief), '--plan-id', 'pilot.test',
        '--chapter-key', 'book1/ch05', '--at', 'book1/ch05',
        '--branch', 'retcon.bind_fixed_dc', '--viewpoint', 'Mara',
        '--workdir', str(work), '--prepare-only', '--skip-setup',
    ], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data['branch'] == 'retcon.bind_fixed_dc'
    prompt = Path(data['plan_prompt'])
    assert prompt.exists()
    assert 'retcon.bind_fixed_dc' in prompt.read_text(encoding='utf-8')
