from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import re

from .contracts import GAP_END_TEMPLATE, parse_gap_response, rewrite_contract_prompt, validate_rewrite_response
from .evidence import GateReport, Issue, paragraph_line_ranges
from .reinjection import directive_for_issue
from .textutil import words


@dataclass(frozen=True)
class Gap:
    id: str
    paragraphs: tuple[int, ...]
    before_anchor: str
    removed_text: str
    after_anchor: str
    diagnoses: tuple[str, ...]
    forbidden_canon: tuple[str, ...]

    def as_dict(self):
        return asdict(self)


@dataclass
class SalvagePlan:
    source_sha256: str
    gaps: list[Gap]
    template: str
    culled_paragraphs: list[int]
    cull_fraction: float
    abort: bool = False
    abort_reason: str | None = None

    def as_dict(self):
        return {
            'source_sha256': self.source_sha256,
            'gaps': [g.as_dict() for g in self.gaps],
            'template': self.template,
            'culled_paragraphs': self.culled_paragraphs,
            'cull_fraction': self.cull_fraction,
            'abort': self.abort,
            'abort_reason': self.abort_reason,
        }


def _clusters(indices: list[int]) -> list[list[int]]:
    if not indices:
        return []
    out = [[indices[0]]]
    for value in indices[1:]:
        if value == out[-1][-1] + 1:
            out[-1].append(value)
        else:
            out.append([value])
    return out


def make_salvage_plan(text: str, report: GateReport, policy: dict[str, Any]) -> SalvagePlan:
    paras = paragraph_line_ranges(text)
    total = len(paras)
    if total == 0:
        return SalvagePlan(sha256(text.encode()).hexdigest(), [], text, [], 0.0, True, 'no paragraphs')
    cfg = policy.get('salvage') or {}
    cut_threshold = float(cfg.get('paragraph_cut_threshold', policy.get('paragraph_suspicion_threshold', 7.0)))
    radius = int(cfg.get('context_cull_radius', 1))
    max_fraction = float(cfg.get('max_cull_fraction', 0.50))

    bad = {p for p, score in report.paragraph_scores.items() if score >= cut_threshold}
    # Every paragraph with a hard issue is contaminated regardless of numeric score.
    bad.update(i.paragraph for i in report.issues if i.hard and i.paragraph)
    source_hash = sha256(text.encode('utf-8')).hexdigest()
    if not bad:
        return SalvagePlan(source_hash, [], text, [], 0.0, True, 'no localized contaminated paragraphs')
    culled=[]; fraction=1.0; chosen_radius=radius
    # Occam context is valuable, but collateral damage is bounded. Shrink the radius
    # deterministically before refusing salvage altogether.
    for try_radius in range(radius, -1, -1):
        expanded=set()
        for p in bad:
            expanded.update(range(max(1, p - try_radius), min(total, p + try_radius) + 1))
        candidate=sorted(expanded); candidate_fraction=len(candidate)/total
        culled=candidate; fraction=candidate_fraction; chosen_radius=try_radius
        if candidate_fraction <= max_fraction:
            break
    if fraction > max_fraction:
        return SalvagePlan(source_hash, [], text, culled, round(fraction, 4), True,
                           f'cull fraction {fraction:.1%} exceeds configured maximum {max_fraction:.1%} even at radius 0')

    para_text = {idx: ptext for idx, _s, _e, ptext in paras}
    issues_by_para: dict[int, list[Issue]] = {}
    for issue in report.issues:
        if issue.paragraph:
            issues_by_para.setdefault(issue.paragraph, []).append(issue)

    gaps: list[Gap] = []
    replacement: dict[int, str] = {}
    for gi, cluster in enumerate(_clusters(culled), 1):
        gid = f'G{gi:03d}'
        start, end = cluster[0], cluster[-1]
        diagnoses = []
        forbidden = set()
        for p in cluster:
            for issue in issues_by_para.get(p, []):
                diagnoses.append(f"{issue.code}: {directive_for_issue(issue).instruction}")
                if issue.code == 'canon.unrevealed_reference':
                    # Redact only the literal phrase that proved the leak. The parent entity/title may
                    # already be known (partial disclosure), and over-redacting it destroys useful context.
                    value = issue.evidence.get('trigger')
                    if value:
                        forbidden.add(str(value))
        # Unique, stable order.
        diagnoses = list(dict.fromkeys(diagnoses))
        gap = Gap(
            id=gid,
            paragraphs=tuple(cluster),
            before_anchor=para_text.get(start - 1, ''),
            removed_text='\n\n'.join(para_text[p] for p in cluster),
            after_anchor=para_text.get(end + 1, ''),
            diagnoses=tuple(diagnoses),
            forbidden_canon=tuple(sorted(forbidden)),
        )
        gaps.append(gap)
        replacement[start] = f'<<<WRITING_RUNTIME_SLOT {gid}>>>'
        for p in cluster[1:]:
            replacement[p] = ''

    template_parts = []
    for idx, _s, _e, ptext in paras:
        if idx in replacement:
            if replacement[idx]:
                template_parts.append(replacement[idx])
        else:
            template_parts.append(ptext)
    template = '\n\n'.join(template_parts)
    return SalvagePlan(source_hash, gaps, template, culled, round(fraction, 4))


