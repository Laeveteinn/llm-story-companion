from __future__ import annotations

from dataclasses import asdict, dataclass, field
from fnmatch import fnmatch
from typing import Any, Iterable


@dataclass(frozen=True)
class Issue:
    code: str
    source: str
    severity: str
    message: str
    line: int | None = None
    column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    paragraph: int | None = None
    family: str = "general"
    hard: bool = False
    weight: float | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolStatus:
    name: str
    available: bool
    version: str | None = None
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GateReport:
    passed: bool
    hard_failures: int
    suspicion_score: float
    threshold: float
    issues: list[Issue]
    paragraph_scores: dict[int, float]
    contaminated_paragraphs: list[int]
    metrics: dict[str, Any] = field(default_factory=dict)
    tools: list[ToolStatus] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pass": self.passed,
            "hard_failures": self.hard_failures,
            "suspicion_score": self.suspicion_score,
            "threshold": self.threshold,
            "issues": [i.as_dict() for i in self.issues],
            "paragraph_scores": {str(k): v for k, v in sorted(self.paragraph_scores.items())},
            "contaminated_paragraphs": self.contaminated_paragraphs,
            "metrics": self.metrics,
            "tools": [t.as_dict() for t in self.tools],
            "rationale": self.rationale,
        }


def paragraph_line_ranges(text: str) -> list[tuple[int, int, int, str]]:
    """Return (paragraph_index, start_line, end_line, paragraph_text), 1-indexed.

    Blank-line separated blocks are the stable unit used by deterministic repair.
    """
    lines = text.splitlines()
    out: list[tuple[int, int, int, str]] = []
    buf: list[str] = []
    start = 1
    idx = 0

    def flush(end_line: int) -> None:
        nonlocal buf, idx
        if not buf:
            return
        idx += 1
        out.append((idx, start, end_line, "\n".join(buf)))
        buf = []

    for lineno, line in enumerate(lines, 1):
        if line.strip():
            if not buf:
                start = lineno
            buf.append(line)
        else:
            flush(lineno - 1)
    flush(len(lines))
    return out


def paragraph_for_line(text: str, line: int | None) -> int | None:
    if line is None:
        return None
    for idx, start, end, _ in paragraph_line_ranges(text):
        if start <= line <= end:
            return idx
    return None


def issue_weight(issue: Issue, policy: dict[str, Any]) -> float:
    if issue.weight is not None:
        return float(issue.weight)
    for pattern, value in (policy.get("weights") or {}).items():
        if fnmatch(issue.code, str(pattern)):
            return float(value)
    return float((policy.get("severity_weights") or {}).get(issue.severity, 1.0))


def is_hard(issue: Issue, policy: dict[str, Any]) -> bool:
    if issue.hard:
        return True
    return any(fnmatch(issue.code, str(p)) for p in policy.get("hard_fail_codes", []))


def issue_fingerprint(issue: Issue) -> tuple[Any, ...]:
    return (issue.code, issue.source, issue.paragraph, issue.line, issue.column, issue.message)


def unique_issues(issues: Iterable[Issue]) -> list[Issue]:
    seen: set[tuple[Any, ...]] = set()
    out: list[Issue] = []
    for issue in issues:
        fp = issue_fingerprint(issue)
        if fp in seen:
            continue
        seen.add(fp)
        out.append(issue)
    return out
