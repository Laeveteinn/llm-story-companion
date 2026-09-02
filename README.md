# Deterministic Writing Runtime

Current checkpoint: **v0.5.0**.

This project treats the LLM as an unreliable candidate generator behind deterministic stores, validators, contracts, and finite repair state machines. Planning, drafting, repair, and model-side orchestration may all use the **same underlying model**; phase names are not trust boundaries.

## v0.5 execution rule

- `fresh_call` (preferred): the same model/runtime may be reused, but every phase/attempt starts with an empty conversation/KV context and is discarded afterward. Author-only planning is allowed because later drafting cannot inherit that context.
- `persistent_safe` (degraded): one continuing context may be used only if hidden/author-only canon and state are withheld from every model prompt. Retry budgets are tighter.
- A persistent context that has already seen hidden author truth is considered contaminated for disclosure-sensitive writing. There is no prompt-based "forget it now" mode.

## Mechanical loop

`input -> compiled context -> model candidate -> deterministic review/evidence -> finite router -> safe reinjection -> model candidate -> gate`, with bounded whole rewrites, Occam-style localized culling/gap filling, cycle detection, strict response contracts, and final `human_review` cutoff.

## Disclosure epochs

When a fact is first revealed mid-chapter, monolithic drafting is refused. `draft-epochs` creates fresh-call generation packets whose knowledge increases monotonically; later facts are physically absent from earlier prompts. Software validates and reassembles epoch responses in canonical beat order.

## Validation

Local-only verification for this checkpoint: **46 pytest tests passed**, plus Python compileall, Node syntax check, and Bash syntax check. No GitHub Actions, hosted runner, CI, or GitHub compute was used.

## Snapshot

The exact downloadable v0.5.0 ZIP is SHA-256:

`6ce98fed16d344535861abcf3924e99e9463463c4418e3aa7f3ff046454d2343`

`SNAPSHOT_MANIFEST.json` records every packaged path and per-file SHA-256. The connected GitHub write API cannot ingest a local binary/directory reference, so this repo checkpoint stores the human-readable architecture/handoff plus the byte-level manifest; the full ZIP is the canonical source handoff from the ChatGPT artifact.
