from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _config(root: Path, slug: str) -> dict:
    path = root / 'projects' / slug / 'project.json'
    if not path.is_file():
        raise SystemExit(f'unknown writing project {slug!r}: {path}')
    data = json.loads(path.read_text(encoding='utf-8'))
    required = {'brief','plan_id','chapter_key','at','branch','viewpoint','canon_source','state_source',
                'canon_library','state_library','workdir','out'}
    missing = sorted(required - set(data))
    if missing:
        raise SystemExit(f'project config is incomplete ({slug}): missing {", ".join(missing)}')
    return data


def _project_args(root: Path, slug: str, *, allow_unpinned: bool = False) -> list[str]:
    c = _config(root, slug)
    provider, model = c.get('provider'), c.get('model')
    if bool(provider) != bool(model):
        raise SystemExit(f'project model pin is incomplete ({slug}): provider and model must be set together')
    if not provider and not allow_unpinned:
        raise SystemExit(
            f'writing project {slug!r} has no pinned Hermes provider/model; refusing mutable Desktop/default state. '
            f'Pin it with: writing-project-model {slug} --provider <provider> --model <model>'
        )
    out = [str(c['brief']), '--plan-id', str(c['plan_id']), '--chapter-key', str(c['chapter_key']),
           '--at', str(c['at']), '--branch', str(c['branch']), '--viewpoint', str(c['viewpoint']),
           '--canon-source', str(c['canon_source']), '--state-source', str(c['state_source']),
           '--canon-library', str(c['canon_library']), '--state-library', str(c['state_library']),
           '--workdir', str(c['workdir']), '--out', str(c['out'])]
    if provider and model:
        out += ['--provider', str(provider), '--model', str(model)]
    return out


