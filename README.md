# Deterministic Writing Runtime v0.7.1

A fiction-writing harness built around one rule: **if a failure can be established mechanically, do not ask an LLM to judge it.** Models generate candidates; typed stores, parsers, validators, contracts, and bounded state machines decide what happens next.

The runtime does **not** claim to calculate literary greatness. Its numeric aggregate is suspicion/evidence, never a prose-quality score.

## v0.7 architecture

```text
AUTHOR BRIEF
   |
   +--> canon.sqlite3 (author-scope exact-trigger context)
   +--> story_state.sqlite3 (author state snapshot)
   v
MODEL — planning phase
   v
STRICT ChapterPlan JSON
   v
PLAN GATE
   | schema / canon / disclosure / DAGs / state / invariants / goals / smells
   +--> localized beat surgery
   +--> one bounded whole-plan recompile
   +--> human_review when budget is exhausted
   v
WRITER-SAFE PLAN COMPILER
   | strips author_intent, hidden mechanics/facts, forbidden literals, private state
   +--> disclosure-epoch compiler when knowledge changes inside the chapter
   v
SAME MODEL — drafting phase (fresh call per epoch when required)
   v
REQUEST-BOUND PROSE
   v
QUALITY / CONTRACT GATE
   | canon + plan obligations + grammar + repetition + NLP + corpus evidence
   +--> bounded rewrite
   +--> Occam paragraph-cluster salvage
   +--> human_review when budget is exhausted
```

Planner/writer/controller names are **phases, not separate minds or trust domains**. The same model may perform every generative phase. The deterministic runtime is the controller.

Two execution modes are supported:

- `fresh_call` (preferred): reuse the same model weights/runtime, but start every phase/attempt with an empty conversation/KV context and discard it afterward. Planning may receive hidden author truth because later drafting cannot inherit that context.
- `persistent_safe` (degraded fallback): one continuing model context is allowed, but hidden/author-only canon and state are withheld from **every** model prompt and retry budgets are tighter.

There is intentionally no "show the persistent model a secret now and ask it to forget later" mode. See `docs/HOSTILE_REVIEW_V5_SINGLE_MODEL.md` and `docs/SINGLE_MODEL_EXECUTION.md`.

## Deterministic stores

### Canon

Human-editable YAML compiles to `canon/canon.sqlite3`:

```powershell
python write_runtime.py canon-build canon_source --out canon/canon.sqlite3
```

Canon stores stable entries, triggers, versioned facts, character knowledge, timed reveals, chronology, mechanics, and relationships. Exact triggers drive automatic injection. SQLite FTS is explicit search only and cannot silently inject lore.

### Narrative state

`state/story_state.sqlite3` is a replayable event/invariant ledger for facts such as:

- character location/alive/injury state;
- inventory and possession;
- doors/locks/world switches;
- counters/resources;
- any other explicitly modeled state.

```powershell
python write_runtime.py state-build state_source `
  --library canon/canon.sqlite3 `
  --out state/story_state.sqlite3
```

State is author-only by default. A record must explicitly declare `writer_safe: true` before the writer compiler can expose it.

### Semantic narrative operations

v0.6+ adds typed semantic actions that compile into the replayable state engine instead of forcing planners to hand-author low-level mutations:

- movement and scene participation;
- acquire/transfer/consume possession;
- injury/healing and capability enable/disable;
- resource spend/gain with underflow protection;
- canon-aware fact learning;
- make/resolve promises.

The runtime derives mechanical preconditions and audits ownership, item/location consistency, resource bounds, promise state, subject types, and beat-required capabilities. Project-specific rules still use generic conditions/effects rather than inflating the semantic vocabulary.

```powershell
python write_runtime.py state-audit --at book1/ch05 --json
```

A plan's semantic effects are intended state, not automatically accepted manuscript truth. Persistent promotion still requires explicit accepted-prose reconciliation. See `docs/SEMANTIC_NARRATIVE_STATE.md`.

## Temporal branches / chronobreaks

v0.7 makes chronology branch-aware rather than destructively rewinding state. Canon facts, reveals, events, attached mechanics, narrative-state events, plans, writer surfaces, and quality disclosure checks all carry a timeline branch.

Create a non-destructive retcon fork:

```powershell
python write_runtime.py chronobreak `
  --id retcon.ch05 `
  --parent main `
  --at book1/ch05 `
  --kind retcon `
  --out canon_source/retcon.ch05.yaml

