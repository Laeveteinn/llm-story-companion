---
name: deterministic-writing-runtime
description: Operate the deterministic fiction runtime from normal Hermes conversation, including Hermes Desktop GUI. Initialize named stories and use writing-pilot for end-to-end runs; Python owns all gates and recursion.
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

Use this skill whenever the user asks Hermes to start a new story/pilot, plan, draft, continue, revise, repair, chronobreak, inspect, or run a writing pilot with the deterministic writing harness.

The intended UX is conversational, including Hermes Desktop GUI. Do **not** make the user manually execute low-level runtime commands unless they explicitly ask for them.

## GUI / Working-Directory Rule

Do not require the Hermes Desktop session to be opened in the harness repository. The supported GUI entry points are globally installed commands:

```text
writing-project-init
writing-project-model
writing-pilot
```

They resolve the editable harness checkout from the installed `writing_runtime` package. The current GUI terminal CWD is not a trust boundary.

If those commands are unavailable, use `python -m writing_runtime.project_init`, `python -m writing_runtime.project_model`, or `python -m writing_runtime.operator`. If those also fail, report that the checkout must be updated and `python -m pip install -e .` run again. Do not hunt the filesystem for another copy or silently clone a second runtime.

## Model Pinning Rule

A named writing project must use an explicit, stable Hermes provider/model pair. Never let a project silently inherit Hermes Desktop's last-used model, `model.default`, or another mutable global default.

Before the first generative run of a named project, ensure `projects/<slug>/project.json` contains both `provider` and `model`. If not, obtain the desired writing model/provider from the user or from an explicit model choice they have already supplied, then run:

```text
writing-project-model <slug> --provider <provider> --model <model>
```

After pinning, `writing-pilot --project <slug>` passes that provider/model pair to every fresh planning, drafting, and repair child process. If the project is unpinned, the operator intentionally fails closed instead of inheriting Desktop state.

To deliberately change a project's writing model, update the pin explicitly with `writing-project-model`; do not rely on selecting another model in the GUI. A one-run explicit `--provider ... --model ...` override is allowed only when the user intentionally requests it.

## New / Own Story Pilot

When the user says **new pilot**, **my pilot**, **my story**, **start a new project**, or supplies a fresh premise that is not the built-in fixture:

1. **Never use Mara/Sable Bind/example canon or state.** Those are test fixtures only.
2. Capture the user's premise, first-chapter intent, stylistic/length constraints, and other supplied material faithfully into one UTF-8 brief file. Do not invent a large story bible in the interactive GUI conversation.
3. Obtain only genuinely required metadata not already supplied:
   - project title;
   - first viewpoint character/name;
   - writing provider/model to pin for deterministic child calls.
   Infer a filesystem-safe slug from the title and tell the user what slug is being used. Default the first chapter/timeline coordinate to `book1/ch01` unless the user specifies otherwise.
4. Run the deterministic sparse initializer:

```powershell
writing-project-init <brief-file> `
  --slug <slug> `
  --title "<title>" `
  --viewpoint "<viewpoint>"
```

5. The initializer creates an isolated local project under `projects/<slug>/` with its own premise, timeline, canon source, state source, compiled stores, runtime state, and manuscript directory. It intentionally begins with empty canon entries/state rather than hallucinating a prewritten bible.
6. Pin the requested provider/model with `writing-project-model`.
7. If initialization and pinning succeed, run:

```powershell
writing-pilot --project <slug> --skip-setup
```

8. Report the initializer/controller's actual status and artifact paths. If either returns a deterministic failure or `human_review`, stop. Do not improvise a replacement workflow.

`projects/` is ignored by the public harness repository by default. Never push a user's story project into the public harness repo unless the user explicitly requests that publication/version-control behavior.

## Existing Named Project

For an existing project created by `writing-project-init`, first ensure its model pin is present, then invoke:

```text
writing-pilot --project <slug> --skip-setup
```

The project config supplies its own brief, plan/timeline coordinates, canon/state sources, compiled libraries, work directory, manuscript output, provider, and model. Do not substitute the root example stores or mutable Hermes defaults.

## Conversational Operator Rule

Interactive Hermes/Desktop is the **operator**, not the planner/writer/controller.

For an end-to-end writing request:

1. Capture the user's requested brief faithfully without reading hidden canon/state into the current interactive conversation.
2. Ensure the named project's provider/model is explicitly pinned.
3. Invoke `writing-pilot` once, either with `--project <slug>` or explicit coordinates for an intentionally low-level run.
4. Let `pilot_controller.py` own planning, fresh child Hermes calls, disclosure epochs, deterministic gates, finite repair, Occam salvage, acceptance, and `human_review`.
5. Do not manually recreate the controller's plan/draft/repair loop in the interactive session.
6. Never convert a controller failure into a conversational "looks good" success.
7. If the controller returns `human_review` or a request/contract failure, stop generative recursion and show the user the deterministic result.

### Built-in fixture defaults

Only when the user explicitly asks for the **current/example/Mara fixture**, use:

- `plan-id`: `pilot.first.ch05`
- `chapter-key`: `book1/ch05`
- `at`: `book1/ch05`
- `branch`: `main`
- `viewpoint`: `Mara`
- `workdir`: `runtime_state/pilot-first`
- `out`: `runtime_state/pilot-first/final-chapter.txt`

Do not silently apply these values to a real project.

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

For a requested retroactive rewrite, use the runtime's `chronobreak` command to create a child timeline rather than destructively editing history. Treat branch identity as part of every subsequent plan/draft/repair request. Do not carry abandoned parent-future state into the child branch unless the deterministic runtime re-injects them.

## Same-Model Rule

Phase names are not trust boundaries. Planner, writer, repairer, and interactive operator may all use the same underlying model weights. Isolation comes from deterministic context compilation and fresh child processes, not persona labels or promises to forget.

## Verification

Before declaring a project operation complete, rely on the deterministic gate that owns the artifact and report its actual pass/fail state.

For an accepted pilot, report at minimum:

- project slug;
- pinned provider/model;
- controller status (`accepted` or `human_review`/failure);
- final chapter path if accepted;
- plan/work directory paths;
- branch used;
- any non-blocking analyzer/tool warnings.