def _git_state(root: Path) -> tuple[str | None, list[str]]:
    if not (root / '.git').exists():
        return None, []
    try:
        head = subprocess.run(['git','rev-parse','HEAD'], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
        text = subprocess.run(['git','status','--porcelain','--untracked-files=no'], cwd=root,
                              text=True, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f'cannot verify tracked harness state: {exc}')
    return head, [x for x in text.splitlines() if x.strip()]


def _paths(root: Path, slug: str) -> tuple[Path, Path]:
    d = root / 'projects' / slug / 'runtime_state' / 'operator'
    d.mkdir(parents=True, exist_ok=True)
    return d / 'job.json', d / 'pilot.log'


def _save(path: Path, data: dict) -> None:
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def _load(root: Path, slug: str) -> tuple[Path, Path, dict | None]:
    jp, lp = _paths(root, slug)
    if not jp.is_file():
        return jp, lp, None
    try:
        return jp, lp, json.loads(jp.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return jp, lp, {'state':'corrupt','project':slug}


def _alive(pid: object) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == 'nt':
        try:
            r = subprocess.run(['tasklist','/FI',f'PID eq {pid}','/NH'], text=True, capture_output=True, timeout=5)
            return r.returncode == 0 and str(pid) in r.stdout and 'No tasks are running' not in r.stdout
        except (OSError, subprocess.SubprocessError):
            return False
    try:
        os.kill(pid, 0); return True
    except OSError:
        return False


def _refresh(root: Path, slug: str, job: dict | None) -> dict | None:
    if not job or job.get('state') not in {'starting','running'}:
        return job
    if _alive(job.get('worker_pid')) or _alive(job.get('controller_pid')):
        return job
    job = dict(job); job.update(state='orphaned', finished_at=time.time(),
        message='managed process disappeared without terminal result; review/cancel before restart')
    _save(_paths(root, slug)[0], job)
    return job


def _status(root: Path, slug: str) -> int:
    jp, lp, job = _load(root, slug); job = _refresh(root, slug, job)
    if not job:
        print(json.dumps({'status':'idle','project':slug,'job':str(jp)}, indent=2)); return 0
    p = dict(job); p['status'] = p.pop('state', 'unknown'); p['job'] = str(jp); p['log'] = str(lp)
    p['chapter_exists'] = (root / str(_config(root, slug)['out'])).is_file()
    if p['status'] in {'failed','orphaned','harness_modified','cancelled'} and lp.is_file():
        p['log_tail'] = lp.read_text(encoding='utf-8', errors='replace')[-6000:]
    print(json.dumps(p, indent=2, ensure_ascii=False)); return 0


def _cancel(root: Path, slug: str) -> int:
    jp, _, job = _load(root, slug); job = _refresh(root, slug, job)
    if not job:
        print(json.dumps({'status':'idle','project':slug}, indent=2)); return 0
    for pid in {job.get('controller_pid'), job.get('worker_pid')}:
        if not _alive(pid): continue
        try:
            if os.name == 'nt': subprocess.run(['taskkill','/PID',str(pid),'/T','/F'], capture_output=True, timeout=15)
            else: os.killpg(int(pid), signal.SIGTERM)
        except (OSError, subprocess.SubprocessError): pass
    job = dict(job); job.update(state='cancelled', finished_at=time.time(), message='cancel requested; no automatic retry')
    _save(jp, job); print(json.dumps({'status':'cancelled','project':slug,'run_id':job.get('run_id')}, indent=2)); return 0


def _worker(root: Path, slug: str, run_id: str, extra: list[str], provider: str | None, model: str | None) -> int:
    jp, lp, job = _load(root, slug)
    if not job or job.get('run_id') != run_id: return 2
    explicit = bool(provider or model)
    if bool(provider) != bool(model): return 2
    args = _project_args(root, slug, allow_unpinned=explicit) + extra
    if explicit: args += ['--provider', str(provider), '--model', str(model)]
    head, dirty = _git_state(root)
    expected = job.get('harness_head')
    if dirty or (expected and head != expected):
        job.update(state='harness_modified', finished_at=time.time(), message='tracked harness changed before worker start')
        _save(jp, job); return 3
    job.update(state='running', worker_pid=os.getpid()); _save(jp, job)
    env = dict(os.environ)
    if expected: env['WRITING_HARNESS_HEAD'] = str(expected)
    controller = root / 'integrations' / 'hermes' / 'pilot_controller.py'
    with lp.open('w', encoding='utf-8', errors='replace') as log:
        proc = subprocess.Popen([sys.executable, str(controller), *args], cwd=root, stdout=log,
                                stderr=subprocess.STDOUT, text=True, env=env)
        job['controller_pid'] = proc.pid; _save(jp, job); rc = int(proc.wait())
    head2, dirty2 = _git_state(root)
    if dirty2 or (expected and head2 != expected):
        state, msg = 'harness_modified', 'tracked harness changed during run; result is not trusted'
    else:
        state = 'completed' if rc == 0 else 'failed'; msg = 'pilot completed' if rc == 0 else 'controller failed; report log, do not patch harness'
    chapter = root / str(_config(root, slug)['out'])
    job.update(state=state, exit_code=rc, finished_at=time.time(), message=msg,
               chapter=str(chapter) if chapter.is_file() else None)
    _save(jp, job); return rc


def _start(root: Path, slug: str, extra: list[str], provider: str | None, model: str | None) -> int:
    explicit = bool(provider or model)
    if bool(provider) != bool(model): raise SystemExit('explicit override requires both --provider and --model')
    _project_args(root, slug, allow_unpinned=explicit)
    _, _, old = _load(root, slug); old = _refresh(root, slug, old)
    if old and old.get('state') in {'starting','running','orphaned'}:
        status = 'already_running' if old.get('state') != 'orphaned' else 'orphaned'
        print(json.dumps({'status':status,'project':slug,'run_id':old.get('run_id'),
                          'message':'poll --status; never launch a duplicate' if status=='already_running' else 'review/cancel orphan before restart'}, indent=2)); return 0
    head, dirty = _git_state(root)
    if dirty:
        print(json.dumps({'status':'blocked_harness_dirty','project':slug,'head':head,
                          'dirty_tracked_files':dirty[:50], 'message':'restore/review tracked harness before writing; projects/ is ignored'}, indent=2)); return 0
    c = _config(root, slug); run_id = uuid.uuid4().hex; jp, lp = _paths(root, slug)
    job = {'version':1,'state':'starting','project':slug,'run_id':run_id,'started_at':time.time(),
           'provider':provider or c.get('provider'),'model':model or c.get('model'),'harness_head':head,
           'worker_pid':None,'controller_pid':None,'exit_code':None,'log':str(lp)}
    _save(jp, job)
    cmd = [sys.executable,'-m','writing_runtime.operator','--project',slug,'--_worker',run_id]
    if provider and model: cmd += ['--provider',provider,'--model',model]
    cmd += extra
    kw = dict(cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.name == 'nt': kw['creationflags'] = getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0) | getattr(subprocess,'CREATE_NO_WINDOW',0)
    else: kw['start_new_session'] = True
    proc = subprocess.Popen(cmd, **kw); job['worker_pid'] = proc.pid; _save(jp, job)
    print(json.dumps({'status':'started','project':slug,'run_id':run_id,'provider':job['provider'],'model':job['model'],
                      'job':str(jp),'log':str(lp),'next':f'writing-pilot --project {slug} --status'}, indent=2, ensure_ascii=False)); return 0


def main(argv: list[str] | None = None) -> int:
    root = _root(); controller = root / 'integrations' / 'hermes' / 'pilot_controller.py'
    if not (root / 'write_runtime.py').is_file() or not controller.is_file():
        print(f'deterministic writing runtime checkout is incomplete: {root}', file=sys.stderr); return 2
    raw = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(add_help=False); p.add_argument('--project'); p.add_argument('--provider'); p.add_argument('--model')
    p.add_argument('--status', action='store_true'); p.add_argument('--cancel', action='store_true'); p.add_argument('--foreground', action='store_true'); p.add_argument('--_worker')
    a, extra = p.parse_known_args(raw)
    if not a.project:
        return int(subprocess.run([sys.executable, str(controller), *raw], cwd=root).returncode)
    if a.status: return _status(root, a.project)
    if a.cancel: return _cancel(root, a.project)
    if a._worker: return _worker(root, a.project, a._worker, extra, a.provider, a.model)
    if a.foreground:
        explicit = bool(a.provider or a.model)
        if bool(a.provider) != bool(a.model): raise SystemExit('explicit override requires both --provider and --model')
        args = _project_args(root, a.project, allow_unpinned=explicit) + extra
        if explicit: args += ['--provider',str(a.provider),'--model',str(a.model)]
        head, dirty = _git_state(root)
        if dirty: raise SystemExit('tracked harness is dirty; refusing foreground writing run')
        env = dict(os.environ)
        if head: env['WRITING_HARNESS_HEAD'] = head
        return int(subprocess.run([sys.executable, str(controller), *args], cwd=root, env=env).returncode)
    return _start(root, a.project, extra, a.provider, a.model)


if __name__ == '__main__':
    raise SystemExit(main())
