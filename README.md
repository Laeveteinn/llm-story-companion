# Deterministic Writing Runtime v0.7.1

A temporal, deterministic fiction-writing harness built around one rule: **if a failure can be established mechanically, do not ask an LLM to judge it.** The model proposes plans and prose; Python owns canon, narrative state, chronology, disclosure, contracts, retry budgets, repair routing, and acceptance.

Planner/writer/controller are phases, not separate minds. The same model can perform every generative phase. Strong isolation comes from fresh contexts plus deterministic context compilation, not role names.

## Install on Windows / Hermes

The public GitHub source tree is the installation authority. The root installer resolves `main` once to an immutable Git commit, checks out that exact source revision, records installation provenance, runs the full bootstrap, and installs the Hermes skill.

```powershell
iex (irm https://raw.githubusercontent.com/Laeveteinn/llm-story-companion/main/install-hermes.ps1)
```

For an already-cloned checkout:

```powershell
.\integrations\hermes\bootstrap.ps1
```

A full bootstrap installs the Python/NLP runtime, Node analyzers, Vale packages where available, builds the example canon/state stores, validates the example plan, writes a toolchain lock, runs `doctor`, and installs the Hermes skill.

## Hermes Desktop GUI: start your own story

The Mara/Sable Bind material in the repository is a **test fixture only**. A real story gets an isolated local namespace under `projects/<slug>/`; it does not inherit the example canon or state.

After installation, Hermes Desktop should be able to handle a natural request such as:

> Start a new deterministic writing pilot called *Memory Debt*. First POV is Iri. The city lets people mortgage memories; Chapter 1 begins with Iri trying to steal one of her own memories back from a courthouse vault. Aim for roughly 2500 words and keep the first project seed sparse rather than inventing a huge bible first.

The installed skill should save that brief and invoke:

```text
writing-project-init <brief> --slug memory-debt --title "Memory Debt" --viewpoint Iri
writing-pilot --project memory-debt --skip-setup
```

You should not have to run those commands yourself from normal Hermes GUI use.

`writing-project-init` creates:

```text
projects/<slug>/
├── brief.txt
├── project.json
├── canon_source/
│   └── project.yaml
├── state_source/
│   └── project.yaml
├── runtime_state/
│   ├── canon.sqlite3
│   └── story_state.sqlite3
└── manuscript/
```

The first seed is intentionally sparse: one timeline point plus empty canon/state ledgers. It does **not** ask a model to hallucinate a prewritten encyclopedia before Chapter 1 exists. `projects/` is ignored by the public harness Git repository by default so private story material is not accidentally pushed upstream.

For an existing named project, the GUI operator can simply invoke `writing-pilot --project <slug> --skip-setup`; `project.json` supplies that story's own brief, coordinates, canon/state sources, compiled stores, work directory, and manuscript output.

## GUI-independent entrypoints

The editable Python installation exposes:

```text
write-runtime
writing-project-init
writing-pilot
```

`writing-pilot` resolves the harness checkout from the installed Python package rather than trusting Hermes Desktop's current working directory. This keeps GUI CWD/project-discovery quirks out of the deterministic control boundary.

## Verify an installation

From the project root:

```powershell
python -m writing_runtime.cli --help
python write_runtime.py doctor
python write_runtime.py tool-verify
python write_runtime.py state-audit --at book1/ch05 --json
python write_runtime.py plan-check plans/example.json --library canon/canon.sqlite3 --state-library state/story_state.sqlite3
```

## Architecture

