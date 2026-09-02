# Deterministic Repair State Machine

## Goal

The runtime must never ask an LLM to decide whether it should keep trying. It measures the candidate, chooses the next state with fixed rules, validates the model response before mutation, and stops after finite budgets.

## State transition

```text
candidate
   |
   v
quality gate
   |
   +-- PASS ------------------------------> accept
   |
   +-- FAIL
         |
         +-- rewrite budget + progress ---> rewrite
         |                                  |
         |                                  v
         |                             response contract
         |                                  |
         |                      invalid -----+----> reject, no manuscript mutation
         |                                  |
         |                                valid
         |                                  |
         |                                  v
         |                              candidate
         |
         +-- no progress / budget ----------> salvage
                                               |
                                               v
                                      localized evidence
                                               |
                                      expand context radius
                                               |
                             cull fraction too large? --yes--> human_review
                                               |
                                              no
                                               v
                                    freeze good paragraphs
                                               |
                                    create exact named gaps
                                               |
                                      model fills gaps
                                               |
                                      response contract
                                               |
                                  invalid -----+----> reject
                                               |
                                             valid
                                               |
                                               v
                                      software reassembly
                                               |
                                               v
                                           candidate
                                               |
                                  salvage budget exhausted
                                               |
                                               v
                                         human_review
```

Defaults live in `config/gate_policy.yaml`:

- 2 full rewrite attempts maximum;
- 1 salvage attempt maximum;
- 7 suspicion points local paragraph cull threshold;
- 1 paragraph of situational context culled on each side;
- salvage is refused if more than 50% of paragraphs would be removed.

These are policy values, not hidden code constants.

## Evidence classes

### Hard truth / contract failures

Examples:

- `canon.unrevealed_reference`
- malformed rewrite/gap output (`contract.*` conceptually)

A hard failure can fail the gate regardless of aggregate suspicion.

### Objective or near-objective mechanical findings

Examples:

- repeated words;
- spelling/terminology errors;
- duplicate paragraphs;
- malformed articles/acronyms;
- extreme localized token bursts;
- parse/readability anomalies relative to an approved corpus.

These contribute weighted evidence.

### Style sensors

Examples:

- passive voice;
- adverb density;
- em-dash density;
- AiTells patterns;
- `write-good` suggestions.

These must not become universal fiction rules. Their weights remain low unless repeated, corpus-abnormal, or independently corroborated.

## Consensus without double-counting

Multiple tools frequently report the same underlying behavior. `QualityGate` groups evidence by paragraph and family. Within a family, the strongest independent source supplies the base score and additional sources add only a bounded consensus bonus.

This prevents “Vale says passive + retext says passive” from being counted as two full defects while preserving the useful fact that independent mechanisms agree.

## Situational salvage

A detector usually points to a sentence or paragraph. A writing failure often contaminates the scene around it. Salvage therefore does not simply remove the offending sentence.

For every contaminated paragraph:

1. expand by `context_cull_radius`;
2. merge overlapping ranges into a gap;
3. preserve the immediately preceding/following good paragraphs as immutable anchors;
4. include removed material only as evidence of intended situation, not wording to preserve;
5. attach localized diagnoses and forbidden unrevealed canon phrases;
6. request replacement prose for the named gap only;
7. validate exact gap IDs and forbid all outside commentary;
8. software-reassemble the immutable anchors and replacement.

This is an explicit Occam's-razor fallback: when repeated model attempts cannot rescue a contaminated situation, remove the smallest bounded region likely to contain the bad causal/prose structure and regenerate only that region.

## Whole-rewrite response contract

A valid response has exactly:

```text
<<<WRITING_RUNTIME_REWRITE>>>
<chapter prose>
<<<END_WRITING_RUNTIME_REWRITE>>>
```

The contract rejects:

- missing/duplicate sentinels;
- anything outside the sentinels;
- empty payloads;
- responses outside configured word-count ratios;
- common plan/meta fingerprints;
- list-dominant output.

Importantly, `rewrite-apply` writes a candidate only after validation succeeds. The original manuscript is never overwritten by the validator.

## Gap response contract

Every expected gap must occur exactly once:

```text
<<<WRITING_RUNTIME_GAP G001>>>
<replacement prose>
<<<END WRITING_RUNTIME_GAP ...>>>
```

(The actual end sentinel emitted by the runtime is `<<<END_WRITING_RUNTIME_GAP G001>>>`.) No unrequested IDs, duplicates, missing gaps, empty gaps, plans, or outside commentary can enter reassembly.

## Progress detection

`repair_state_transition` fingerprints the deterministic evidence state. If a rewrite does not reduce suspicion and does not reduce hard failures, it is considered no progress and the loop escalates rather than burning the remaining full-rewrite budget indefinitely.

After the configured salvage budget, the state is `human_review`. There is intentionally no “try again forever” branch.
