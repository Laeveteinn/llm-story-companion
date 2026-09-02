# Reinjection Firewall — v0.5

The repair loop treats reinjection as a security/compiler boundary.

## Rule 1: diagnostics are data, never instructions

External tools may emit arbitrary prose. Raw tool messages are stored in reports for humans but are never copied into model prompts.

Every issue code is lowered through an allowlisted deterministic template:

```text
Issue(code, location, typed evidence)
        |
        v
fixed directive template
```

Unknown issue codes receive a generic fixed instruction containing only the stable code and location.

## Rule 2: protected literal canon remains private

If a candidate contains unrevealed canon, the validator keeps the real trigger privately. Before a prose-repair model sees the failed manuscript, exact protected trigger phrases are replaced with:

```text
[REDACTED_UNREVEALED_CANON]
```

The original manuscript remains hash-bound and unchanged on disk. The candidate is re-audited against the private literal after generation.

The same redaction is applied to Occam salvage anchors and removed-material context. This prevents a bad chapter from teaching the next model the secret it is supposed to forget.

## Rule 3: plans are compiled, not forwarded

The prose writer never receives raw `ChapterPlan` JSON. `writer_plan_surface()` lowers only:

- plan/chapter/timeline/viewpoint identity;
- writer goals that passed disclosure checks;
- writer-safe state;
- POV-safe canon triggered by writer-facing plan text;
- scene participants;
- safe beat directives;
- required literal terms.

It excludes author intent, reveal IDs, forbidden literal terms, hidden mechanics, author-only state, and diagnostics.

## Rule 4: outputs are request-bound

Rewrite, plan, scene, and gap outputs use exact sentinels containing a request contract ID where appropriate. Responses with commentary, plans instead of prose, missing/duplicate blocks, Markdown fences, stale source hashes, wrong IDs, implausible word ratios, or material outside the transport blocks are rejected before touching manuscript state.

## Rule 5: software owns reassembly

In salvage mode the model fills only named holes. Untouched prose is immutable and reinserted by software. A salvage plan is SHA-256-bound to the exact source chapter.

## Rule 6: finite retries

Repeated equal-or-worse evidence is treated as no progress and accelerates escalation. Exhausted repair budgets become `human_review`; there is no `while critic_dislikes_text` loop.

## Provenance is hash-bound, not guessed

`draft-apply` strips transport markers but records scene/beat paragraph ranges and SHA-256 hashes. Later quality passes may attach those IDs to localized findings only when the provenance file's chapter hash exactly matches the current candidate. After a rewrite changes the chapter, the old map becomes unavailable rather than being approximately remapped.
