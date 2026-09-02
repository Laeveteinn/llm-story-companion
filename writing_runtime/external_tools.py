from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

from .evidence import Issue, ToolStatus, paragraph_for_line
from .toolchain import find_languagetool_jar


def _run(cmd: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)


def _version(exe: str, args: list[str] | None = None) -> str | None:
    path = shutil.which(exe)
    if not path:
        return None
    try:
        cp = subprocess.run([path, *(args or ["--version"])], text=True, capture_output=True, timeout=15)
        out = (cp.stdout or cp.stderr).strip().splitlines()
        return out[0] if out else "installed"
    except Exception:
        return "installed"


def doctor(root: str | Path) -> list[ToolStatus]:
    root = Path(root)
    local_cspell = root / "node_modules" / ".bin" / ("cspell.cmd" if sys.platform.startswith("win") else "cspell")
    statuses = [
        ToolStatus("python", True, sys.version.split()[0]),
        ToolStatus("node", shutil.which("node") is not None, _version("node", ["--version"])),
        ToolStatus("npm", shutil.which("npm") is not None, _version("npm", ["--version"])),
        ToolStatus("npm-lock", (root / "package-lock.json").exists(),
                   "present" if (root / "package-lock.json").exists() else None,
                   None if (root / "package-lock.json").exists() else "first full npm install must generate package-lock.json; preserve it for reproducible npm ci"),
        ToolStatus("vale", shutil.which("vale") is not None, _version("vale", ["--version"])),
        ToolStatus("cspell", local_cspell.exists() or shutil.which("cspell") is not None,
                   "local npm" if local_cspell.exists() else _version("cspell", ["--version"])),
        ToolStatus("retext", (root / "node_modules" / "retext-english").exists(),
                   "local npm" if (root / "node_modules" / "retext-english").exists() else None),
        ToolStatus("plain-english", _local_bin(root, "plain-english") is not None,
                   "local npm" if (root / "node_modules" / "plain-english").exists() else _version("plain-english", ["--version"])),
        ToolStatus("slopless", _local_bin(root, "slopless") is not None,
                   "local npm" if (root / "node_modules" / "slopless").exists() else _version("slopless", ["--version"])),
        ToolStatus("java", shutil.which("java") is not None, _version("java", ["-version"])),
        ToolStatus("languagetool", bool(find_languagetool_jar(root)),
                   str(find_languagetool_jar(root)) if find_languagetool_jar(root) else None,
                   None if find_languagetool_jar(root) else "optional: set LANGUAGETOOL_JAR or place standalone CLI under .tools/LanguageTool"),
    ]
    for module in ("pydantic", "networkx", "spacy", "textdescriptives", "wordfreq", "cmudict", "rapidfuzz"):
        try:
            mod = __import__(module)
            statuses.append(ToolStatus(module, True, getattr(mod, "__version__", "installed")))
        except Exception as exc:
            statuses.append(ToolStatus(module, False, detail=str(exc)))
    try:
        import spacy
        spacy.load("en_core_web_sm")
        statuses.append(ToolStatus("spacy:en_core_web_sm", True, "installed"))
    except Exception as exc:
        statuses.append(ToolStatus("spacy:en_core_web_sm", False, detail=str(exc)))
    return statuses


