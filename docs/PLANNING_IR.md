# Typed Planning IR and Narrative State — v0.5

The planning phase is not trusted prose. The same model may later write the chapter; its planning output is still an untrusted strict intermediate representation (IR) that must compile before any writer-facing packet exists.

## Boundary

```text
author brief
   |
   +--> exact canon trigger lookup (author scope)
   +--> narrative-state snapshot (author scope)
   |
planning phase (same model allowed; fresh context preferred)
   |
strict ChapterPlan JSON
   |
PlanGate
   +--> schema
   +--> timeline/canon IDs
   +--> disclosure firewall on every writer-facing field
   +--> scene/beat DAGs and forward references
   +--> state preconditions/effects/invariants
   +--> actor/participant consistency
   +--> required goals and thread ordering
   +--> duplicate-directive/no-op evidence
   |
accepted plan
   |
writer_plan_surface()
   |
writer-safe packet only
   |
writing phase (same model allowed)
```

`author_intent`, hidden fact IDs, forbidden literal terms, author-only state, mechanics, and plan diagnostics never cross `writer_plan_surface()`. This boundary only prevents prompt-level disclosure; strong isolation additionally requires a fresh model context between author-aware planning and writing. In `persistent_safe`, author-only inputs are withheld from planning too.

## Narrative state

`state/story_state.sqlite3` is a replayable event ledger, not a mutable blob. Events are ordered by canon timeline ordinal and sequence. Supported effects are:

- `set`, `unset`
- `add`, `remove`
- `inc`, `dec`

Supported conditions are:

- `eq`, `neq`
- `exists`, `not_exists`
- `contains`, `not_contains`
- `gte`, `lte`, `gt`, `lt`

Invariants can be active over timeline ranges. A plan is replayed beat by beat against a snapshot; state violations are hard failures.

State records default to author-only. A record must explicitly set `writer_safe: true` before it can appear in a prose-writer packet.

## Planning gates

Hard/mechanical examples:

- invalid schema or unknown timeline key;
- duplicate IDs;
- dependency cycle or dependency on a later scene/beat;
- failed state precondition or invariant;
- actor absent from scene participants;
- viewpoint omitted from a single-viewpoint scene;
- unknown canon/fact ID;
- unauthorized fact reveal;
- unrevealed canon in chapter/scene/beat writer-facing fields;
- required goal never advanced.

Evidence-only examples:

- near-duplicate beat directives;
- writer-directive bloat;
- no-op state effects;
- thread advancement/payoff without earlier setup;
- unusually dense authorized reveals.

## Bounded plan repair

The router has four states:

1. `accept`
2. `repair_beats` — Occam surgery on localized contaminated beat clusters
3. `rewrite_plan` — one bounded full recompile for nonlocal/no-progress structural contamination
4. `human_review`

The default policy permits two localized repairs and one full-plan recompile. It cannot recurse indefinitely.

Localized plan salvage preserves unaffected beats structurally. The model returns replacement beat JSON for exact request-bound gap IDs; software reassembles the plan and runs `PlanGate` again.

## Why not solve fiction with PDDL/Z3 yet?

The IR is intentionally compatible with later constraint-solver work, but current fiction semantics are not sufficiently formalized to justify forcing every beat into a symbolic planner. Use deterministic state replay and DAG validation where the ontology is real; add solver-backed constraints only when a domain rule can be expressed without pretending subjective story logic is formal truth.
