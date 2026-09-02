# Hermes integration — v0.7.1

Hermes Desktop is the conversational operator. Python owns deterministic control. Fresh child Hermes processes are candidate generators only.

## Normal GUI experience

After bootstrap, the profile-level `deterministic-writing-runtime` skill lets Hermes Desktop operate the harness without depending on its current working directory.

Supported entry points:

```text
writing-project-init
writing-project-model
writing-pilot
```

For a new story, Hermes saves the user's brief, initializes an isolated `projects/<slug>/` namespace, pins an explicit provider/model pair, then starts the project through `writing-pilot --project <slug>`. The root Mara/Sable Bind material is a fixture only.

General-third/omniscient stories should initialize with `--viewpoint-kind narrator`; named-character POVs use `character`.

## Managed named-project runs

Named projects use a managed, non-blocking job by default:

```text
writing-pilot --project <slug> --skip-setup
```

The start command returns immediately with a run ID and paths to `job.json` and `pilot.log`. Poll with:

```text
writing-pilot --project <slug> --status
```

If the status is `starting` or `running`, keep polling that run. If a second start attempt returns `already_running`, do not launch another controller. To stop only when the user requests it:

```text
writing-pilot --project <slug> --cancel
```

This avoids treating a Hermes Desktop terminal timeout as evidence that the underlying writing run failed.

Expected terminal states include `completed`, `failed`, `orphaned`, `cancelled`, `harness_modified`, and `blocked_harness_dirty`. A failure/orphan/dirty-harness state is a report-and-stop condition for normal writing. Interactive Hermes must not patch the harness to recover automatically.

`--foreground` remains available for explicit human debugging, but is not the normal Desktop path.

## Harness immutability

Managed runs require tracked Git files to be clean before starting. The operator records the current Git HEAD. During the run, the controller checks that tracked harness source still matches that HEAD around deterministic/model phases and before accepting prose.

`projects/` is gitignored and is not part of this source guard. If tracked harness code changes during a run, the controller aborts and the result is marked untrusted rather than adapting to the mutation.

Fresh child calls already use Hermes' minimal `clarify` toolset, so generative planner/writer calls are not general-purpose coding agents.

## Model routing

Named stories must explicitly pin both Hermes provider and model:

```text
writing-project-model <slug> --provider <provider> --model <model>
```

`writing-pilot` fails closed on an unpinned project instead of inheriting Hermes Desktop's last-used/default model. The pair is forwarded to every fresh planning, drafting, and repair call.

## Safe project replacement

`writing-project-init` no longer has a generic `--force` path. If a project already exists, initialization stops. Only after explicit user approval to discard/restart that exact project should Hermes use:

```text
--replace-existing <exact-slug>
```

## Authority-path guard

For a named project, always use `writing-pilot --project <slug>`. Do not call `pilot_controller.py` directly and do not guess modules such as `writing_runtime.pilot`.

The controller itself refuses a brief under `projects/` if it would silently fall back to the root fixture canon/state sources or databases. This prevents a real story from accidentally planning against the Mara fixture.

## Controller ownership

Once launched, the controller owns:

```text
rebuild selected project stores
 -> compile planning packet
 -> fresh Hermes plan call
 -> deterministic plan gate / bounded repair
 -> disclosure epochs
 -> fresh Hermes draft call(s)
 -> software assembly
 -> deterministic prose/canon/state gates
 -> bounded repair/salvage
 -> accepted or human_review/failure
```

Interactive Hermes should not read hidden author packets just to narrate progress and must not recreate this loop manually.

## Installation

Windows public installer:

```powershell
iex (irm https://raw.githubusercontent.com/Laeveteinn/llm-story-companion/main/install-hermes.ps1)
```

Existing checkout:

```powershell
.\integrations\hermes\bootstrap.ps1
```

The installer/bootstrap installs the profile skill. `start-project.ps1/.sh` remains useful for CLI sessions, but Hermes Desktop GUI does not require launching through that wrapper.

## Low-level debugging

Direct controller/runtime calls, Git repair, tracked source edits, and store surgery are maintenance operations. Use them only when the user explicitly asks to inspect or repair the harness itself. They are not an automatic fallback for a failed writing job.