def _redact_private_phrases(text: str, phrases: tuple[str, ...]) -> str:
    out = text
    for phrase in sorted((p for p in phrases if p), key=len, reverse=True):
        out = re.sub(re.escape(phrase), '[REDACTED_UNREVEALED_CANON]', out, flags=re.IGNORECASE)
    return out


def salvage_prompt(plan: SalvagePlan, *, global_constraints: str = '') -> str:
    if plan.abort:
        raise ValueError(f'cannot prompt aborted salvage plan: {plan.abort_reason}')
    blocks = []
    for gap in plan.gaps:
        diagnoses = '\n'.join(f'- {x}' for x in gap.diagnoses) or '- contaminated by chapter-level gate'
        forbidden = str(len(gap.forbidden_canon)) + ' protected trigger(s) are held privately by the validator; their wording is intentionally not injected.'
        before = _redact_private_phrases(gap.before_anchor, gap.forbidden_canon)
        removed = _redact_private_phrases(gap.removed_text, gap.forbidden_canon)
        after = _redact_private_phrases(gap.after_anchor, gap.forbidden_canon)
        blocks.append(f"""GAP {gap.id}
IMMUTABLE PRECEDING ANCHOR:
{before or '[chapter start]'}

REMOVED MATERIAL (use only to understand intended situation; do not preserve its wording or mistakes):
{removed}

IMMUTABLE FOLLOWING ANCHOR:
{after or '[chapter end]'}

DETERMINISTIC DIAGNOSIS:
{diagnoses}

FORBIDDEN UNREVEALED CANON REFERENCES:
{forbidden}
""")
    gap_contract = '\n'.join(
        f"<<<WRITING_RUNTIME_GAP {g.id}>>>\n<replacement prose for {g.id}>\n{GAP_END_TEMPLATE.format(gap_id=g.id)}"
        for g in plan.gaps
    )
    return f"""You are repairing specific holes in a fiction chapter. Untouched paragraphs are immutable and will be reassembled by software; you are not allowed to rewrite them.

GLOBAL CONSTRAINTS
{global_constraints.strip() or '(none beyond the deterministic diagnoses below)'}

The removed text may have damaged an entire situation. Repair causality, continuity, character intent, transitions, and local scene logic across each gap; do not merely delete the sentence that tripped a detector. Respect the immutable before/after anchors.

{chr(10).join(blocks)}
OUTPUT CONTRACT
Return every requested gap exactly once, no additional text, no analysis, no plan, no Markdown fences:
{gap_contract}
"""