python write_runtime.py canon-build canon_source --out canon/canon.sqlite3
python write_runtime.py state-build state_source --library canon/canon.sqlite3 --out state/story_state.sqlite3
```

A child sees ancestor history only through its fork point. Parent future after the fork is not inherited. Query or compare histories explicitly:

```powershell
python write_runtime.py state-branches --json
python write_runtime.py state-history --branch retcon.ch05 --at book1/ch09 --json
python write_runtime.py state-diff --left main --right retcon.ch05 --at book1/ch09 --json
```

Truth time, character-knowledge time, and branch identity are distinct axes. Flashbacks query an earlier ordinal on the same branch; history-changing time travel uses an explicit branch and explicit carried state/knowledge at arrival. Automatic branch merge is intentionally absent in the pilot. See `docs/TEMPORAL_MODEL.md` and `docs/HOSTILE_REVIEW_V7_TEMPORAL.md`.

## Typed planning

Generate a strict architect request:

```powershell
python write_runtime.py plan-prompt brief.txt `
  --plan-id book1.ch05 `
  --chapter-key book1/ch05 `
  --at book1/ch05 --viewpoint Mara `
  --library canon/canon.sqlite3 `
  --state-library state/story_state.sqlite3 `
  --out .runtime/plan-prompt.txt `
  --manifest-out .runtime/plan-request.json
```

The prompt automatically receives exact-trigger **author-scope** canon plus the narrative-state snapshot. The model must return a strict `ChapterPlan` JSON object inside request-bound sentinels.

Plan validation checks:

- strict Pydantic schema (`extra=forbid`);
- timeline and stable canon IDs;
- chapter/scene/beat disclosure firewall;
- scene and beat dependency DAGs, cycles, and forward references;
- state preconditions/effects and persistent invariants;
- actor/participant and viewpoint presence;
- required goals and thread ordering;
- unauthorized reveals;
- future-reveal priming: configured fact phrases cannot appear in writer-facing fields before their scheduled reveal beat;
- duplicate beat directives, no-op state transitions, directive bloat, and reveal-density evidence.

```powershell
python write_runtime.py plan-check .runtime/plan.json `
  --library canon/canon.sqlite3 `
  --state-library state/story_state.sqlite3
```

Bad plans enter a finite state machine: `repair_beats` -> at most one `rewrite_plan` fallback -> `human_review`. See `docs/PLANNING_IR.md`.

## Writer-safe lowering

Only an accepted plan can be compiled into a prose prompt:

```powershell
python write_runtime.py draft-prompt .runtime/plan.json `
  --library canon/canon.sqlite3 `
  --state-library state/story_state.sqlite3 `
  --out .runtime/draft-prompt.txt `
  --manifest-out .runtime/draft-request.json
```

`writer_plan_surface()` physically omits author intent, hidden fact IDs, forbidden secret phrases, hidden mechanics, non-writer-safe state, and plan diagnostics. Writer-facing canon is retrieved again with POV-safe disclosure filtering.

If a protected fact first becomes available **inside the current chapter** and the plan assigns it to a `reveal_facts` beat, monolithic drafting is mechanically refused. Use disclosure epochs instead:

```powershell
python write_runtime.py draft-epochs .runtime/plan.json `
  --library canon/canon.sqlite3 `
  --state-library state/story_state.sqlite3 `
  --context-mode fresh_call `
  --out-dir .runtime/epochs `
  --manifest-out .runtime/epochs.json `
  --json
```

Each `E###.prompt.txt` must be run against a fresh context of the same model. Facts scheduled for later epochs are physically absent from earlier packets; their literal triggers remain private in the manifest for post-generation validation. `draft-epochs-apply` validates every epoch response and lets software reassemble the chapter in canonical beat order. See `docs/DISCLOSURE_EPOCHS.md`.

`draft-apply` rejects wrong/missing scene **or beat** blocks, plans instead of prose, meta commentary, word-budget violations, missing beat-local literal obligations, forbidden terms, and unrevealed canon before extracting chapter text. It also writes a SHA-256-bound `.provenance.json` sidecar mapping final paragraphs back to scene/beat IDs.

## Mechanical prose evidence

One normalized evidence bus combines internal checks and any installed deterministic analyzers:

| Layer | Default/optional tool |
|---|---|
| truth/disclosure | SQLite canon runtime |
| plan conformance | typed `ChapterPlan` obligations |
| lint bus | Vale 3.17.0 |
| grammar | Harper Vale package / optional LanguageTool |
| AST English checks | retext |
| spelling/terminology | CSpell 10.1.1 |
| rhetoric/AI-pattern sensors | plain-english 1.0.0, Slopless 0.2.36, Vale AiTells |
| parsing | spaCy 3.8.16 |
| linguistic statistics | TextDescriptives 2.8.4 |
| lexical frequency | wordfreq 3.1.1 |
| pronunciation/stress | CMUdict 1.1.3 |
| near duplicates | RapidFuzz 3.14.5 |

