from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'write_runtime.py'
HERMES_CALL = Path(__file__).resolve().with_name('hermes_fresh_call.py')


def run(args: list[str], *, allowed=(0,), capture=True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=capture)
    if proc.returncode not in allowed:
        if capture:
            sys.stderr.write(proc.stdout)
            sys.stderr.write(proc.stderr)
        raise RuntimeError(f'command failed ({proc.returncode}): {args!r}')
    return proc


def runtime(*args: str, allowed=(0,)) -> subprocess.CompletedProcess[str]:
    return run([sys.executable, str(RUNTIME), *args], allowed=allowed)


def parse_json_stdout(proc: subprocess.CompletedProcess[str]) -> dict:
    text = proc.stdout.strip()
    if not text:
        return {}
    return json.loads(text)


def hermes(prompt: Path, out: Path, *, manifest: Path | None, provider: str | None,
           model: str | None, safe_mode: bool, timeout: int) -> None:
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
    ap.add_argument('--provider')
    ap.add_argument('--model')
    ap.add_argument('--safe-mode', action='store_true')
    ap.add_argument('--timeout', type=int, default=900)
    ap.add_argument('--prepare-only', action='store_true', help='Build stores and compile the first plan prompt, but do not invoke Hermes.')
    ap.add_argument('--skip-setup', action='store_true', help='Do not run dependency setup; still rebuild deterministic stores.')
    args = ap.parse_args(argv)

    work = (ROOT / args.workdir).resolve() if not Path(args.workdir).is_absolute() else Path(args.workdir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    brief = Path(args.brief).resolve()
    if not brief.is_file():
        print(f'brief not found: {brief}', file=sys.stderr); return 2

    # Deterministic authority is rebuilt before any model call.
    if not args.skip_setup:
        setup = ROOT / ('setup.ps1' if sys.platform.startswith('win') else 'setup.sh')
        if sys.platform.startswith('win'):
            # Do not silently bypass PowerShell execution policy or choose a shell for the user.
            ps = shutil.which('pwsh') or shutil.which('powershell')
            if not ps:
                print('PowerShell not found; use --skip-setup after running setup.ps1 manually.', file=sys.stderr); return 2
            run([ps, '-NoProfile', '-File', str(setup)], allowed=(0,), capture=False)
        else:
            run([str(setup)], allowed=(0,), capture=False)
    runtime('canon-build', 'canon_source', '--out', 'canon/canon.sqlite3')
    runtime('state-build', 'state_source', '--library', 'canon/canon.sqlite3', '--out', 'state/story_state.sqlite3')

    plan_prompt = work / 'plan.prompt.txt'
    plan_manifest = work / 'plan.request.json'
    runtime('plan-prompt', str(brief), '--plan-id', args.plan_id, '--chapter-key', args.chapter_key,
            '--at', args.at, '--branch', args.branch, '--viewpoint', args.viewpoint,
            '--library', 'canon/canon.sqlite3', '--state-library', 'state/story_state.sqlite3',
            '--context-mode', 'fresh_call', '--out', str(plan_prompt), '--manifest-out', str(plan_manifest))
    if args.prepare_only:
        print(json.dumps({'status':'prepared','plan_prompt':str(plan_prompt),'manifest':str(plan_manifest),'branch':args.branch}, indent=2))
        return 0

    plan_response = work / 'plan.response.txt'
    plan = work / 'plan.json'
    hermes(plan_prompt, plan_response, manifest=plan_manifest, provider=args.provider, model=args.model,
           safe_mode=args.safe_mode, timeout=args.timeout)
    if runtime('plan-apply', '--response', str(plan_response), '--manifest', str(plan_manifest), '--out', str(plan), '--json', allowed=(0,2)).returncode != 0:
        print('Initial plan response violated its output contract; stopping rather than asking the same context to explain itself.', file=sys.stderr)
        return 3

    # Plan repair is already finite in the runtime. The controller only obeys its action.
    plan_state = work / 'plan-repair-state.json'
    for _ in range(8):  # absolute outer safety fuse; normal runtime budgets stop much earlier.
        check = runtime('plan-check', str(plan), '--library', 'canon/canon.sqlite3', '--state-library', 'state/story_state.sqlite3', '--json', allowed=(0,2))
        if check.returncode == 0:
            break
        repair_prompt = work / 'plan-repair.prompt.txt'
        repair_manifest = work / 'plan-repair.request.json'
        salvage = work / 'plan-salvage.json'
        routed = parse_json_stdout(runtime('plan-repair-next', str(plan), '--state', str(plan_state),
            '--library', 'canon/canon.sqlite3', '--state-library', 'state/story_state.sqlite3',
            '--salvage-out', str(salvage), '--prompt-out', str(repair_prompt), '--manifest-out', str(repair_manifest),
            '--context-mode', 'fresh_call', '--json', allowed=(0,3)))
        action = routed.get('action')
        if action == 'human_review':
            print(json.dumps(routed, indent=2)); return 3
        if action not in {'repair_beats','rewrite_plan'} or not repair_prompt.exists():
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

    # Always use disclosure epochs. A one-epoch plan is just the degenerate safe case.
    epoch_dir = work / 'epochs'
    epoch_manifest = work / 'epochs.json'
    runtime('draft-epochs', str(plan), '--library', 'canon/canon.sqlite3', '--state-library', 'state/story_state.sqlite3',
            '--context-mode', 'fresh_call', '--out-dir', str(epoch_dir), '--manifest-out', str(epoch_manifest), '--json')
    em = json.loads(epoch_manifest.read_text(encoding='utf-8'))
    responses = work / 'epoch-responses'; responses.mkdir(exist_ok=True)
    for row in em['epochs']:
        eid = row['epoch']['id']
        prompt = epoch_dir / row['prompt_file']
        # Materialize the embedded call manifest so the fresh-call wrapper can verify prompt bytes.
        call_manifest = epoch_dir / f'{eid}.call.json'
        call_manifest.write_text(json.dumps(row['call_manifest'], indent=2) + '\n', encoding='utf-8')
        hermes(prompt, responses / f'{eid}.response.txt', manifest=call_manifest, provider=args.provider,
               model=args.model, safe_mode=args.safe_mode, timeout=args.timeout)

    chapter = work / 'chapter.txt'
    provenance = work / 'chapter.provenance.json'
    if runtime('draft-epochs-apply', '--plan', str(plan), '--manifest', str(epoch_manifest), '--responses-dir', str(responses),
               '--library', 'canon/canon.sqlite3', '--out', str(chapter), '--provenance-out', str(provenance), '--json', allowed=(0,2)).returncode != 0:
        print('Draft epoch response failed deterministic contract/canon validation.', file=sys.stderr); return 3

    # Finite prose repair loop. The runtime owns normal budgets and cycle detection; this fuse catches integration bugs.
    prose_state = work / 'prose-repair-state.json'
    for _ in range(12):
        prompt = work / 'prose-repair.prompt.txt'
        salvage = work / 'prose-salvage.json'
        call_manifest = work / 'prose-repair.request.json'
        routed = parse_json_stdout(runtime('repair-next', str(chapter), '--state', str(prose_state), '--writer-plan', str(plan),
            '--library', 'canon/canon.sqlite3', '--state-library', 'state/story_state.sqlite3', '--viewpoint', args.viewpoint,
            '--at', args.at, '--branch', args.branch, '--prompt-out', str(prompt), '--plan-out', str(salvage),
            '--manifest-out', str(call_manifest), '--context-mode', 'fresh_call', '--json', allowed=(0,3)))
        action = routed.get('action')
        if action == 'accept':
            final = Path(args.out).resolve() if Path(args.out).is_absolute() else (ROOT / args.out).resolve()
            final.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(chapter, final)
            print(json.dumps({'status':'accepted','chapter':str(final),'plan':str(plan),'branch':args.branch}, indent=2))
            return 0
        if action == 'human_review':
            print(json.dumps(routed, indent=2)); return 3
        if action not in {'rewrite','salvage'} or not prompt.exists():
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
