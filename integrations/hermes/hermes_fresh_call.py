from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Run one isolated Hermes candidate-generation call.')
    ap.add_argument('--prompt', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--manifest', help='Optional runtime prompt/call manifest; must match prompt and require fresh_call.')
    ap.add_argument('--project-root', default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument('--hermes', default='hermes')
    ap.add_argument('--provider')
    ap.add_argument('--model')
    ap.add_argument('--timeout', type=int, default=900)
    ap.add_argument('--toolsets', default='clarify', help='Minimal valid Hermes toolset; contract rejects tool detours.')
    ap.add_argument('--meta-out')
    ap.add_argument('--safe-mode', action='store_true', help='Also disable Hermes user config/plugins/MCP/hooks. Requires provider/runtime access that survives safe mode.')
    args = ap.parse_args(argv)

    root = Path(args.project_root).resolve()
    prompt_path = Path(args.prompt).resolve()
    out_path = Path(args.out).resolve()
    if not (root/'write_runtime.py').is_file():
        print(f'project root is invalid: {root}', file=sys.stderr); return 2
    if not prompt_path.is_file():
        print(f'prompt not found: {prompt_path}', file=sys.stderr); return 2
    prompt = prompt_path.read_text(encoding='utf-8')
    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
        call = manifest.get('call', manifest) if isinstance(manifest, dict) else {}
        expected = call.get('prompt_sha256')
        if expected and expected != sha(prompt):
            print('runtime call manifest does not match prompt bytes', file=sys.stderr); return 2
        mode = call.get('context_mode')
        if mode and mode != 'fresh_call':
            print(f'refusing non-fresh Hermes call manifest: {mode}', file=sys.stderr); return 2
    exe = shutil.which(args.hermes)
    if not exe:
        print(f'Hermes executable not found on PATH: {args.hermes}', file=sys.stderr); return 2
    # No --resume / --continue path exists in this command builder. Each invocation is a new CLI session.
    cmd = [exe, 'chat', '-Q', '--ignore-rules', '--source', 'tool', '--max-turns', '1']
    if args.safe_mode:
        cmd += ['--safe-mode']
    if args.toolsets:
        cmd += ['--toolsets', args.toolsets]
    if args.provider:
        cmd += ['--provider', args.provider]
    if args.model:
        cmd += ['--model', args.model]
    cmd += ['-q', prompt]

    started = time.time()
    proc = subprocess.run(cmd, cwd=root, text=True, capture_output=True, timeout=args.timeout,
                          env={**os.environ, 'WRITING_RUNTIME_ROOT': str(root)})
    elapsed = round(time.time()-started, 3)
    if proc.returncode != 0:
        print(proc.stderr.rstrip(), file=sys.stderr)
        return proc.returncode or 2
    response = proc.stdout
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(response, encoding='utf-8')
    meta = {
        'version': 1,
        'mode': 'fresh_hermes_process',
        'project_root': str(root),
        'prompt_path': str(prompt_path),
        'prompt_sha256': sha(prompt),
        'response_sha256': sha(response),
        'elapsed_seconds': elapsed,
        'hermes_executable': exe,
        'provider': args.provider,
        'model': args.model,
        'toolsets': args.toolsets,
        'session_resume_flags_allowed': False,
        'ignore_rules': True,
        'safe_mode': bool(args.safe_mode),
    }
    meta_path = Path(args.meta_out).resolve() if args.meta_out else out_path.with_suffix(out_path.suffix+'.meta.json')
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(out_path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
