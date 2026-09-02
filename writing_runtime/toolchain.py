from __future__ import annotations

from hashlib import sha256
from importlib import metadata
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

import yaml


def _sha(path: Path) -> str:
    h = sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _cmd_version(name: str, args: list[str] | None = None) -> str | None:
    exe = shutil.which(name)
    if not exe:
        return None
    try:
        cp = subprocess.run([exe, *(args or ['--version'])], text=True, capture_output=True, timeout=15, check=False)
        lines = (cp.stdout or cp.stderr).strip().splitlines()
        return lines[0].strip() if lines else 'installed'
    except Exception:
        return 'installed'


def _dist_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _node_package_versions(root: Path) -> dict[str, str | None]:
    pkg = root / 'package.json'
    if not pkg.exists():
        return {}
    data = json.loads(pkg.read_text(encoding='utf-8'))
    out: dict[str, str | None] = {}
    for name in sorted((data.get('dependencies') or {}).keys()):
        installed = root / 'node_modules' / name / 'package.json'
        if installed.exists():
            try:
                out[name] = str(json.loads(installed.read_text(encoding='utf-8')).get('version'))
            except Exception:
                out[name] = 'unreadable'
        else:
            out[name] = None
    return out


def find_languagetool_jar(root: str | Path) -> Path | None:
    root = Path(root)
    import os
    env = os.environ.get('LANGUAGETOOL_JAR')
    if env and Path(env).is_file():
        return Path(env)
    candidates = [
        root / '.tools' / 'LanguageTool' / 'languagetool-commandline.jar',
        root / '.tools' / 'languagetool-commandline.jar',
    ]
    for p in candidates:
        if p.is_file():
            return p
    lt_root = root / '.tools' / 'LanguageTool'
    if lt_root.exists():
        hits = sorted(lt_root.rglob('languagetool-commandline.jar'))
        if hits:
            return hits[0]
    return None


def snapshot(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    files: dict[str, str] = {}
    for rel in ('package.json', 'package-lock.json', '.vale.ini', 'cspell.json', 'config/gate_policy.yaml', 'config/planning_policy.yaml', 'config/toolchain_expected.yaml'):
        p = root / rel
        if p.is_file():
            files[rel] = _sha(p)
    styles = root / '.vale' / 'styles'
    if styles.exists():
        for p in sorted(x for x in styles.rglob('*') if x.is_file()):
            files[str(p.relative_to(root)).replace('\\', '/')] = _sha(p)
    lt = find_languagetool_jar(root)
    if lt:
        files[str(lt.relative_to(root)).replace('\\', '/') if root in lt.parents else str(lt)] = _sha(lt)
    python_packages = {name: _dist_version(name) for name in ('PyYAML','pydantic','networkx','spacy','textdescriptives','wordfreq','cmudict','rapidfuzz')}
    return {
        'format': 1,
        'python': sys.version.split()[0],
        'commands': {
            'node': _cmd_version('node'), 'npm': _cmd_version('npm'), 'vale': _cmd_version('vale'), 'java': _cmd_version('java', ['-version'])
        },
        'python_packages': python_packages,
        'node_packages': _node_package_versions(root),
        'languagetool_jar': str(lt) if lt else None,
        'files': files,
    }


def write_lock(root: str | Path, out: str | Path) -> dict[str, Any]:
    data = snapshot(root)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')
    return data


def verify_lock(root: str | Path, lock_path: str | Path) -> dict[str, Any]:
    root = Path(root); lock_path = Path(lock_path)
    if not lock_path.exists():
        return {'ok': False, 'errors': [f'lock file not found: {lock_path}'], 'changes': {}}
    expected = json.loads(lock_path.read_text(encoding='utf-8'))
    actual = snapshot(root)
    changes: dict[str, Any] = {}
    for section in ('commands','python_packages','node_packages','files','languagetool_jar'):
        if expected.get(section) != actual.get(section):
            changes[section] = {'locked': expected.get(section), 'actual': actual.get(section)}
    return {'ok': not changes, 'errors': [], 'changes': changes}


def expected_version_report(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    cfg_path = root / 'config' / 'toolchain_expected.yaml'
    cfg = yaml.safe_load(cfg_path.read_text(encoding='utf-8')) if cfg_path.exists() else {}
    actual = snapshot(root)
    issues: list[str] = []
    node_raw = actual['commands'].get('node') or ''
    m = re.search(r'(\d+)', node_raw)
    min_major = int(((cfg.get('node') or {}).get('minimum_major')) or 0)
    if m and int(m.group(1)) < min_major:
        issues.append(f'Node {m.group(1)} is below required major {min_major}')
    min_version = str(((cfg.get('node') or {}).get('minimum_version')) or '')
    if min_version and node_raw:
        vm = re.search(r'(\d+)\.(\d+)\.(\d+)', node_raw)
        try:
            want = tuple(int(x) for x in min_version.split('.')[:3])
        except ValueError:
            want = ()
        if vm and want and tuple(map(int, vm.groups())) < want:
            issues.append(f'Node: expected >= {min_version}, got {".".join(vm.groups())}')
    npm_expected = cfg.get('npm') or {}
    for name, want in npm_expected.items():
        got = actual['node_packages'].get(name)
        if got is not None and str(got) != str(want):
            issues.append(f'npm {name}: expected {want}, got {got}')
    vale_target = str(((cfg.get('vale') or {}).get('target')) or '')
    vale_actual = actual['commands'].get('vale') or ''
    if vale_actual and vale_target and vale_target not in vale_actual:
        issues.append(f'Vale: expected {vale_target}, got {vale_actual}')
    py_expected = cfg.get('python') or {}
    for name, want in py_expected.items():
        got = actual['python_packages'].get(name)
        if got is not None and str(got) != str(want):
            issues.append(f'Python {name}: expected {want}, got {got}')
    return {'ok': not issues, 'issues': issues, 'expected': cfg, 'actual': actual}
