from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from hashlib import sha256
import json
import tempfile
from typing import Any
import yaml

from .canon import CanonLibrary
from .evidence import GateReport, Issue, ToolStatus, is_hard, issue_weight, paragraph_line_ranges, paragraph_for_line, unique_issues
from .external_tools import run_cspell, run_languagetool, run_plain_english, run_retext, run_slopless, run_vale
from .nlp_tools import optional_language_metrics
from .prose import ProseAnalyzer, load_profile
from .planning import load_plan
from .textutil import words


STOPWORDS = {
    'about','after','again','against','all','also','and','any','are','because','been','before','being','between',
    'both','but','can','could','did','does','doing','down','each','even','for','from','had','has','have','her','here',
    'hers','him','his','how','into','its','just','more','most','not','now','off','once','only','other','our','out','over',
    'same','she','should','some','such','than','that','the','their','them','then','there','these','they','this','those',
    'through','too','under','until','upon','very','was','were','what','when','where','which','while','who','will','with',
    'would','you','your','said','says','say','one','two','three','like','back','still','though','then','than',
}


def load_policy(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        path = Path(__file__).parents[1] / 'config' / 'gate_policy.yaml'
    data = yaml.safe_load(Path(path).read_text(encoding='utf-8')) or {}
    if not isinstance(data, dict):
        raise ValueError('gate policy must be a mapping')
    return data


def _word_bursts(text: str, policy: dict[str, Any]) -> list[Issue]:
    cfg = policy.get('lexical_burst') or {}
    min_count = int(cfg.get('min_count', 10))
    min_per_1k = float(cfg.get('min_per_1k', 4.0))
    min_len = int(cfg.get('min_word_length', 4))
    toks = [w.lower().replace('’', "'") for w in words(text)]
    counts = Counter(toks)
    n = max(1, len(toks))
    paragraphs = paragraph_line_ranges(text)
    issues: list[Issue] = []
    allowed = {str(x).lower() for x in cfg.get('allow', [])}
    for token, count in counts.most_common():
        if token in STOPWORDS or token in allowed or len(token) < min_len:
            continue
        per1k = count / n * 1000
        if count < min_count or per1k < min_per_1k:
            continue
        para_counts = []
        for pidx, start, _end, ptext in paragraphs:
            pc = sum(w.lower().replace('’', "'") == token for w in words(ptext))
            if pc:
                para_counts.append((pidx, start, pc))
        concentration = max((pc for _, _, pc in para_counts), default=0) / count
        for pidx, start, pc in para_counts:
            # Scale localized suspicion with actual absurdity, but cap it: repetition is
            # evidence, not a universal literary law. A pathological 20x token in one
            # paragraph can trigger salvage; a name recurring twice per paragraph cannot.
            base = float((policy.get('weights') or {}).get('lexical.word_burst', 1.75))
            local_weight = min(7.5, base + max(0, pc - 2) * 0.75 + max(0.0, per1k - min_per_1k) / 25.0)
            issues.append(Issue(
                code='lexical.word_burst', source='runtime', severity='warning', family='repetition',
                message=f"'{token}' occurs {count} times ({per1k:.1f}/1k words); {pc} occurrence(s) in this paragraph.",
                line=start, paragraph=pidx, weight=round(local_weight, 3),
                evidence={'token': token, 'chapter_count': count, 'per_1k': round(per1k, 3),
                          'paragraph_count': pc, 'max_paragraph_concentration': round(concentration, 3)},
            ))
    return issues



def _near_duplicate_paragraphs(text: str, policy: dict[str, Any]) -> tuple[list[Issue], ToolStatus]:
    cfg = policy.get('near_duplicate') or {}
    threshold = float(cfg.get('paragraph_similarity', 90.0))
    min_words = int(cfg.get('min_words', 12))
    max_pairs = int(cfg.get('max_pairs', 20))
    try:
        from rapidfuzz import fuzz
        import rapidfuzz
    except Exception as exc:
        return [], ToolStatus('rapidfuzz', False, detail=str(exc))
    paras = paragraph_line_ranges(text)
    normed = []
    for idx, start, _end, ptext in paras:
        if len(words(ptext)) < min_words:
            continue
        normed.append((idx, start, ' '.join(w.lower() for w in words(ptext))))
    pairs = []
    for i in range(len(normed)):
        p1, l1, a = normed[i]
        for j in range(i + 1, len(normed)):
            p2, l2, b = normed[j]
            score = float(fuzz.ratio(a, b))
            if score >= threshold:
                pairs.append((score, p1, l1, p2, l2))
    pairs.sort(key=lambda x: (-x[0], x[1], x[3]))
    issues: list[Issue] = []
    for score, p1, l1, p2, l2 in pairs[:max_pairs]:
        weight = min(5.0, 1.25 + max(0.0, score - threshold) / 4.0)
        message = f'Paragraphs {p1} and {p2} are {score:.1f}% lexically similar.'
        evidence = {'other_paragraph': p2, 'similarity': round(score, 3), 'threshold': threshold}
        issues.append(Issue(code='rapidfuzz.near_duplicate_paragraph', source='rapidfuzz', severity='warning',
                            family='repetition', message=message, line=l1, paragraph=p1,
                            weight=round(weight, 3), evidence=evidence))
        evidence2 = {'other_paragraph': p1, 'similarity': round(score, 3), 'threshold': threshold}
        issues.append(Issue(code='rapidfuzz.near_duplicate_paragraph', source='rapidfuzz', severity='warning',
                            family='repetition', message=message, line=l2, paragraph=p2,
                            weight=round(weight, 3), evidence=evidence2))
    return issues, ToolStatus('rapidfuzz', True, getattr(rapidfuzz, '__version__', 'installed'))

def _internal_prose_issues(text: str, profile: dict[str, Any] | None) -> tuple[list[Issue], dict[str, Any]]:
    report = ProseAnalyzer().analyze(text, profile)
    issues = [
        Issue(
            code=f"prose.{f['code']}", source='runtime', severity='warning' if f['severity'] == 'warn' else 'suggestion',
            family='style', message=f['message'], evidence={'metric': f.get('metric')},
        )
        for f in report.flags
    ]
    if report.profile_fit:
        for metric, detail in report.profile_fit.get('details', {}).items():
            if detail.get('status') == 'in_range':
                continue
            issues.append(Issue(
                code=f'profile.{metric}.{detail.get("status")}', source='profile', severity='suggestion', family='profile',
                message=f"{metric} is {detail.get('status')} versus the configured corpus band.",
                evidence=detail,
            ))
    return issues, report.as_dict()


def _canon_issues(text: str, library: CanonLibrary | None, viewpoint: str | None, at: str | None, branch: str = 'main') -> list[Issue]:
    if not library or not viewpoint or not at:
        return []
    out: list[Issue] = []
    for hit in library.disclosure_audit(text, viewpoint=viewpoint, at=at, branch=branch):
        for m in hit['matches']:
            out.append(Issue(
                code='canon.unrevealed_reference', source='canon', severity='error', hard=True, family='canon',
                message=(f"Reference to '{hit['title']}' uses trigger '{m['phrase']}' before any timed reveal "
                         f"to {viewpoint} at {at}."),
                line=m['line'], column=m['column'], paragraph=paragraph_for_line(text, m['line']),
                evidence={'entry_id': hit['id'], 'title': hit['title'], 'trigger': m['phrase'],
                          'fact_key': hit.get('fact_key'), 'audit_kind': hit.get('kind', 'entry'),
                          'disclosure_state': hit['disclosure_state'], 'viewpoint': viewpoint, 'at': at, 'branch': branch},
            ))
    return out


def _plan_prose_issues(text: str, plan_path: str | Path | None, *, viewpoint: str | None, at: str | None) -> list[Issue]:
    """Validate generated prose against explicit, mechanically testable plan obligations.

    This deliberately does not attempt semantic beat completion. Only literal obligations,
    forbidden terms, context identity, and aggregate word budgets are hard/mechanical here.
    """
    if not plan_path:
        return []
    plan = load_plan(plan_path)
    out: list[Issue] = []
    if viewpoint and viewpoint != plan.viewpoint:
        out.append(Issue(code='plan.prose_context_mismatch', source='plan', severity='error', hard=True,
                         family='plan', message='viewpoint does not match validated chapter plan',
                         evidence={'expected':plan.viewpoint,'actual':viewpoint,'field':'viewpoint'}))
    if at and at != plan.timeline_key:
        out.append(Issue(code='plan.prose_context_mismatch', source='plan', severity='error', hard=True,
                         family='plan', message='timeline point does not match validated chapter plan',
                         evidence={'expected':plan.timeline_key,'actual':at,'field':'timeline_key'}))
    low = text.casefold()
    for scene in plan.scenes:
        for beat in scene.beats:
            for term in beat.required_terms:
                if term.casefold() not in low:
                    out.append(Issue(code='plan.prose_missing_required_term', source='plan', severity='error', hard=True,
                                     family='plan', message='required literal plan term is absent',
                                     evidence={'scene_id':scene.id,'beat_id':beat.id,'term':term}))
            for term in beat.forbidden_terms:
                start=0
                t=term.casefold()
                while t and (idx:=low.find(t,start)) >= 0:
                    line=text.count('\n',0,idx)+1
                    out.append(Issue(code='plan.prose_forbidden_term', source='plan', severity='error', hard=True,
                                     family='plan', message='forbidden literal plan term is present', line=line,
                                     paragraph=paragraph_for_line(text,line),
                                     evidence={'scene_id':scene.id,'beat_id':beat.id,'term':term}))
                    start=idx+max(1,len(t))
    mins=[s.target_words_min for s in plan.scenes]
    maxs=[s.target_words_max for s in plan.scenes]
    wc=len(words(text))
    if mins and all(x is not None for x in mins):
        floor=sum(int(x) for x in mins if x is not None)
        if wc < floor:
            out.append(Issue(code='plan.prose_word_budget_low', source='plan', severity='warning', family='plan',
                             message='chapter is below the aggregate validated scene minimum',
                             evidence={'words':wc,'minimum':floor}))
    if maxs and all(x is not None for x in maxs):
        ceiling=sum(int(x) for x in maxs if x is not None)
        if wc > ceiling:
            out.append(Issue(code='plan.prose_word_budget_high', source='plan', severity='warning', family='plan',
                             message='chapter exceeds the aggregate validated scene maximum',
                             evidence={'words':wc,'maximum':ceiling}))
    return out




def _plan_echo_issues(text: str, plan_path: str | Path | None, policy: dict[str, Any]) -> list[Issue]:
    """Detect verbatim plan-language leakage into prose.

    This is intentionally lexical, not semantic. It catches the one-model failure mode where
    the model copies its own planning directives into narration instead of transforming them.
    """
    if not plan_path:
        return []
    cfg=policy.get('plan_echo') or {}
    min_words=int(cfg.get('min_phrase_words',8))
    max_findings=int(cfg.get('max_findings',16))
    if min_words < 4: min_words=4
    plan=load_plan(plan_path)
    sources=[]
    sources.append(('chapter.writer_goal',None,None,plan.writer_goal))
    for scene in plan.scenes:
        sources.append((f'scene.{scene.id}.writer_goal',scene.id,None,scene.writer_goal))
        for beat in scene.beats:
            sources.append((f'beat.{beat.id}.writer_directive',scene.id,beat.id,beat.writer_directive))
    paras=paragraph_line_ranges(text)
    findings=[]
    seen=set()
    for label,sid,bid,src in sources:
        stoks=[w.casefold().replace('’',"'") for w in words(src)]
        if len(stoks)<min_words:
            continue
        # Exact minimum-length windows are enough to prove copying; report at most one
        # match per plan field/paragraph to avoid charging overlapping windows repeatedly.
        grams={' '.join(stoks[i:i+min_words]) for i in range(len(stoks)-min_words+1)}
        for pidx,start,_end,ptext in paras:
            ptoks=[w.casefold().replace('’',"'") for w in words(ptext)]
            if len(ptoks)<min_words:
                continue
            pgrams={' '.join(ptoks[i:i+min_words]) for i in range(len(ptoks)-min_words+1)}
            overlap=sorted(grams & pgrams)
            if not overlap:
                continue
            key=(label,pidx)
            if key in seen:
                continue
            seen.add(key)
            phrase=overlap[0]
            findings.append(Issue(
                code='plan.prose_plan_echo',source='plan',severity='warning',family='plan',
                message='prose copies a long exact phrase from writer-facing plan language',
                line=start,paragraph=pidx,weight=float((policy.get('weights') or {}).get('plan.prose_plan_echo',2.0)),
                evidence={'plan_field':label,'scene_id':sid,'beat_id':bid,'phrase_words':min_words,
                          'phrase_sha256':sha256(phrase.encode()).hexdigest()[:16]},
            ))
            if len(findings)>=max_findings:
                return findings
    return findings

def _attach_provenance(issues: list[Issue], text: str, provenance_path: str | Path | None) -> tuple[list[Issue], ToolStatus | None]:
    if not provenance_path:
        return issues, None
    p=Path(provenance_path)
    if not p.exists():
        return issues, ToolStatus('provenance', False, detail=f'missing {p}')
    try:
        data=json.loads(p.read_text(encoding='utf-8'))
    except Exception as exc:
        return issues, ToolStatus('provenance', False, detail=f'invalid JSON: {exc}')
    actual=sha256(text.encode('utf-8')).hexdigest()
    if data.get('chapter_sha256') != actual:
        return issues, ToolStatus('provenance', False, detail='stale: chapter SHA-256 does not match')
    ranges=[]
    for scene in data.get('scenes',[]):
        for beat in scene.get('beats',[]):
            ranges.append((int(beat['paragraph_start']),int(beat['paragraph_end']),scene.get('scene_id'),beat.get('beat_id')))
    out=[]
    for issue in issues:
        evidence=dict(issue.evidence or {})
        if issue.paragraph:
            for start,end,sid,bid in ranges:
                if start <= issue.paragraph <= end:
                    evidence.setdefault('scene_id',sid); evidence.setdefault('beat_id',bid); break
        out.append(replace(issue,evidence=evidence))
    return out, ToolStatus('provenance', True, 'hash-bound scene/beat map')


def _consensus_scores(issues: list[Issue], policy: dict[str, Any]) -> tuple[float, dict[int, float], list[str]]:
    """Score evidence without double charging duplicate independent linters.

    Same-family findings in the same paragraph are grouped: maximum base weight plus
    a bounded bonus for independent sources. Distinct findings from one source remain
    additive only when their codes differ. Hard failures are always counted separately.
    """
    chapter_score = 0.0
    paragraph_scores: dict[int, float] = defaultdict(float)
    rationale: list[str] = []
    groups: dict[tuple[int | None, str], list[Issue]] = defaultdict(list)
    hard_seen: set[tuple[str, int | None, str]] = set()
    for issue in issues:
        if is_hard(issue, policy):
            key = (issue.code, issue.paragraph, str(issue.evidence.get('entry_id', '')))
            if key in hard_seen:
                continue
            hard_seen.add(key)
            w = issue_weight(issue, policy)
            chapter_score += w
            if issue.paragraph:
                paragraph_scores[issue.paragraph] += w
            rationale.append(f"hard {issue.code}: +{w:g}")
        else:
            groups[(issue.paragraph, issue.family)].append(issue)

    bonus = float(policy.get('consensus_bonus_per_extra_source', 0.75))
    cap = float(policy.get('consensus_bonus_cap', 2.0))
    for (paragraph, family), group in groups.items():
        # Preserve independent concrete findings from a single source, but stop Vale +
        # retext from counting the same passive/repetition signal twice at full weight.
        by_source: dict[str, list[Issue]] = defaultdict(list)
        for issue in group:
            by_source[issue.source].append(issue)
        source_scores = []
        for source, src_issues in by_source.items():
            unique_codes = {}
            for issue in src_issues:
                unique_codes[issue.code] = max(unique_codes.get(issue.code, 0.0), issue_weight(issue, policy))
            source_scores.append(sum(unique_codes.values()))
        if not source_scores:
            continue
        base = max(source_scores)
        extra = min(cap, max(0, len(source_scores) - 1) * bonus)
        score = base + extra
        chapter_score += score
        if paragraph:
            paragraph_scores[paragraph] += score
        if len(source_scores) > 1:
            rationale.append(f"consensus p{paragraph or '-'} {family}: {len(source_scores)} sources -> +{score:.2f}")
    return round(chapter_score, 3), {k: round(v, 3) for k, v in paragraph_scores.items()}, rationale


class QualityGate:
    def __init__(self, *, root: str | Path, policy: dict[str, Any] | None = None):
        self.root = Path(root)
        self.policy = policy or load_policy(None)

    def analyze(
        self,
        text: str,
        *,
        source_path: str | Path | None = None,
        canon_library: str | Path | None = None,
        viewpoint: str | None = None,
        at: str | None = None,
        branch: str | None = None,
        profile_path: str | Path | None = None,
        chapter_plan: str | Path | None = None,
        provenance_path: str | Path | None = None,
        external: bool = True,
        advanced_nlp: bool = True,
    ) -> GateReport:
        profile = load_profile(profile_path) if profile_path else None
        issues, prose = _internal_prose_issues(text, profile)
        issues.extend(_word_bursts(text, self.policy))
        tools: list[ToolStatus] = []

        if branch is None and chapter_plan:
            try:
                branch = load_plan(chapter_plan).timeline_branch
            except Exception:
                branch = 'main'
        branch = branch or 'main'
        lib = CanonLibrary.load(canon_library) if canon_library else None
        try:
            issues.extend(_canon_issues(text, lib, viewpoint, at, branch))
        finally:
            if lib:
                lib.close()

        issues.extend(_plan_prose_issues(text, chapter_plan, viewpoint=viewpoint, at=at))
        issues.extend(_plan_echo_issues(text, chapter_plan, self.policy))

        metrics: dict[str, Any] = {'prose': prose}
        if advanced_nlp:
            duplicate_issues, duplicate_status = _near_duplicate_paragraphs(text, self.policy)
            issues.extend(duplicate_issues); tools.append(duplicate_status)
            language_metrics, language_status = optional_language_metrics(text)
            metrics['language'] = language_metrics
            tools.extend(language_status)

        temp: tempfile.NamedTemporaryFile | None = None
        if source_path is None:
            temp = tempfile.NamedTemporaryFile('w', suffix='.txt', encoding='utf-8', delete=False)
            temp.write(text); temp.close()
            path = Path(temp.name)
        else:
            path = Path(source_path)

        try:
            if external:
                for runner in (run_retext, run_cspell, run_vale, run_plain_english, run_slopless, run_languagetool):
                    found, status = runner(path, self.root, text)
                    issues.extend(found); tools.append(status)
        finally:
            if temp:
                Path(temp.name).unlink(missing_ok=True)

        issues, provenance_status = _attach_provenance(issues, text, provenance_path)
        if provenance_status: tools.append(provenance_status)
        issues = unique_issues(issues)
        score, paragraph_scores, rationale = _consensus_scores(issues, self.policy)
        hard_count = sum(is_hard(i, self.policy) for i in issues)
        threshold = float(self.policy.get('chapter_suspicion_threshold', 24.0))
        para_threshold = float(self.policy.get('paragraph_suspicion_threshold', 7.0))
        contaminated = sorted(p for p, v in paragraph_scores.items() if v >= para_threshold)
        passed = hard_count == 0 and score <= threshold
        return GateReport(
            passed=passed, hard_failures=hard_count, suspicion_score=score, threshold=threshold,
            issues=issues, paragraph_scores=paragraph_scores, contaminated_paragraphs=contaminated,
            metrics=metrics, tools=tools, rationale=rationale,
        )