Style tools are sensors, not laws. Passive voice, adverbs, punctuation choices, AiTells, etc. remain low-weight unless evidence accumulates. Hard gates are reserved for objective contract/canon/plan violations.

```powershell
python write_runtime.py quality chapter.txt `
  --chapter-plan .runtime/plan.json `
  --library canon/canon.sqlite3 `
  --viewpoint Mara --at book1/ch05 --json
```

## Reinjection firewall

The runtime does not copy arbitrary analyzer prose into the next model prompt. Each issue code lowers through an allowlisted fixed directive template. Raw tool messages remain human-report data only.

If a failed manuscript contains an unrevealed literal canon trigger, the writer repair prompt receives:

```text
[REDACTED_UNREVEALED_CANON]
```

instead of the real secret phrase. The original source remains SHA-256-bound and the candidate is re-audited privately afterward. The same redaction applies to Occam salvage context.

See `docs/REINJECTION_FIREWALL.md`.

## Bounded prose repair / Occam razor

```powershell
python write_runtime.py repair-next chapter.txt `
  --state .runtime/prose-state.json `
  --writer-plan .runtime/plan.json `
  --library canon/canon.sqlite3 `
  --state-library state/story_state.sqlite3 `
  --viewpoint Mara --at book1/ch05 `
  --prompt-out .runtime/repair-prompt.txt `
  --plan-out .runtime/salvage.json `
  --manifest-out .runtime/rewrite-request.json `
  --json
```

Actions are exactly:

- `accept`
- `rewrite`
- `salvage`
- `human_review`

Whole rewrites are finite. Equal-or-worse evidence accelerates escalation. Salvage mechanically identifies contaminated paragraphs, expands by a bounded scene-context radius, makes unaffected paragraphs immutable, asks the model only for exact named gaps, and lets software reassemble the chapter. Salvage plans are hash-bound to the exact source.

There is no unbounded “critic says try again” loop.

## Hermes integration

Hermes is supported as a **candidate generator**, not as the deterministic controller. A skill or `.hermes.md` improves discoverability but cannot guarantee a fresh model context or correct invocation.

For project setup and interactive use:

```powershell
.\integrations\hermes\bootstrap.ps1
.\integrations\hermes\start-project.ps1
```

For a public Git checkout, `integrations/hermes/install-from-github.ps1`/`.sh` performs an unattended clone/fetch, detaches at the resolved commit, verifies required runtime files, records the resolved commit, and runs bootstrap. Pin `ExpectedCommit`/`WRITING_HARNESS_EXPECTED_COMMIT` when you need byte-stable deployment. No GitHub Actions are required.

The pilot controller is:

```powershell
python integrations\hermes\pilot_controller.py .\brief.txt `
  --plan-id book1.ch05 `
  --chapter-key book1/ch05 `
  --at book1/ch05 `
  --branch main `
  --viewpoint Mara `
  --provider <provider> --model <model>
```

Use `--prepare-only --skip-setup` to compile the deterministic stores and first request without invoking Hermes. Full mode always uses fresh one-turn Hermes subprocesses and obeys finite runtime routers; Hermes never decides to skip a gate.

For the strong automated path, use `integrations/hermes/hermes_fresh_call.py`. It pins the project root, launches a new one-turn Hermes process, never resumes a prior session, validates fresh-call manifests, captures output, and records hashes. The candidate must still pass the corresponding deterministic apply/gate command.

See `integrations/hermes/README.md` and `docs/HOSTILE_REVIEW_V6_HERMES.md`.

## Reinvent-the-wheel rule

Generic language mechanics belong to mature deterministic libraries whenever possible. v0.6+ delegates more linguistic work to TextDescriptives, including information-theory metrics and an independently optional coherence pass. The runtime should remain focused on fiction-specific authority/disclosure/state/provenance/repair. See `docs/HOSTILE_REVIEW_V6_REINVENTING_WHEEL.md`.
v0.7 adds a permissive-wheel decision gate and temporal prior-art review. `eventsourcing` (BSD), `novel-hint` (MIT), and RDFLib/pySHACL (BSD/Apache) are preferred candidates if their evidence classes outgrow our thin adapters; Bookwright remains an external EUPL benchmark rather than a pilot dependency. See `docs/HOSTILE_REVIEW_V7_OPEN_SOURCE_WHEELS.md`.

