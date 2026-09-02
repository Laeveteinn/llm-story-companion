# Hostile Review v0.4 — Planning and Reinjection

## Failures found in v0.3

1. **Planning was still privileged prose.** A plan could contain structurally impossible events while appearing plausible to an LLM reviewer.
2. **Chapter/scene writer goals were not disclosure-audited.** Beat directives were protected, but higher-level writer fields could leak secrets downstream.
3. **Raw diagnostic prose crossed into repair prompts.** A linter message or echoed source fragment could become accidental instruction text.
4. **Secret source text crossed into the next writer attempt.** Hiding the diagnostic wording did not help if the failed paragraph itself repeated the protected fact.
5. **Narrative continuity had no executable state.** Location, inventory, injury, possession, and similar facts could only be remembered textually.
6. **Plan repair had no nonlocal bounded fallback.** A bad chapter/scene goal could force immediate human review because only beat-local surgery existed.
7. **Plan-to-prose conformance was mostly aesthetic.** Explicit literal obligations/forbidden terms were not part of the chapter quality gate.

## Corrections

- Added strict Pydantic `ChapterPlan` IR with `extra=forbid`.
- Added NetworkX-backed dependency DAG validation with deterministic DFS fallback.
- Added replayable SQLite narrative-state events and invariants.
- Added author-scope planning context and a separate writer-surface compiler.
- Disclosure-audit every field that can cross to the prose writer.
- Added fixed diagnostic lowering; raw tool messages never reinject.
- Redact unrevealed literal canon from failed source material before prose repair.
- Added hard plan/prose obligations for required terms, forbidden terms, and viewpoint/timeline context.
- Added bounded plan surgery plus a single whole-plan recompile before `human_review`.
- Added plan smells for duplicate directives, forward dependencies, missing viewpoint participation, thread misuse, and no-op state effects.

## Remaining hard problem

Semantic beat completion is not yet objectively decidable from unrestricted prose. The runtime can prove explicit state/literal/canon violations, but it cannot prove that prose emotionally or semantically accomplished a beat merely because no forbidden phrase appears.

The next defensible improvement is provenance: retain scene/beat transport boundaries long enough to map later paragraph findings back to the exact plan region. This improves localization without pretending a semantic classifier is deterministic truth.
