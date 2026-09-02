# v0.7.1 Handoff — Temporal Deterministic Writing Runtime

## Canonical state

The public GitHub source tree is the current installation authority. One underlying model may perform every generative phase, but Python owns canon, narrative state, chronology, disclosure, model routing, contracts, retry budgets, repair routing, managed execution, and accepted outputs.

## Verified baseline

Before the Desktop control-plane patch, the full local suite was green at **66 pytest tests passed**, plus Python compile checks, canon/state rebuilds, branch-specific temporal smokes, and named-project `prepare-only` validation. PowerShell/Hermes Desktop behavior is exercised on the target Windows machine; no GitHub-hosted runners are used.

The control-plane patch adds focused regression tests for project replacement/narrator mode, managed-job state, and named-project fixture isolation. Changed Python modules were syntax-compiled while preparing the patch. Do not claim a new full-suite count until the target checkout runs pytest again.

## Current operating model

### Named projects

Real stories live under gitignored `projects/<slug>/` with their own brief, YAML sources, compiled canon/state stores, runtime state, and manuscript output. Root Mara/Sable Bind data is a fixture only.

New projects are deliberately sparse. Character POVs are registered as characters; omniscient/general-third/no-central-POV projects use narrator mode instead of creating a fake character.

### Stable model routing

Every named project must explicitly pin both Hermes provider and model in `project.json` via `writing-project-model`. `writing-pilot` fails closed when the pin is absent instead of inheriting Hermes Desktop's last-used/default model.

### Managed Desktop runs

`writing-pilot --project <slug>` starts one non-blocking managed run and returns a run ID plus status/log paths. Poll with `--status`; cancel only on explicit user request. Duplicate starts return `already_running` rather than spawning another controller.

Terminal states such as `failed`, `orphaned`, `harness_modified`, `blocked_harness_dirty`, and `human_review` are report-and-stop conditions in normal writing mode. They are not permission for interactive Hermes to patch the harness.

### Harness immutability

Managed runs require tracked Git files to be clean, record the current HEAD, and pass it into the controller. The controller rechecks tracked source around deterministic/model phases and before acceptance. A tracked-source mutation aborts the run and makes the result untrusted.

Fresh planner/writer child Hermes calls already use the minimal `clarify` toolset; the destructive self-editing failure observed during the first Desktop pilot came from the interactive operator after timeouts, not from those fresh candidate-generation calls.

### Safe replacement

The generic initializer `--force` path is removed. Existing projects stop initialization unless the user explicitly asks to discard/restart that exact slug, in which case `--replace-existing <exact-slug>` is required.

### Authority-path guard

A brief under `projects/` cannot silently run against root fixture canon/state defaults. Named projects should always enter through `writing-pilot --project <slug>`, which supplies their own authority paths.

## Temporal model

- immutable timeline branches replace destructive rewind;
- fact validity, character knowledge, and branch identity are separate axes;
- canon facts/reveals/mechanics/state/plans carry branch identity;
- child timelines inherit ancestor history only through the fork point;
- automatic merge remains intentionally absent;
- `chronobreak` creates non-destructive branch overlays.

## Execution doctrine

Interactive Hermes/Desktop is the conversational operator only. It may initialize, pin, start, poll, cancel, and report. During ordinary writing it must not:

- patch Python/tests/skills/tracked configuration;
- hand-edit canon/state to bypass a gate;
- guess alternate entry points;
- invent config formats;
- launch duplicate runs after a GUI timeout;
- reinterpret deterministic failure as approval.

The controller owns fresh planning, bounded plan repair, disclosure epochs, fresh drafting, deterministic assembly/gates, bounded prose repair/salvage, and `accepted` vs `human_review`/failure.

## Installation / refresh

Public Windows install:

```powershell
iex (irm https://raw.githubusercontent.com/Laeveteinn/llm-story-companion/main/install-hermes.ps1)
```

Existing checkout:

```powershell
.\integrations\hermes\bootstrap.ps1
```

After source-only updates, an editable-package reinstall plus skill reinstall is sufficient unless dependency metadata changed.

## Read next

- `README.md`
- `integrations/hermes/README.md`
- `integrations/hermes/skill/deterministic-writing-runtime/SKILL.md`
- `docs/TEMPORAL_MODEL.md`
- `docs/SEMANTIC_NARRATIVE_STATE.md`
- `docs/DISCLOSURE_EPOCHS.md`
- `docs/REINJECTION_FIREWALL.md`
- `docs/DETERMINISTIC_REPAIR.md`