```text
AUTHOR BRIEF
    |
    +--> author-scope canon
    +--> narrative state snapshot
    v
SAME MODEL: planning call
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

Human-editable YAML compiles to SQLite authority stores. The root commands below target the built-in fixture; named projects use project-specific paths automatically.

```powershell
python write_runtime.py canon-build canon_source --out canon/canon.sqlite3
python write_runtime.py state-build state_source --library canon/canon.sqlite3 --out state/story_state.sqlite3
```

Canon tracks stable entries, exact triggers, versioned facts, who knows what, timed reveals, chronology, mechanics, and relationships. Exact triggers drive automatic injection; FTS is explicit search only.

Narrative state is a replayable event/invariant ledger. Semantic operations include movement, scene participation, possession transfer/consume, injury/healing, capability enable/disable, resource spend/gain, fact learning, and promises. These compile to the generic state engine rather than becoming a giant handcrafted story ontology.

## Temporal branches / chronobreaks

v0.7 makes truth branch-aware instead of destructively rewinding history. Canon facts, reveals, mechanics, state events, plans, writer surfaces, and disclosure checks all carry a timeline branch.

```powershell
python write_runtime.py chronobreak `
  --id retcon.ch05 `
  --parent main `
  --at book1/ch05 `
  --kind retcon `
  --out canon_source/retcon.ch05.yaml
```

A child timeline inherits ancestor history only through its fork point. Parent future after the fork is not inherited. Truth time, character-knowledge time, and branch identity are separate axes. Automatic branch merge is intentionally absent in the pilot.

## Disclosure-safe single-model execution

Two modes exist:

- **`fresh_call`** — preferred. Reuse the same model weights/runtime, but every phase/attempt starts with an empty context and is discarded afterward. Author-only planning is permitted because drafting cannot inherit that context.
- **`persistent_safe`** — degraded fallback. Hidden author-only truth is withheld from every prompt and retry budgets are tighter.

There is deliberately no "show the model a secret and ask it to forget later" mode.

If knowledge changes inside a chapter, `draft-epochs` splits generation into monotonic disclosure epochs. Later facts are physically absent from earlier prompts.

## Pilot controller

`integrations/hermes/pilot_controller.py` is the automated execution path. Python owns the loop; Hermes is only the candidate generator. It supports explicit project-specific canon/state source and SQLite paths; `writing-pilot --project <slug>` fills those from the named project's `project.json`.

Conceptually:

```text
rebuild that project's stores
 -> compile planning packet
 -> fresh Hermes call
 -> deterministic plan gate / finite repair
 -> compile disclosure epochs
 -> fresh Hermes call per epoch
 -> software assembly
 -> prose gate / finite repair
 -> accept or human_review
```

Use `--prepare-only` to test packet generation without invoking Hermes.

## Deterministic prose sensors

The normalized evidence bus can use Vale/Harper/proselint/AiTells, retext, CSpell, plain-english, Slopless, spaCy, TextDescriptives, wordfreq, CMUdict, RapidFuzz, and optional LanguageTool.

Style tools are sensors, not laws. Hard gates are reserved for objective contract, canon, timeline, state, and disclosure violations.

## Current pilot status

The current source was locally regression-tested with **66/66 pytest tests passing**, including sparse isolated project creation and a named-project `prepare-only` controller smoke. The earlier v0.7 temporal/state/canon/disclosure tests remain green. PowerShell/Hermes Desktop execution is exercised on the target Windows installation rather than GitHub-hosted runners.

## Important docs

- `docs/TEMPORAL_MODEL.md`
- `docs/HOSTILE_REVIEW_V7_TEMPORAL.md`
- `docs/HOSTILE_REVIEW_V7_OPEN_SOURCE_WHEELS.md`
- `docs/HOSTILE_REVIEW_V6_HERMES.md`
- `docs/SEMANTIC_NARRATIVE_STATE.md`
- `docs/DISCLOSURE_EPOCHS.md`
- `docs/REINJECTION_FIREWALL.md`
- `docs/DETERMINISTIC_REPAIR.md`
- `integrations/hermes/README.md`

This is a pilot, not a claim that deterministic metrics can calculate literary greatness. The objective is narrower: mechanically establish everything we reasonably can, feed only normalized and disclosure-safe evidence back into the model, cap recursion, and cut/regenerate contaminated regions when repeated attempts fail.
