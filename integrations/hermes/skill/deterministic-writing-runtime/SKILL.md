---
name: deterministic-writing-runtime
description: Operate the deterministic fiction runtime from normal Hermes conversation, including Hermes Desktop GUI. Use writing-pilot for end-to-end runs; Python owns all gates and recursion.
version: 0.7.1
author: Project-local
license: MIT
platforms: [windows, linux, macos]
allowed-tools: terminal, read_file, write_file, search_files
metadata:
  hermes:
    tags: [fiction, writing, deterministic, canon, continuity, pilot, desktop]
    requires_toolsets: [terminal]
---

# Deterministic Writing Runtime

## When to Use

Use this skill whenever the user asks Hermes to plan, draft, continue, revise, repair, chronobreak, inspect, or run a writing pilot for the deterministic writing harness.

The intended UX is conversational, including Hermes Desktop GUI. The user should be able to say things like:

- "Start a writing pilot using the current fixture."
- "Write chapter 12 from Mara's POV on main; here is the brief..."
- "Run the deterministic harness on this chapter."
- "Chronobreak from chapter 8 and rewrite the affected branch."

Do **not** make the user manually execute low-level runtime commands unless they explicitly ask for them.

## GUI / Working-Directory Rule

Do not require the Hermes Desktop session to be opened in the harness repository. Desktop working-directory/project-skill discovery can differ from the active GUI project.

The supported GUI entry point is the globally installed console command:

```text
writing-pilot
```

`writing-pilot` resolves the editable harness checkout from the installed `writing_runtime` package itself, changes into that authoritative root, and delegates to `integrations/hermes/pilot_controller.py`. Therefore the current GUI terminal CWD is not a trust boundary.

If `writing-pilot` is unavailable, try:

```text
python -m writing_runtime.operator
```

If both are unavailable, report that the checkout must be updated and bootstrapped again. Do not hunt the filesystem for another copy and do not silently clone a second runtime.

## Conversational Operator Rule

Interactive Hermes/Desktop is the **operator**, not the planner/writer/controller**.**

For an end-to-end writing request:

1. Capture the user's requested writing brief faithfully in a UTF-8 file. A temporary/operator file in the current writable workspace is fine; it does not need to live in the harness checkout. Do not enrich the brief by reading hidden canon/state into the current interactive conversation.
2. Determine the explicit runtime coordinates: `plan-id`, `chapter-key`, `at`, `timeline branch`, and `viewpoint`.
3. Invoke `writing-pilot` once. Let that Python entry point locate the harness and let `pilot_controller.py` own planning, fresh child Hermes calls, disclosure epochs, deterministic gates, finite repair, Occam salvage, acceptance, and `human_review`.
4. Do not manually recreate the controller's plan/draft/repair loop in the interactive session.
5. Report the controller's actual terminal status and artifact paths. Never convert a controller failure into a conversational "looks good" success.
6. If the controller returns `human_review` or a request/contract failure, stop generative recursion and show the user the deterministic failure/result. Do not improvise another rewrite.

### Current fixture defaults

Only when the user explicitly says to use the **current/example/first pilot fixture**, use:

- `plan-id`: `pilot.first.ch05`
- `chapter-key`: `book1/ch05`
- `at`: `book1/ch05`
- `branch`: `main`
- `viewpoint`: `Mara`
- `workdir`: `runtime_state/pilot-first`
- `out`: `runtime_state/pilot-first/final-chapter.txt`

Do not silently apply these fixture values to a real project.

### Preferred GUI invocation after bootstrap

```powershell
writing-pilot <brief-file> `
  --plan-id <plan-id> `
  --chapter-key <chapter-key> `
  --at <timeline-key> `
  --branch <branch> `
  --viewpoint <viewpoint> `
  --workdir <workdir> `
  --out <output-file> `
  --skip-setup
```

The same arguments can be passed to `python -m writing_runtime.operator` as a fallback.

Pass `--provider` / `--model` only when the user asks to override Hermes's configured defaults. Do not use `--safe-mode` unless the configured provider/model is known to survive Hermes safe mode.

## Why the Interactive GUI Session Must Not Draft

The controller deliberately spawns a fresh one-turn Hermes process for every generative phase. This allows one underlying model to be reused while preventing an accumulating Desktop conversation from carrying author-only information across planning, disclosure epochs, and repairs.

The interactive Hermes session may know the user's brief and public/operator metadata. It should **not** read author-only planning packets or hidden canon merely to narrate what the controller is doing. Treat generated plan prompts, private validator literals, and author-scope state as controller-private unless the user explicitly requests inspection.

## Low-Level Operations

Use low-level runtime commands directly only for explicit inspection/maintenance operations or when debugging a failed pilot:

1. Run the relevant deterministic preflight (`state-audit`, `plan-check`, `quality`, `doctor`, `tool-verify`) before claiming an artifact is valid.
2. Use only prompt files emitted by `write_runtime.py` for recursive plan/prose repair. Never turn raw lint output into an ad-hoc rewrite prompt.
3. Respect process exit codes. A hard failure remains a failure until the deterministic gate changes state.
4. For drafting, use disclosure epochs whenever required. Never resume a model context across epochs.
5. Apply responses only through the runtime's request-bound apply commands.
6. Use `plan-repair-next` / `repair-next` for recursion routing. Do not invent extra critique loops after `human_review`.
7. Preserve immutable anchors during Occam salvage. The runtime, not the model, reassembles accepted text.

## Chronobreak Operations

For a requested retroactive rewrite, use the runtime's `chronobreak` command to create a child timeline rather than destructively editing history. Treat branch identity as part of every subsequent plan/draft/repair request. Do not carry abandoned parent-future state into the child branch unless the runtime explicitly reintroduces it.

## Same-Model Rule

Phase names are not trust boundaries. Planner, writer, repairer, and interactive operator may all use the same underlying model weights.

Isolation comes from deterministic context compilation and fresh child processes, not persona labels or promises to forget.

## Verification

Before declaring a project operation complete, run or rely on the deterministic gate that owns that artifact and report its actual pass/fail state.

For an accepted pilot, report at minimum:

- controller status (`accepted` or `human_review`/failure);
- final chapter path if accepted;
- plan/work directory paths;
- branch used;
- any non-blocking analyzer/tool warnings.