def apply_gap_response(plan: SalvagePlan, response: str) -> tuple[str | None, dict[str, Any]]:
    result = parse_gap_response(response, [g.id for g in plan.gaps])
    if not result.valid or result.gaps is None:
        return None, result.as_dict()
    text = plan.template
    for gap in plan.gaps:
        text = text.replace(f'<<<WRITING_RUNTIME_SLOT {gap.id}>>>', result.gaps[gap.id])
    return text, result.as_dict()


def repair_state_transition(
    state: dict[str, Any] | None,
    *,
    report: GateReport,
    candidate_text: str,
    policy: dict[str, Any],
    context_mode: str = 'fresh_call',
) -> dict[str, Any]:
    """Pure deterministic bounded-loop transition; no model invocation occurs here."""
    cfg = policy.get('repair') or {}
    max_attempts = int(cfg.get('max_full_rewrite_attempts', 2))
    max_salvage = int(cfg.get('max_salvage_attempts', 1))
    if str(context_mode).replace('-', '_') == 'persistent_safe':
        max_attempts = min(max_attempts, int(cfg.get('persistent_max_full_rewrite_attempts', 1)))
        max_salvage = min(max_salvage, int(cfg.get('persistent_max_salvage_attempts', 1)))
    state = dict(state or {})
    state.setdefault('full_rewrite_attempts', 0)
    state.setdefault('salvage_attempts', 0)
    state.setdefault('history', [])
    fp = sha256(json.dumps({
        'hard': report.hard_failures,
        'score': report.suspicion_score,
        'contaminated': report.contaminated_paragraphs,
        'codes': sorted(i.code for i in report.issues),
    }, sort_keys=True).encode()).hexdigest()[:16]
    candidate_sha=sha256(candidate_text.encode('utf-8')).hexdigest()
    prior_fps={str(x.get('fingerprint')) for x in state['history']}
    prior_candidates={str(x.get('candidate_sha256')) for x in state['history']}
    cycle_detected=fp in prior_fps or candidate_sha in prior_candidates
    state['history'].append({'fingerprint': fp, 'score': report.suspicion_score, 'hard': report.hard_failures,
                             'candidate_sha256': candidate_sha})
    if cycle_detected: state['cycle_detected']=True
    if report.passed:
        state['action'] = 'accept'
        state['done'] = True
        return state

    previous = state['history'][-2] if len(state['history']) >= 2 else None
    no_progress = bool(previous and report.suspicion_score >= float(previous['score']) and report.hard_failures >= int(previous['hard'])) or cycle_detected
    if state['full_rewrite_attempts'] < max_attempts and not no_progress:
        state['full_rewrite_attempts'] += 1
        state['action'] = 'rewrite'
        state['done'] = False
        return state
    if state['salvage_attempts'] < max_salvage:
        state['salvage_attempts'] += 1
        plan = make_salvage_plan(candidate_text, report, policy)
        state['salvage_plan'] = plan.as_dict()
        if plan.abort:
            state['action'] = 'human_review'
            state['done'] = True
            state['reason'] = f'salvage refused: {plan.abort_reason}'
            return state
        state['action'] = 'salvage'
        state['done'] = False
        return state
    state['action'] = 'human_review'
    state['done'] = True
    state['reason'] = 'bounded repair budget exhausted'
    return state


def salvage_plan_from_dict(data: dict[str, Any]) -> SalvagePlan:
    gaps = [Gap(
        id=g['id'],
        paragraphs=tuple(g.get('paragraphs', [])),
        before_anchor=g.get('before_anchor', ''),
        removed_text=g.get('removed_text', ''),
        after_anchor=g.get('after_anchor', ''),
        diagnoses=tuple(g.get('diagnoses', [])),
        forbidden_canon=tuple(g.get('forbidden_canon', [])),
    ) for g in data.get('gaps', [])]
    return SalvagePlan(
        source_sha256=data['source_sha256'], gaps=gaps, template=data.get('template', ''),
        culled_paragraphs=list(data.get('culled_paragraphs', [])),
        cull_fraction=float(data.get('cull_fraction', 0.0)),
        abort=bool(data.get('abort', False)), abort_reason=data.get('abort_reason'),
    )
