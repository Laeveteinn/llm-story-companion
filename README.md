# Deterministic Writing Runtime v0.7.1

A temporal, deterministic fiction-writing harness built around one rule: **if a failure can be established mechanically, do not ask an LLM to judge it.** Models propose plans and prose; Python owns canon, narrative state, chronology, disclosure, contracts, model routing, retry budgets, repair routing, and acceptance.

Planner/writer/controller are phases, not separate minds. Strong isolation comes from fresh contexts plus deterministic context compilation, not role names.

## Install on Windows / Hermes

The public GitHub source tree is the installation authority. The root installer resolves `main` once to an immutable Git commit, checks out that exact source revision, records installation provenance, runs the bootstrap, and installs the Hermes skill.

```powershell
iex (irm https://raw.githubusercontent.com/Laeveteinn/llm-story-companion/main/install-hermes.ps1)
```

For an existing checkout:

```powershell
.\integrations\hermes\bootstrap.ps1
```

## Hermes Desktop: your own story

The Mara/Sable Bind material in the repository is a **test fixture only**. Real stories live under gitignored `projects/<slug>/` and get their own canon/state sources and SQLite authority stores.

Natural Hermes GUI use should look like:

> Start a new deterministic writing pilot called *Memory Debt*. First POV is Iri. The city lets people mortgage memories; Chapter 1 begins with Iri trying to steal one of her own memories back. Keep the initial project sparse.

Hermes should internally use the supported entry points:

```text
writing-project-init <brief> --slug memory-debt --title "Memory Debt" --viewpoint Iri --viewpoint-kind character
writing-project-model memory-debt --provider <provider> --model <model>
writing-pilot --project memory-debt --skip-setup
```

For omniscient/general-third/no central POV, initialization uses `--viewpoint-kind narrator` rather than registering a fake character called "general third person".

The sparse initializer creates:

```text
projects/<slug>/
├── brief.txt
├── project.json
├── canon_source/project.yaml
├── state_source/project.yaml
├── runtime_state/
│   ├── canon.sqlite3
│   └── story_state.sqlite3
└── manuscript/
```

The seed intentionally contains only the first timeline point and the supplied viewpoint/narrator identity. It does not ask a model to invent a giant bible before Chapter 1.

## Stable model routing

A named project must explicitly pin both Hermes provider and model:

```text
writing-project-model <slug> --provider <provider> --model <model>
```

`writing-pilot` refuses an unpinned project rather than inheriting Hermes Desktop's last-used/default model. The stored pair is forwarded to every fresh planning, drafting, and repair call.

## Managed pilot jobs

For named projects, `writing-pilot` is **non-blocking by default**:

```text
writing-pilot --project <slug> --skip-setup
```

It starts one managed controller job and immediately returns a run ID plus job/log paths. Poll it with:

```text
writing-pilot --project <slug> --status
```

Stop only when requested:

```text
writing-pilot --project <slug> --cancel
```

A second start while one is active returns `already_running` instead of launching another controller. This prevents GUI/terminal timeouts from turning into overlapping orphan runs.

Expected states include `started`, `running`, `completed`, `failed`, `orphaned`, `cancelled`, `blocked_harness_dirty`, and `harness_modified`. Failure/orphan/dirty-harness states are report-and-stop conditions; normal writing mode must not patch the harness in response.

`--foreground` is reserved for explicit human debugging.

## Harness immutability during writing

Managed jobs require tracked Git files to be clean before start. The operator records the current Git HEAD. The controller checks tracked source around deterministic/model phases and before final acceptance. If tracked harness files change during the run, generation aborts and the result is untrusted.

`projects/` is gitignored and is not part of this guard.

Fresh child Hermes calls already use the minimal `clarify` toolset, so planner/writer subprocesses are candidate generators rather than general-purpose coding agents.

## Safe project replacement

The initializer no longer exposes a generic `--force` overwrite. If a project exists, it stops. Only after explicit user approval to discard/restart that exact project should the operator use:

```text
--replace-existing <exact-slug>
```

## Named-project authority guard

For a real project, use `writing-pilot --project <slug>`. Do not guess alternate modules or call `pilot_controller.py` directly.

The controller itself rejects a project brief if it would silently fall back to the root fixture canon/state sources or databases. This prevents real stories from accidentally using the Mara fixture after a low-level invocation mistake.