def run_retext(path: str | Path, root: str | Path, text: str) -> tuple[list[Issue], ToolStatus]:
    root = Path(root)
    path = Path(path)
    node = shutil.which("node")
    script = root / "tools" / "retext-lint.mjs"
    if not node or not script.exists() or not (root / "node_modules" / "retext-english").exists():
        return [], ToolStatus("retext", False, detail="run setup script / npm install")
    cp = _run([node, str(script), str(path)], root)
    if cp.returncode not in (0, 1):
        return [], ToolStatus("retext", False, detail=(cp.stderr or cp.stdout).strip()[:500])
    try:
        raw = json.loads(cp.stdout or "[]")
    except json.JSONDecodeError as exc:
        return [], ToolStatus("retext", False, detail=f"invalid JSON: {exc}")
    issues = []
    objective = {"retext-repeated-words", "retext-indefinite-article", "retext-redundant-acronyms", "retext-contractions"}
    family_map = {
        "retext-repeated-words": "repetition",
        "retext-indefinite-article": "grammar",
        "retext-redundant-acronyms": "grammar",
        "retext-contractions": "grammar",
        "retext-passive": "passive",
        "retext-intensify": "style",
    }
    for r in raw:
        source = str(r.get("source") or "retext")
        line = r.get("line")
        issues.append(Issue(
            code=f"retext.{source.removeprefix('retext-')}.{r.get('ruleId') or 'issue'}",
            source="retext",
            severity="warning" if source in objective else "suggestion",
            message=str(r.get("message") or "retext finding"),
            line=int(line) if line else None,
            column=int(r["column"]) if r.get("column") else None,
            end_line=int(r["endLine"]) if r.get("endLine") else None,
            end_column=int(r["endColumn"]) if r.get("endColumn") else None,
            paragraph=paragraph_for_line(text, int(line)) if line else None,
            family=family_map.get(source, "style"),
            evidence={k: v for k, v in r.items() if k not in {"message"}},
        ))
    return issues, ToolStatus("retext", True, "local npm")


def run_vale(path: str | Path, root: str | Path, text: str) -> tuple[list[Issue], ToolStatus]:
    root = Path(root)
    path = Path(path)
    vale = shutil.which("vale")
    if not vale:
        local = root / ".tools" / ("vale.exe" if sys.platform.startswith("win") else "vale")
        vale = str(local) if local.exists() else None
    if not vale:
        return [], ToolStatus("vale", False, detail="install Vale; setup scripts attempt this automatically")
    cp = _run([vale, "--output=JSON", str(path)], root)
    # Vale returns a non-zero exit code when alerts exceed the configured level.
    try:
        data = json.loads(cp.stdout or "{}")
    except json.JSONDecodeError:
        return [], ToolStatus("vale", False, detail=(cp.stderr or cp.stdout).strip()[:500])
    alerts: list[dict[str, Any]] = []
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                alerts.extend(x for x in value if isinstance(x, dict))
    elif isinstance(data, list):
        alerts = [x for x in data if isinstance(x, dict)]
    issues: list[Issue] = []
    for a in alerts:
        check = str(a.get("Check") or a.get("check") or "Vale")
        severity_raw = str(a.get("Severity") or a.get("severity") or "suggestion").lower()
        severity = {"error": "warning", "warning": "warning", "suggestion": "suggestion"}.get(severity_raw, "suggestion")
        line = a.get("Line") or a.get("line")
        span = a.get("Span") or a.get("span") or []
        column = span[0] if isinstance(span, list) and span else a.get("Column")
        family = "style"
        lc = check.lower()
        if "passive" in lc:
            family = "passive"
        elif "repeat" in lc or "cliche" in lc:
            family = "repetition"
        elif "harper" in lc:
            family = "grammar"
        elif "aitells" in lc:
            family = "ai_tell"
        issues.append(Issue(
            code=f"vale.{check}", source="vale", severity=severity,
            message=str(a.get("Message") or a.get("message") or a.get("Description") or "Vale finding"),
            line=int(line) if line else None,
            column=int(column) if column else None,
            paragraph=paragraph_for_line(text, int(line)) if line else None,
            family=family,
            evidence={"check": check, "original_severity": severity_raw, "action": a.get("Action")},
        ))
    return issues, ToolStatus("vale", True, _version(vale, ["--version"]))


_CSPELL_RE = re.compile(r"^(?P<file>.*?):(?P<line>\d+):(?P<col>\d+)\s+-\s+(?P<msg>.*)$")


def _local_bin(root: Path, name: str) -> str | None:
    candidate = root / "node_modules" / ".bin" / (name + ".cmd" if sys.platform.startswith("win") else name)
    if candidate.exists():
        return str(candidate)
    return shutil.which(name)


