# Disclosure epochs

## Why they exist

A beat-local validator can catch a secret mentioned too early, but a monolithic chapter prompt may already have shown the model a later reveal. With one model reused for all phases, prevention is stronger than asking the same weights not to use information already present in their context.

A **disclosure epoch** is a contiguous run of beats generated under one fixed viewpoint-knowledge state. When a protected fact first becomes available at the chapter's timeline point and the plan assigns that fact to a `reveal_facts` beat, the runtime creates a new epoch beginning at that beat.

```text
E001: B001 B002       fact X absent from packet
                      fresh call ends

E002: B003 B004 B005  fact X unlocked at B003
                      fresh call ends

E003: B006 ...        fact X + fact Y unlocked at B006
```

The model binary/weights may be identical for every epoch. The isolation boundary is the inference/chat context, not model identity.

## Compiler rules

1. Canon remains authoritative about whether the fact may be disclosed in this chapter.
2. `reveal_facts` assigns the within-chapter beat boundary.
3. A fact whose first canon reveal ordinal equals the chapter ordinal is considered a current-chapter scheduled disclosure unless it was already available before that ordinal.
4. Literal fact triggers in chapter/scene/beat writer-facing fields *before* the assigned reveal beat are a hard `plan.future_reveal_priming` error.
5. Pre-reveal epoch packets remove scheduled future facts from POV-safe canon payloads, including fact values and fact-keyed knowledge/reveal records.
6. The reveal epoch receives the newly unlocked fact explicitly as `epoch_unlocked_facts`.
7. Literal future-fact triggers are retained privately in the epoch manifest so response validation can reject leakage without priming the model with the forbidden strings.
8. `draft-prompt` refuses a plan requiring more than one epoch. Use `draft-epochs` instead.
9. Multi-epoch generation requires `fresh_call`. A persistent conversation is refused because later unlocked knowledge would contaminate any subsequent repair of earlier prose.

## CLI

Compile prompts:

```powershell
python write_runtime.py draft-epochs .runtime/plan.json `
  --library canon/canon.sqlite3 `
  --state-library state/story_state.sqlite3 `
  --context-mode fresh_call `
  --out-dir .runtime/epochs `
  --manifest-out .runtime/epochs.json `
  --json
```

For each manifest row, run the same model in a **new empty context** against `E###.prompt.txt` and save the exact response as:

```text
.runtime/epoch-responses/E001.response.txt
.runtime/epoch-responses/E002.response.txt
...
```

Then validate and assemble:

```powershell
python write_runtime.py draft-epochs-apply `
  --plan .runtime/plan.json `
  --manifest .runtime/epochs.json `
  --responses-dir .runtime/epoch-responses `
  --library canon/canon.sqlite3 `
  --out .runtime/chapter.txt `
  --provenance-out .runtime/chapter.provenance.json `
  --json
```

Software, not the model, reassembles beat outputs in canonical plan order and rechecks scene word budgets.

## Hard limit

The runtime can mechanically isolate configured/literal protected facts and explicit reveal boundaries. It cannot prove that an unrestricted semantic implication is equivalent to a hidden fact unless that implication has been encoded as a protected trigger/constraint. Critical secrets therefore need authored fact-level triggers or another explicit deterministic representation.
