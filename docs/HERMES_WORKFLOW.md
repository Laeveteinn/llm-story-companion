# Hermes / CLI Workflow — v0.7

Hermes should act as an executor of runtime decisions, not as the authority deciding whether work is complete. The same underlying model may perform planning, drafting, and repair; those are phases, not independent agents.

## 0. Build deterministic stores

```powershell
python write_runtime.py canon-build canon_source --out canon/canon.sqlite3
python write_runtime.py state-build state_source --library canon/canon.sqlite3 --out state/story_state.sqlite3
python write_runtime.py canon-spell-dict --library canon/canon.sqlite3 --out config/canon-terms.txt
```

## 1. Compile an author brief to a plan request

```powershell
python write_runtime.py plan-prompt .\brief.txt `
  --plan-id book1.ch05 `
  --chapter-key book1/ch05 `
  --at book1/ch05 --branch main --viewpoint Mara `
  --library canon/canon.sqlite3 `
  --state-library state/story_state.sqlite3 `
  --context-mode fresh_call `
  --out .runtime/plan-prompt.txt `
  --manifest-out .runtime/plan-request.json
```

In `fresh_call`, this planning call may receive author-only canon/state and therefore MUST use a fresh model context that is discarded afterward. If Hermes cannot create fresh calls and must remain one conversation, use `--context-mode persistent_safe`; author-only runtime data will then be withheld.

## 2. Validate/extract the plan response

```powershell
python write_runtime.py plan-apply `
  --response .runtime/plan-model.txt `
  --manifest .runtime/plan-request.json `
  --out .runtime/plan.json

python write_runtime.py plan-check .runtime/plan.json `
  --library canon/canon.sqlite3 `
  --state-library state/story_state.sqlite3
```

If the plan fails, route mechanically:

```powershell
python write_runtime.py plan-repair-next .runtime/plan.json `
  --state .runtime/plan-repair-state.json `
  --library canon/canon.sqlite3 `
  --state-library state/story_state.sqlite3 `
  --salvage-out .runtime/plan-salvage.json `
  --prompt-out .runtime/plan-repair-prompt.txt `
  --manifest-out .runtime/plan-rewrite-request.json `
  --context-mode fresh_call `
  --json
```

Read the JSON `action`: `accept`, `repair_beats`, `rewrite_plan`, or `human_review`.

## 3. Lower accepted plan to writer-safe generation

First try the one-call compiler:

```powershell
python write_runtime.py draft-prompt .runtime/plan.json `
  --library canon/canon.sqlite3 `
  --state-library state/story_state.sqlite3 `
  --context-mode fresh_call `
  --out .runtime/draft-prompt.txt `
  --manifest-out .runtime/draft-request.json
```

If it succeeds, run that prompt in a fresh context and use `draft-apply` as before.

If it refuses because the chapter contains a within-chapter disclosure boundary, this is a safety decision, not an error to work around. Compile disclosure epochs:

```powershell
python write_runtime.py draft-epochs .runtime/plan.json `
  --library canon/canon.sqlite3 `
  --state-library state/story_state.sqlite3 `
  --context-mode fresh_call `
  --out-dir .runtime/epochs `
  --manifest-out .runtime/epochs.json `
  --json
```

For each manifest epoch, invoke the **same model in a new empty context** using `E###.prompt.txt`, then save the exact response as `.runtime/epoch-responses/E###.response.txt`.

Assemble only through software:

```powershell
python write_runtime.py draft-epochs-apply `
  --plan .runtime/plan.json `
  --manifest .runtime/epochs.json `
  --responses-dir .runtime/epoch-responses `
  --library canon/canon.sqlite3 `
  --out .runtime/chapter.txt `
  --json
```

Never concatenate epoch output manually or feed later-epoch material back into an earlier epoch.

## 4. Mechanical prose loop

```powershell
python write_runtime.py repair-next .runtime/chapter.txt `
  --state .runtime/prose-repair-state.json `
  --writer-plan .runtime/plan.json `
  --library canon/canon.sqlite3 `
  --state-library state/story_state.sqlite3 `
  --viewpoint Mara --at book1/ch05 `
  --prompt-out .runtime/prose-repair-prompt.txt `
  --plan-out .runtime/prose-salvage.json `
  --manifest-out .runtime/prose-rewrite-request.json `
  --context-mode fresh_call `
  --json
```

Route only on `action`:

- `accept`: stop.
- `rewrite`: invoke writer with generated prompt, then `rewrite-apply`, then loop.
- `salvage`: invoke writer with generated gap prompt, then `salvage-apply`, then loop.
- `human_review`: stop automatically.

Never ask the model whether the chapter or plan is done. Never feed a model's self-summary back as the next diagnostic state. Never bypass a failed contract by manually extracting text.

## Context rule

For `fresh_call`, never continue planning -> drafting -> repair inside one conversational context. Reuse the same model if desired, but start a new inference/chat context for each prompt manifest. For `persistent_safe`, do not switch into it after the conversation has already seen author-only canon; discard the contaminated conversation first.

## v0.7 Hermes launch boundary

For unattended execution, do not rely on the current Hermes conversation to create its own fresh context. Invoke `integrations/hermes/hermes_fresh_call.py` from the parent deterministic workflow. Interactive `start-project` sessions are convenient but are not disclosure-isolated after author-only information has entered the conversation. See `integrations/hermes/README.md` and `docs/HOSTILE_REVIEW_V6_HERMES.md`.


## Temporal pilot

Every plan/request is branch-bound. After a chronobreak, pass `--branch <id>` through planning and prose repair; never rely on a remembered branch. The safest end-to-end pilot is `integrations/hermes/pilot_controller.py`, which always drafts through disclosure epochs and fresh Hermes child processes.

A non-destructive editorial fork can be created with `write_runtime.py chronobreak`; rebuild canon/state afterward, inspect `state-diff`, then regenerate plans on the child branch. Stale parent plans are expected to fail when preconditions diverge.
