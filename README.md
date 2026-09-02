# Deterministic Writing Runtime v0.7.1

A temporal, deterministic fiction-writing harness built around one rule: **if a failure can be established mechanically, do not ask an LLM to judge it.** The model proposes plans and prose; Python owns canon, narrative state, chronology, disclosure, contracts, retry budgets, repair routing, and acceptance.

Planner/writer/controller are phases, not separate minds. The same model can perform every generative phase. Strong isolation comes from fresh contexts plus deterministic context compilation, not role names.

## Install on Windows / Hermes

The public GitHub source tree is the installation authority. The root installer resolves `main` once to an immutable 40-character Git commit, downloads the installer from that exact commit, checks out that exact source revision, records installation provenance, runs the full bootstrap, and installs the Hermes skill.

```powershell
iex (irm https://raw.githubusercontent.com/Laeveteinn/llm-story-companion/main/install-hermes.ps1)
```

Default destination:

```text
%USERPROFILE%\WritingHarness-Deterministic
```

If Hermes is missing, the Windows bootstrap delegates Hermes installation to Nous Research's official installer. If Git is missing and WinGet is available, it installs Git for Windows. No GitHub Actions or hosted runners are required.

For an already-cloned checkout, run:

```powershell
.\integrations\hermes\bootstrap.ps1
```

That invokes `setup.ps1`, installs the local Hermes skill, and leaves the project ready to launch with:

```powershell
.\integrations\hermes\start-project.ps1
```

A real full bootstrap installs the core Python runtime, optional pinned NLP stack, Node analyzers, attempts Vale, builds canon/state SQLite stores, validates the example plan, writes a toolchain lock, runs `doctor`, and installs the Hermes skill.

## Verify an installation

From the project root:

```powershell
python -m writing_runtime.cli --help
python write_runtime.py doctor
python write_runtime.py tool-verify
python write_runtime.py state-audit --at book1/ch05 --json
python write_runtime.py plan-check plans/example.json --library canon/canon.sqlite3 --state-library state/story_state.sqlite3
```

The `write-runtime` console command is also installed by the package metadata.

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

Human-editable YAML compiles to SQLite authority stores:

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

A child timeline inherits ancestor history only through its fork point. Parent future after the fork is not inherited.

Inspect timelines mechanically:

```powershell
python write_runtime.py state-branches --json
python write_runtime.py state-history --branch retcon.ch05 --at book1/ch09 --json
python write_runtime.py state-diff --left main --right retcon.ch05 --at book1/ch09 --json
```

Truth time, character-knowledge time, and branch identity are separate axes. Automatic branch merge is intentionally absent in the pilot.

## Disclosure-safe single-model execution

Two modes exist:

- **`fresh_call`** — preferred. Reuse the same model weights/runtime, but every phase/attempt starts with an empty context and is discarded afterward. Author-only planning is permitted because drafting cannot inherit that context.
- **`persistent_safe`** — degraded fallback. Hidden author-only truth is withheld from every prompt and retry budgets are tighter.

There is deliberately no "show the model a secret and ask it to forget later" mode.

If knowledge changes inside a chapter, `draft-epochs` splits generation into monotonic disclosure epochs. Later facts are physically absent from earlier prompts.

## Pilot controller

`integrations/hermes/pilot_controller.py` is the preferred automated pilot path. Python owns the loop; Hermes is only the candidate generator.

Conceptually:

```text
rebuild stores
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

The normalized evidence bus can use:

- Vale / Harper / proselint / AiTells
- retext
- CSpell
- plain-english
- Slopless
- spaCy
- TextDescriptives
- wordfreq
- CMUdict
- RapidFuzz
- optional LanguageTool

Style tools are sensors, not laws. Hard gates are reserved for objective contract, canon, timeline, state, and disclosure violations.

## Current pilot status

The v0.7.1 source snapshot was locally verified with **64/64 pytest tests passing**, Python compile checks, retext/Bash syntax checks, canon/state rebuilds, branch-specific canon/mechanics smoke checks, temporal state-diff checks, and pilot-controller `--prepare-only` validation. PowerShell wrappers must be exercised on the target Windows machine.

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