## GUI-independent entry points

The editable Python install exposes:

```text
write-runtime
writing-project-init
writing-project-model
writing-pilot
```

These resolve the harness checkout from the installed Python package rather than trusting Hermes Desktop's current working directory.

## Architecture

```text
AUTHOR BRIEF
    |
    +--> author-scope canon
    +--> narrative state snapshot
    v
SAME MODEL: fresh planning call
    v
STRICT ChapterPlan JSON
    v
DETERMINISTIC PLAN GATE
    | schema / canon / disclosure / DAG / state / invariants / smells
    +--> localized plan repair
    +--> one bounded whole-plan recompile
    +--> human_review
    v
WRITER-SAFE LOWERING
    | removes author-only intent, hidden facts/mechanics, private state
    +--> disclosure epochs when knowledge changes mid-chapter
    v
SAME MODEL: fresh drafting call per epoch
    v
REQUEST-BOUND PROSE
    v
DETERMINISTIC QUALITY / CONTRACT GATE
    | canon + plan obligations + repetition + grammar + NLP + corpus evidence
    +--> bounded rewrite
    +--> Occam paragraph-cluster salvage
    +--> human_review
```

The runtime never uses an unbounded critic/rewrite loop.

## Canon and narrative state

Human-editable YAML compiles to SQLite authority stores. The root commands below target the built-in fixture; named projects use their own paths automatically.

```powershell
python write_runtime.py canon-build canon_source --out canon/canon.sqlite3
python write_runtime.py state-build state_source --library canon/canon.sqlite3 --out state/story_state.sqlite3
```

Canon tracks stable entries, exact triggers, versioned facts, who knows what, timed reveals, chronology, mechanics, and relationships. Narrative state is a replayable event/invariant ledger for movement, possession, injuries, resources, knowledge, promises, scene participation, and other semantic effects.

## Temporal branches / chronobreaks

v0.7 makes truth branch-aware rather than destructively rewinding history. Canon facts, reveals, mechanics, state events, plans, writer surfaces, and disclosure checks all carry a timeline branch.

```powershell
python write_runtime.py chronobreak `
  --id retcon.ch05 `
  --parent main `
  --at book1/ch05 `
  --kind retcon `
  --out canon_source/retcon.ch05.yaml
```

A child timeline inherits ancestor history only through its fork point. Parent future after the fork is not inherited. Truth time, character-knowledge time, and branch identity are separate axes.

## Disclosure-safe single-model execution

- **`fresh_call`** — preferred. The same model weights/runtime can be reused, but every phase/attempt starts with an empty context and is discarded afterward.
- **`persistent_safe`** — degraded fallback. Hidden author-only truth is withheld from every prompt and retry budgets are tighter.

There is deliberately no "show the model a secret and ask it to forget later" mode. If knowledge changes inside a chapter, drafting is split into monotonic disclosure epochs.

## Deterministic prose sensors

The evidence bus can use Vale/Harper/proselint/AiTells, retext, CSpell, plain-english, Slopless, spaCy, TextDescriptives, wordfreq, CMUdict, RapidFuzz, and optional LanguageTool. Style tools are sensors, not laws; hard gates are reserved for objective contract/canon/timeline/state/disclosure failures.

## Verify an installation

```powershell
python -m writing_runtime.cli --help
python write_runtime.py doctor
python write_runtime.py tool-verify
```

The post-control-plane regression reconstruction passed **73/73 pytest tests**, plus Python compile checks. It used the canonical v0.7.1 test tree overlaid with the exact published managed-job/project/controller modules and tests. The Windows/Hermes process lifecycle still needs target-machine exercise because this repository intentionally does not use GitHub-hosted runners.

## Important docs

- `docs/TEMPORAL_MODEL.md`
- `docs/SEMANTIC_NARRATIVE_STATE.md`
- `docs/DISCLOSURE_EPOCHS.md`
- `docs/REINJECTION_FIREWALL.md`
- `docs/DETERMINISTIC_REPAIR.md`
- `integrations/hermes/README.md`

This is a pilot, not a claim that deterministic metrics can calculate literary greatness. The objective is narrower: mechanically establish everything we reasonably can, expose only normalized/disclosure-safe evidence to the model, cap recursion, and stop cleanly instead of allowing an agent to mutate the control plane when something fails.