def run_cspell(path: str | Path, root: str | Path, text: str) -> tuple[list[Issue], ToolStatus]:
    root = Path(root)
    path = Path(path)
    exe = _local_bin(root, "cspell")
    if not exe:
        return [], ToolStatus("cspell", False, detail="run npm install")
    cmd = [exe, "lint", str(path), "--config", str(root / "cspell.json"), "--no-progress", "--no-summary", "--no-color"]
    cp = _run(cmd, root)
    issues: list[Issue] = []
    for line_text in (cp.stdout + "\n" + cp.stderr).splitlines():
        m = _CSPELL_RE.match(line_text.strip())
        if not m:
            continue
        line = int(m.group("line")); col = int(m.group("col")); msg = m.group("msg")
        issues.append(Issue(
            code="cspell.unknown_word", source="cspell", severity="warning", message=msg,
            line=line, column=col, paragraph=paragraph_for_line(text, line), family="spelling",
        ))
    return issues, ToolStatus("cspell", True, "local npm" if str(exe).startswith(str(root)) else _version("cspell", ["--version"]))



def _line_col_from_offset(text: str, offset: int) -> tuple[int, int]:
    offset = max(0, min(len(text), int(offset)))
    before = text[:offset]
    line = before.count("\n") + 1
    last = before.rfind("\n")
    column = offset + 1 if last < 0 else offset - last
    return line, column


def run_languagetool(path: str | Path, root: str | Path, text: str) -> tuple[list[Issue], ToolStatus]:
    """Run an explicitly installed LanguageTool standalone CLI; never downloads it."""
    root = Path(root); path = Path(path)
    jar = find_languagetool_jar(root)
    java = shutil.which("java")
    if not jar:
        return [], ToolStatus("languagetool", False, detail="optional: set LANGUAGETOOL_JAR or place standalone distribution under .tools/LanguageTool")
    if not java:
        return [], ToolStatus("languagetool", False, detail="LanguageTool found but Java 17+ is unavailable")
    cp = _run([java, "-jar", str(jar), "-l", "en-CA", "--json", str(path)], root, timeout=180)
    # Some LT builds write progress to stderr while JSON remains on stdout.
    try:
        data = json.loads(cp.stdout or "{}")
    except json.JSONDecodeError:
        return [], ToolStatus("languagetool", False, detail=(cp.stderr or cp.stdout).strip()[:500])
    issues: list[Issue] = []
    for match in data.get("matches", []) if isinstance(data, dict) else []:
        if not isinstance(match, dict):
            continue
        rule = match.get("rule") or {}
        rid = str(rule.get("id") or "issue")
        category = rule.get("category") or {}
        issue_type = str(rule.get("issueType") or "").lower()
        family = "grammar"
        if issue_type in {"style", "locale-violation"}:
            family = "style"
        elif issue_type in {"duplication"} or "repeat" in rid.lower():
            family = "repetition"
        offset = int(match.get("offset") or 0)
        line, col = _line_col_from_offset(text, offset)
        replacements = [r.get("value") for r in (match.get("replacements") or []) if isinstance(r, dict) and r.get("value")][:5]
        issues.append(Issue(
            code=f"languagetool.{rid}", source="languagetool",
            severity="suggestion" if family == "style" else "warning",
            message=str(match.get("message") or "LanguageTool finding"),
            line=line, column=col, paragraph=paragraph_for_line(text, line), family=family,
            evidence={"rule": rid, "issue_type": issue_type, "category": category, "replacements": replacements,
                      "offset": offset, "length": match.get("length")},
        ))
    detail = str(data.get("software", {}).get("version") or jar) if isinstance(data, dict) else str(jar)
    return issues, ToolStatus("languagetool", True, detail)


