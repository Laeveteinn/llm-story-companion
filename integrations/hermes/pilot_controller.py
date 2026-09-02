from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'write_runtime.py'
HERMES_CALL = Path(__file__).resolve().with_name('hermes_fresh_call.py')


def _assert_harness_unchanged() -> None:
    expected = os.environ.get('WRITING_HARNESS_HEAD')
    if not expected:
        return
    git = shutil.which('git')
    if not git or not (ROOT / '.git').exists():
        raise RuntimeError('managed writing run cannot verify harness immutability: git checkout unavailable')
    head = subprocess.run([git, 'rev-parse', 'HEAD'], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    dirty = subprocess.run(
        [git, 'status', '--porcelain', '--untracked-files=no'],
        cwd=ROOT, text=True, capture_output=True, check=True,
    ).stdout.strip()
    if head != expected or dirty:
        detail = dirty.splitlines()[:20]
        raise RuntimeError(
            'tracked harness changed during managed writing run; aborting before further model/runtime work. '
            f'expected_head={expected} actual_head={head} dirty={detail!r}'
        )


def run(args: list[str], *, allowed=(0,), capture=True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=capture)
    if proc.returncode not in allowed:
        if capture:
            sys.stderr.write(proc.stdout)
            sys.stderr.write(proc.stderr)
        raise RuntimeError(f'command failed ({proc.returncode}): {args!r}')
    return proc


def runtime(*args: str, allowed=(0,)) -> subprocess.CompletedProcess[str]:
    _assert_harness_unchanged()
    proc = run([sys.executable, str(RUNTIME), *args], allowed=allowed)
    _assert_harness_unchanged()
    return proc


def parse_json_stdout(proc: subprocess.CompletedProcess[str]) -> dict:
    text = proc.stdout.strip()
    if not text:
        return {}
    return json.loads(text)


def rooted(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def hermes(prompt: Path, out: Path, *, manifest: Path | None, provider: str | None,
           model: str | None, safe_mode: bool, timeout: int) -> None:
    _assert_harness_unchanged()
    cmd = [sys.executable, str(HERMES_CALL), '--prompt', str(prompt), '--out', str(out),
           '--project-root', str(ROOT), '--timeout', str(timeout)]
    if manifest is not None:
        cmd += ['--manifest', str(manifest)]
    if provider:
        cmd += ['--provider', provider]
    if model:
        cmd += ['--model', model]
    if safe_mode:
        cmd += ['--safe-mode']
    run(cmd, allowed=(0,))
    _assert_harness_unchanged()


def atomic_replace(src: Path, dst: Path) -> None:
    src.replace(dst)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Pilot controller: one-model, fresh-call, finite deterministic fiction loop.')
    ap.add_argument('brief')
    ap.add_argument('--plan-id', required=True)
    ap.add_argument('--chapter-key', required=True)
    ap.add_argument('--at', required=True)
    ap.add_argument('--branch', default='main')
    ap.add_argument('--viewpoint', required=True)
    ap.add_argument('--workdir', default='runtime_state/pilot')
    ap.add_argument('--out', default='runtime_state/pilot/final-chapter.txt')
    ap.add_argument('--canon-source', default='canon_source')
    ap.add_argument('--state-source', default='state_source')
    ap.add_argument('--canon-library', default='canon/canon.sqlite3')
    ap.add_argument('--state-library', default='state/story_state.sqlite3')
    ap.add_argument('--provider')
    ap.add_argument('--model')
    ap.add_argument('--safe-mode', action='store_true')
    ap.add_argument('--timeout', type=int, default=900)
    ap.add_argument('--prepare-only', action='store_true', help='Build stores and compile the first plan prompt, but do not invoke Hermes.')
    ap.add_argument('--skip-setup', action='store_true', help='Do not run dependency setup; still rebuild deterministic stores.')
    args = ap.parse_args(argv)

    work = rooted(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    brief = rooted(args.brief)
    canon_source = rooted(args.canon_source)
    state_source = rooted(args.state_source)
    canon_library = rooted(args.canon_library)
    state_library = rooted(args.state_library)
    output_path = rooted(args.out)

    if not brief.is_file():
        print(f'brief not found: {brief}', file=sys.stderr); return 2
    if not canon_source.exists():
        print(f'canon source not found: {canon_source}', file=sys.stderr); return 2
    if not state_source.exists():
        print(f'state source not found: {state_source}', file=sys.stderr); return 2

    projects_root = (ROOT / 'projects').resolve()
    if _under(brief, projects_root):
        unsafe_defaults = {
            (ROOT / 'canon_source').resolve(),
            (ROOT / 'state_source').resolve(),
            (ROOT / 'canon' / 'canon.sqlite3').resolve(),
            (ROOT / 'state' / 'story_state.sqlite3').resolve(),
        }
        selected = {canon_source, state_source, canon_library, state_library}
        if selected & unsafe_defaults:
            print(
                'named-project brief cannot use root fixture canon/state defaults; invoke writing-pilot --project <slug> '
                'or pass that project\'s explicit authority paths.',
                file=sys.stderr,
            )
            return 2

    _assert_harness_unchanged()

    if not args.skip_setup:
        setup = ROOT / ('setup.ps1' if sys.platform.startswith('win') else 'setup.sh')
        if sys.platform.startswith('win'):
            ps = shutil.which('pwsh') or shutil.which('powershell')
            if not ps:
                print('PowerShell not found; use --skip-setup after running setup.ps1 manually.', file=sys.stderr); return 2
            run([ps, '-NoProfile', '-File', str(setup)], allowed=(0,), capture=False)
        else:
            run([str(setup)], allowed=(0,), capture=False)

    canon_library.parent.mkdir(parents=True, exist_ok=True)
    state_library.parent.mkdir(parents=True, exist_ok=True)
    runtime('canon-build', str(canon_source), '--out', str(canon_library))
    runtime('state-build', str(state_source), '--library', str(canon_library), '--out', str(state_library))

    plan_prompt = work / 'plan.prompt.txt'
    plan_manifest = work / 'plan.request.json'
    runtime('plan-prompt', str(brief), '--plan-id', args.plan_id, '--chapter-key', args.chapter_key,
            '--at', args.at, '--branch', args.branch, '--viewpoint', args.viewpoint,
            '--library', str(canon_library), '--state-library', str(state_library),
            '--context-mode', 'fresh_call', '--out', str(plan_prompt), '--manifest-out', str(plan_manifest))
    if args.prepare_only:
        print(json.dumps({
            'status': 'prepared',
            'plan_prompt': str(plan_prompt),
            'manifest': str(plan_manifest),
            'branch': args.branch,
            'canon_library': str(canon_library),
            'state_library': str(state_library),
        }, indent=2))
        return 0

    plan_response = work / 'plan.response.txt'
    plan = work / 'plan.json'
    hermes(plan_prompt, plan_response, manifest=plan_manifest, provider=args.provider, model=args.model,
           safe_mode=args.safe_mode, timeout=args.timeout)
    if runtime('plan-apply', '--response', str(plan_response), '--manifest', str(plan_manifest), '--out', str(plan), '--json', allowed=(0,2)).returncode != 0:
        print('Initial plan response violated its output contract; stopping rather than asking the same context to explain itself.', file=sys.stderr)
        return 3

    plan_state = work / 'plan-repair-state.json'
    for _ in range(8):
        check = runtime('plan-check', str(plan), '--library', str(canon_library), '--state-library', str(state_library), '--json', allowed=(0,2))
        if check.returncode == 0:
            break
        repair_prompt = work / 'plan-repair.prompt.txt'
        repair_manifest = work / 'plan-repair.request.json'
        salvage = work / 'plan-salvage.json'
        routed = parse_json_stdout(runtime('plan-repair-next', str(plan), '--state', str(plan_state),
            '--library', str(canon_library), '--state-library', str(state_library),
            '--salvage-out', str(salvage), '--prompt-out', str(repair_prompt), '--manifest-out', str(repair_manifest),
            '--context-mode', 'fresh_call', '--json', allowed=(0,3)))
        action = routed.get('action')
        if action == 'human_review':
            print(json.dumps(routed, indent=2)); return 3
        if action not in {'repair_beats', 'rewrite_plan'} or not repair_prompt.exists():
            print(f'unexpected plan router action: {action}', file=sys.stderr); return 3
        repair_response = work / 'plan-repair.response.txt'
        hermes(repair_prompt, repair_response, manifest=repair_manifest, provider=args.provider, model=args.model,
               safe_mode=args.safe_mode, timeout=args.timeout)
        replacement = work / 'plan.next.json'
        if action == 'repair_beats':
            rc = runtime('plan-salvage-apply', '--plan', str(plan), '--salvage', str(salvage), '--response', str(repair_response), '--out', str(replacement), '--json', allowed=(0,2)).returncode
        else:
            rc = runtime('plan-apply', '--response', str(repair_response), '--manifest', str(repair_manifest), '--out', str(replacement), '--json', allowed=(0,2)).returncode
        if rc != 0:
            print('Plan repair response violated its request-bound contract.', file=sys.stderr); return 3
        atomic_replace(replacement, plan)
    else:
        print('Outer plan safety fuse exhausted.', file=sys.stderr); return 3

    epoch_dir = work / 'epochs'
    epoch_manifest = work / 'epochs.json'
    runtime('draft-epochs', str(plan), '--library', str(canon_library), '--state-library', str(state_library),
            '--context-mode', 'fresh_call', '--out-dir', str(epoch_dir), '--manifest-out', str(epoch_manifest), '--json')
    em = json.loads(epoch_manifest.read_text(encoding='utf-8'))
    responses = work / 'epoch-responses'; responses.mkdir(exist_ok=True)
    for row in em['epochs']:
        eid = row['epoch']['id']
        prompt = epoch_dir / row['prompt_file']
        call_manifest = epoch_dir / f'{eid}.call.json'
        call_manifest.write_text(json.dumps(row['call_manifest'], indent=2) + '\n', encoding='utf-8')
        hermes(prompt, responses / f'{eid}.response.txt', manifest=call_manifest, provider=args.provider,
               model=args.model, safe_mode=args.safe_mode, timeout=args.timeout)

    chapter = work / 'chapter.txt'
    provenance = work / 'chapter.provenance.json'
    if runtime('draft-epochs-apply', '--plan', str(plan), '--manifest', str(epoch_manifest), '--responses-dir', str(responses),
               '--library', str(canon_library), '--out', str(chapter), '--provenance-out', str(provenance), '--json', allowed=(0,2)).returncode != 0:
        print('Draft epoch response failed deterministic contract/canon validation.', file=sys.stderr); return 3

    prose_state = work / 'prose-repair-state.json'
    for _ in range(12):
        prompt = work / 'prose-repair.prompt.txt'
        salvage = work / 'prose-salvage.json'
        call_manifest = work / 'prose-repair.request.json'
        routed = parse_json_stdout(runtime('repair-next', str(chapter), '--state', str(prose_state), '--writer-plan', str(plan),
            '--library', str(canon_library), '--state-library', str(state_library), '--viewpoint', args.viewpoint,
            '--at', args.at, '--branch', args.branch, '--prompt-out', str(prompt), '--plan-out', str(salvage),
            '--manifest-out', str(call_manifest), '--context-mode', 'fresh_call', '--json', allowed=(0,3)))
        action = routed.get('action')
        if action == 'accept':
            _assert_harness_unchanged()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(chapter, output_path)
            print(json.dumps({
                'status': 'accepted',
                'chapter': str(output_path),
                'plan': str(plan),
                'branch': args.branch,
                'canon_library': str(canon_library),
                'state_library': str(state_library),
            }, indent=2))
            return 0
        if action == 'human_review':
            print(json.dumps(routed, indent=2)); return 3
        if action not in {'rewrite', 'salvage'} or not prompt.exists():
            print(f'unexpected prose router action: {action}', file=sys.stderr); return 3
        response = work / 'prose-repair.response.txt'
        hermes(prompt, response, manifest=call_manifest if call_manifest.exists() else None, provider=args.provider,
               model=args.model, safe_mode=args.safe_mode, timeout=args.timeout)
        next_chapter = work / 'chapter.next.txt'
        if action == 'rewrite':
            rc = runtime('rewrite-apply', '--response', str(response), '--source', str(chapter), '--manifest', str(call_manifest), '--out', str(next_chapter), '--json', allowed=(0,2)).returncode
        else:
            rc = runtime('salvage-apply', '--plan', str(salvage), '--source', str(chapter), '--response', str(response), '--out', str(next_chapter), '--json', allowed=(0,2)).returncode
        if rc != 0:
            print('Prose repair response violated the deterministic contract.', file=sys.stderr); return 3
        atomic_replace(next_chapter, chapter)
    print('Outer prose safety fuse exhausted.', file=sys.stderr)
    return 3


if __name__ == '__main__':
    raise SystemExit(main())
