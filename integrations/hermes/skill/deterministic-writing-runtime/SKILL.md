---
name: deterministic-writing-runtime
description: Operate the deterministic fiction runtime from normal Hermes conversation, including Hermes Desktop GUI. Named projects use managed writing-pilot jobs; Python owns gates, recursion, model routing, and acceptance.
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

## Operator Contract

Interactive Hermes/Desktop is only the conversational operator. It may capture the user's brief, initialize/pin a named project, start/cancel a managed pilot, poll its status, and report deterministic results. It must **not** manually recreate planning, drafting, critique, repair, canon promotion, or acceptance.

For normal writing operations, the tracked harness source is immutable. Never edit Python, tests, `.hermes.md`, the installed skill, root canon/state fixtures, or tracked configuration in response to a pilot failure. Never hand-edit project canon/state to bypass a gate. Never invent compatibility files such as `model_pin.yaml`.

If a managed run reports `failed`, `orphaned`, `harness_modified`, `blocked_harness_dirty`, or `human_review`, stop and report that state plus the provided log/status. Do not debug or repair the harness unless the user explicitly switches to a harness-maintenance/debugging request.

## Supported GUI Commands

The supported CWD-independent entry points are:

```text
writing-project-init
writing-project-model
writing-pilot
```

Fallback module forms are only:

```text
python -m writing_runtime.project_init
python -m writing_runtime.project_model
python -m writing_runtime.operator
```

Do not guess alternate module names such as `writing_runtime.pilot` or `writing_runtime.pilot_controller`. Do not call `integrations/hermes/pilot_controller.py` directly for a named project; `writing-pilot --project <slug>` is the authority-aware entry point.

## Model Pinning

Every named project must contain an explicit Hermes provider/model pair in `projects/<slug>/project.json`. Never inherit Hermes Desktop's last-used model or another mutable default.

Pin or deliberately change it with:

```text
writing-project-model <slug> --provider <provider> --model <model>
```

Both values are required. Do not infer an exact provider/model identifier when the user has not supplied it and it cannot be read from an existing explicit configuration; ask the user instead.

## New User-Owned Story

For a new/my/own story:

1. Never use the Mara/Sable Bind fixture stores.
2. Save the user's premise, chapter intent, style, length, and supplied world details faithfully to a UTF-8 brief. Do not generate a giant bible before Chapter 1.
3. Obtain the title and viewpoint mode. For a named character POV use `--viewpoint-kind character`. For omniscient/general-third/no central POV use `--viewpoint-kind narrator`; do not register "general third person" as a character.
4. Initialize once:

```text
writing-project-init <brief-file> --slug <slug> --title <title> --viewpoint <viewpoint> --viewpoint-kind <character|narrator>
```

5. If the project already exists, **stop**. Never add a destructive flag on your own. Only if the user explicitly says to discard/restart/replace that project may you rerun initialization with:

```text
--replace-existing <exact-slug>
```

6. Pin the requested provider/model with `writing-project-model`.
7. Start the managed pilot as described below.

`projects/` is ignored by the public harness repository. Never publish a story project unless the user explicitly asks.

## Managed Pilot Jobs — Default for Named Projects

Start one project run with:

```text
writing-pilot --project <slug> --skip-setup
```

For named projects this is intentionally **non-blocking**. It returns a structured `started` result with a run ID, pinned provider/model, job file, log file, and a status command. Do not wait on a long terminal call and do not treat GUI tool timeout as controller failure.

Poll only with:

```text
writing-pilot --project <slug> --status
```

If status is `starting` or `running`, poll again later. If another start request returns `already_running`, do not launch another controller. A project may have only one managed pilot at a time.

To stop an active run when the user requests it:

```text
writing-pilot --project <slug> --cancel
```

`orphaned` is deliberately fail-closed: report it and do not automatically restart. `failed` includes the tail of the controller log; report it, do not patch the harness. `harness_modified` means tracked source changed during the run and the result is untrusted.

`--foreground` exists for explicit human debugging only. Do not use it for normal Hermes Desktop writing.

## Harness Immutability

Before a managed run, `writing-pilot` checks tracked Git files. A dirty tracked harness returns `blocked_harness_dirty` and does not start. The ignored `projects/` tree is not part of this check.

The managed worker pins the current Git HEAD, and the controller rechecks tracked source before and after deterministic runtime/model phases and before accepting prose. If tracked source changes mid-run, generation aborts instead of adapting to the mutation.

Therefore, on any harness-source problem during a normal writing operation: **report and stop**. Do not `git reset`, `git pull`, patch source, reinstall packages, or change skill files unless the user explicitly asks for maintenance.

## Controller Ownership

Once started, `pilot_controller.py` owns:

- rebuilding the selected project's canon/state stores;
- fresh Hermes planning calls;
- typed plan validation and bounded plan repair;
- disclosure epochs;
- fresh drafting calls;
- deterministic assembly/quality/canon/state gates;
- bounded prose repair/salvage;
- `accepted` vs `human_review`/failure.

Fresh child calls use a minimal Hermes toolset and do not inherit the interactive Desktop conversation. Never expose hidden author packets to the interactive session merely to narrate progress.

A project brief under `projects/` is forbidden from silently falling back to the root fixture canon/state stores. If such a low-level invocation is attempted, the controller fails and tells you to use the named-project operator.

## Existing Project

For an existing initialized project, do not reinitialize it to continue writing. Verify its explicit model pin, then use the managed `writing-pilot --project <slug>` path. Project config supplies its own brief, timeline coordinates, canon/state sources, compiled libraries, work directory, manuscript output, provider, and model.

## Built-In Fixture

Only when the user explicitly asks for the example/Mara fixture may you use the root fixture defaults (`book1/ch05`, `main`, `Mara`, `pilot.first.ch05`). Never silently apply them to a real project.

## Low-Level Maintenance

Direct `write_runtime.py` gates, manual store inspection, source edits, Git repair, and foreground controller calls are maintenance/debugging operations. Perform them only when the user explicitly asks to inspect or repair the harness itself, not as an automatic response to a writing-run failure.

For deterministic repair, use only prompts/manifests emitted by the runtime and respect finite retry budgets. If any path reaches `human_review`, stop.

## Reporting

For a managed project operation report the actual structured state. On acceptance include at least project slug, pinned provider/model, final chapter path, branch, and job/log location. On failure include the status and log tail supplied by `--status`; do not reinterpret it as success.