## Installation

### Public GitHub one-command install (recommended for Hermes)

Once `Laeveteinn/llm-story-companion` is public, Windows can install the current `main` source into a fixed local workspace with one command:

```powershell
iex (irm https://raw.githubusercontent.com/Laeveteinn/llm-story-companion/main/install-hermes.ps1)
```

The installer resolves `main` once to an immutable 40-character commit SHA, reads `dist/current.json` from that exact commit, reconstructs the versioned `tar.xz` source bundle from repository-stored base64 parts, verifies its SHA-256, validates the temporal/semantic/Hermes runtime files, records the resolved commit and archive hash, runs bootstrap, and installs the Hermes skill. If Hermes itself is missing, it delegates installation to Nous Research's official installer rather than maintaining a competing Python/Node bootstrap. No GitHub Actions or hosted runners are used.

For a pinned deployment, download the script and pass `-ExpectedCommit <sha>` and/or `-ExpectedArchiveSha256 <sha>`. The Bash installer supports the equivalent `WRITING_HARNESS_EXPECTED_COMMIT` and `WRITING_HARNESS_EXPECTED_ARCHIVE_SHA256` variables.

### Windows / PowerShell from an existing checkout

```powershell
.\setup.ps1
```

The full setup installs pinned Python/npm dependencies, attempts Vale through common package managers, builds canon and narrative-state SQLite stores, exports canon spelling terms, verifies the example plan, and freezes a toolchain lock. If `package-lock.json` exists it uses `npm ci`; otherwise the first full install resolves the tree and creates the lock, which should then be preserved with the project.

Minimal deterministic core:

```powershell
.\setup.ps1 -CoreOnly
```

### Bash

```bash
./setup.sh
```

Environment switches: `CORE_ONLY=1`, `SKIP_VALE=1`, `REFRESH_VALE=1`.

LanguageTool remains an optional manual standalone install because it also requires Java; once its JAR is available under `.tools/LanguageTool` or `LANGUAGETOOL_JAR`, the runtime detects and uses it automatically.

## Toolchain determinism

```powershell
python write_runtime.py doctor
python write_runtime.py tool-lock --out config/toolchain.lock.json
python write_runtime.py tool-verify
```

Package/ruleset drift is observable. Vale styles are not silently refreshed on every run.

## Verification

```powershell
python -m compileall -q writing_runtime
node --check tools/retext-lint.mjs
python -m pytest -q
```

Current source verification: **64 tests**.

## Boundaries

The runtime can prove explicit contradictions, disclosure leaks, malformed responses, typed state failures, dependency failures, literal plan obligations, repetition anomalies, and many linguistic/mechanical conditions. It still cannot deterministically prove that a paragraph is moving, beautiful, funny, frightening, or that an unrestricted semantic beat was truly achieved. Those remain model/human judgments after the mechanical surface has been reduced as far as practical.

The current draft compiler retains SHA-256-bound scene/beat provenance and attaches it to later localized findings while the sidecar is still valid. A stale provenance map is rejected rather than guessed from.

Within-chapter **disclosure epochs** and typed **semantic narrative state** are now implemented for explicitly modeled facts/actions. The remaining hard frontier is observation/reconciliation: the runtime can prove that a plan is executable and state-consistent, but it cannot deterministically infer every semantic event from arbitrary literary prose. High-value secrets still need fact-level triggers/constraints, and intended plan effects must not become accepted canon/state until the manuscript is explicitly reconciled.

## Documentation

- `docs/PLANNING_IR.md`
- `docs/REINJECTION_FIREWALL.md`
- `docs/DETERMINISTIC_REPAIR.md`
- `docs/HERMES_WORKFLOW.md`
- `docs/HOSTILE_REVIEW_V5_SINGLE_MODEL.md`
- `docs/SINGLE_MODEL_EXECUTION.md`
- `docs/DISCLOSURE_EPOCHS.md`
- `docs/SEMANTIC_NARRATIVE_STATE.md`
- `docs/TEMPORAL_MODEL.md`
- `docs/HOSTILE_REVIEW_V7_TEMPORAL.md`
- `docs/HOSTILE_REVIEW_V7_OPEN_SOURCE_WHEELS.md`
- `docs/HOSTILE_REVIEW_V6_HERMES.md`
- `docs/HOSTILE_REVIEW_V6_REINVENTING_WHEEL.md`
- `docs/FICTION_SYSTEM_PRIOR_ART.md`
- `integrations/hermes/README.md`
- `docs/AUTOMATED_TOOLING.md`
- `docs/RESOURCE_STACK.md`