def run_plain_english(path: str | Path, root: str | Path, text: str) -> tuple[list[Issue], ToolStatus]:
    """Run only plain-english's deterministic lint path; never invoke its optional semantic/model layer."""
    root = Path(root); path = Path(path)
    exe = _local_bin(root, "plain-english")
    if not exe:
        return [], ToolStatus("plain-english", False, detail="run npm install")
    cp = _run([exe, "lint", "--format", "json", "--fail-on", "never", str(path)], root)
    if cp.returncode not in (0, 1):
        return [], ToolStatus("plain-english", False, detail=(cp.stderr or cp.stdout).strip()[:500])
    try:
        data = json.loads(cp.stdout or "{}")
    except json.JSONDecodeError as exc:
        return [], ToolStatus("plain-english", False, detail=f"invalid JSON: {exc}")
    issues: list[Issue] = []
    files = data.get("files", []) if isinstance(data, dict) else []
    for file_result in files:
        if not isinstance(file_result, dict):
            continue
        for finding in file_result.get("findings", []) or []:
            if not isinstance(finding, dict):
                continue
            rid = str(finding.get("ruleId") or finding.get("rule") or "issue")
            line = finding.get("line")
            col = finding.get("column")
            lc = rid.lower()
            if "unglossed" in lc or "jargon" in lc or "term" in lc:
                family = "terminology"
            elif "sentence" in lc or "spread" in lc or "readab" in lc:
                family = "rhythm"
            else:
                family = "ai_style"
            # This tool intentionally remains low-weight style evidence. Its own
            # error/warn labels never become hard runtime failures.
            raw_severity = str(finding.get("severity") or "warn").lower()
            severity = "warning" if raw_severity in {"error", "block"} else "suggestion"
            issues.append(Issue(
                code=f"plain-english.{rid}", source="plain-english", severity=severity,
                message=str(finding.get("message") or "plain-english finding"),
                line=int(line) if line else None, column=int(col) if col else None,
                paragraph=paragraph_for_line(text, int(line)) if line else None,
                family=family,
                evidence={
                    "rule": rid, "original_severity": raw_severity,
                    "match": finding.get("match"), "link": finding.get("link"),
                },
            ))
    return issues, ToolStatus("plain-english", True, "deterministic lint only")


def run_slopless(path: str | Path, root: str | Path, text: str) -> tuple[list[Issue], ToolStatus]:
    """Run Slopless as a deterministic, JSON-only style sensor."""
    root = Path(root); path = Path(path)
    exe = _local_bin(root, "slopless")
    if not exe:
        return [], ToolStatus("slopless", False, detail="run npm install")
    cp = _run([exe, str(path)], root)
    # 0=no findings, 1=findings, 2=command failure.
    if cp.returncode not in (0, 1):
        return [], ToolStatus("slopless", False, detail=(cp.stderr or cp.stdout).strip()[:500])
    try:
        data = json.loads(cp.stdout or "[]")
    except json.JSONDecodeError as exc:
        return [], ToolStatus("slopless", False, detail=f"invalid JSON: {exc}")
    results = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    issues: list[Issue] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        for msg in result.get("messages", []) or []:
            if not isinstance(msg, dict):
                continue
            rid = str(msg.get("ruleId") or "slopless/issue")
            rid_short = rid.split("/", 1)[-1]
            line = msg.get("line"); col = msg.get("column")
            lc = rid_short.lower()
            if "repeat" in lc or "cliche" in lc:
                family = "repetition"
            elif "sentence" in lc or "rhythm" in lc or "cadence" in lc:
                family = "rhythm"
            else:
                family = "ai_style"
            # Slopless is deliberately an opinionated style sensor. Never promote its
            # textlint severity to a hard runtime error.
            raw_severity = msg.get("severity")
            severity = "warning" if raw_severity in (2, "2", "error") else "suggestion"
            issues.append(Issue(
                code=f"slopless.{rid_short}", source="slopless", severity=severity,
                message=str(msg.get("message") or "Slopless finding"),
                line=int(line) if line else None, column=int(col) if col else None,
                end_line=int(msg["endLine"]) if msg.get("endLine") else None,
                end_column=int(msg["endColumn"]) if msg.get("endColumn") else None,
                paragraph=paragraph_for_line(text, int(line)) if line else None,
                family=family, evidence={"rule": rid, "original_severity": raw_severity},
            ))
    return issues, ToolStatus("slopless", True, "deterministic JSON lint")
