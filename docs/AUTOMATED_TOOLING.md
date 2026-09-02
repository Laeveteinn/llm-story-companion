# Automated Deterministic Tooling

## Design rule

Each dependency must own a distinct evidence class or materially improve an existing one. The runtime should not accumulate five readability calculators merely because they are easy to install.

All optional analyzers are capability-detected. Missing tools reduce evidence coverage but do not break canon, contracts, repair state transitions, or the lightweight core.

## Automatically integrated

### Vale

Purpose: one offline lint bus for mature rule packs. `.vale.ini` enables Harper, proselint, write-good and AiTells. Findings are normalized into runtime `Issue` records.

Installation: `setup.ps1` attempts WinGet, then Chocolatey, then Scoop. Bash attempts Homebrew when available. Rule packages sync once and are then treated as frozen until an intentional refresh.

Why not hard-law every Vale warning: fiction legitimately violates technical/editorial style rules. Package identity determines default weight.

### retext / unified

Purpose: AST-based English rules independent of Vale. The local `tools/retext-lint.mjs` emits normalized JSON for Python to consume.

Pinned npm dependencies cover repeated words, indefinite articles, redundant acronyms, contractions, intensifiers and passive voice. Objective-ish rule families are weighted more strongly than stylistic ones.


### plain-english

Purpose: an additional deterministic AI-style/jargon/sentence-spread sensor with JSON output. The runtime invokes **only** `plain-english lint`; its optional semantic/model-backed layer is never used by the deterministic gate. Findings remain low-weight evidence.

### Slopless

Purpose: a second, independently maintained deterministic rhetoric/slop rule set. It bundles textlint internally, emits JSON only, and covers boilerplate framing, fake contrasts, hedging, clichés, vacuous closers, sentence-pattern issues, and related LLM-shaped prose. It is pinned and normalized as low-weight evidence rather than treated as proof of authorship or bad writing.

Having both plain-english and Slopless is intentional but bounded: they share the `ai_style` evidence family, so the runtime consensus combiner prevents correlated findings from being added at full weight indefinitely.

### CSpell

Purpose: spelling/terminology. Canon names/aliases/fact trigger vocabulary are exported from SQLite to `config/canon-terms.txt` so invented terminology does not become perpetual false-positive noise.

CSpell 10.x requires Node >=22.18.0. Full setup enforces that rather than silently installing an incompatible tree.

### spaCy

Purpose: real tokenization, lemmatization/POS, dependency parsing and named entities. This replaces increasingly fragile regex attempts to infer syntax.

### TextDescriptives

Purpose: descriptive statistics, readability, dependency distance, POS proportions and related deterministic feature extraction on top of spaCy.

### wordfreq

Purpose: empirical word-frequency evidence. Useful for local rarity/register spikes and eventual dialogue/register profiles; not a rule that rare words are bad.

### CMUdict

Purpose: pronunciation/stress/syllable evidence for rhythm and phonetic analysis. Unknown words remain unknown rather than being assigned invented pronunciations.

### RapidFuzz

Purpose: cheap deterministic lexical near-duplicate paragraph detection. This is distinct from exact n-gram repetition and catches copy/paste or lightly edited duplicated prose.

## Optional manual integration: LanguageTool standalone

LanguageTool is supported as an additional offline grammar/style sensor but deliberately not downloaded by default. It requires Java and a separate standalone distribution, and its release/distribution model is heavier than the npm/Python stack.

Once installed, point the runtime at its CLI jar with either:

```text
LANGUAGETOOL_JAR=/path/to/languagetool-commandline.jar
```

or place a distribution under:

```text
.tools/LanguageTool/**/languagetool-commandline.jar
```

`doctor` detects it; `tool-lock` hashes the jar. This makes the manually installed snapshot reproducible after installation.

## Considered but intentionally not in the default runtime

### textstat / LexicalRichness

Useful libraries, but their primary metrics overlap heavily with TextDescriptives and the existing lexical feature layer. Adding them would increase correlated votes more than information.

### generic textlint installation

Not installed separately. Slopless already bundles textlint for the distinct rule set we want; adding generic textlint plus overlapping rules would increase maintenance and correlated warnings rather than evidence diversity.

### prosesmasher / @veldica/prose-linter / additional AI-slop CLIs

Useful and worth watching, but they substantially overlap the deterministic rhetoric/readability surface now covered by Vale AiTells + plain-english + Slopless + profile calibration. Do not add another scorer merely because it produces a number. Revisit only if a tool demonstrates a distinct detector family or materially better validation corpus.

### Open English WordNet / `wn`

Very useful future **language-library data**, not yet a hard gate. Synonymy/polysemy requires sense disambiguation; mechanically treating every semantic relation as an error would create false certainty. A pinned WordNet database is a good phase for `language.sqlite3` once we have a concrete use such as semantic-family repetition or register checks.

### TAACO / TAALES / TAASSC / TAALED

Excellent academic prior art for cohesion, lexical sophistication and syntax. Their licensing/distribution and desktop-oriented workflows make them less suitable as default redistributable CLI dependencies. Their published metrics should guide our own validated measurements instead of being casually vendored.

### sentence-transformers / embedding similarity

Potentially valuable for semantic duplicate/slop detection, but substantially heavier and less bitwise reproducible across hardware/backends than RapidFuzz. If added, it should be a pinned optional sensor with a fixed local model, never a hard canon/disclosure gate.

### Language-model grammar/rewrite services

Excluded from the deterministic tier. They can be writer/critic models, but their judgments must not masquerade as mechanical evidence.

## Reproducibility

`config/toolchain_expected.yaml` declares deliberate target versions. After setup:

```bash
python write_runtime.py tool-lock --out config/toolchain.lock.json
```

records:

- command versions;
- installed Python/npm package versions;
- project config hashes;
- every frozen Vale style file;
- optional LanguageTool jar hash.

Before a production run:

```bash
python write_runtime.py tool-verify
```

A drift failure should be treated like a changed compiler or changed test suite: investigate before comparing new quality results against old ones.

## v0.4 planning/runtime libraries

### Pydantic

Purpose: strict typed planning IR and generated JSON Schema. `extra=forbid` makes unexpected model fields contract failures instead of silently carrying prompt debris forward.

The repository pins the version actually regression-tested by this handoff. Do not float to newest during a production run; update intentionally and rerun the full plan/contract suite.

### NetworkX

Purpose: scene/beat dependency DAG validation and cycle detection. A deterministic DFS fallback exists so a missing optional graph implementation cannot make the core unusable, but the pinned package is the default tested path.

### SQLite narrative-state event store

Purpose: replayable physical/story state and invariants. This is project code over Python's SQLite stdlib rather than another workflow dependency, because the operations required are deliberately small and auditable.

## Experimental solver tier — not enabled by default

### Z3

`z3-solver` is an attractive future backend for domains that truly have symbolic constraints: numeric resources, mutually exclusive states, timing inequalities, route constraints, or mechanics whose validity can be expressed as satisfiability. It should not be asked to decide whether a dramatic beat is emotionally justified.

### Unified Planning

Unified Planning is a planner-independent Python modeling layer with multiple planner integrations. It is worth evaluating when the narrative-state ontology becomes rich enough to justify actual planning/search rather than sequential state replay. It is deliberately not a core dependency in v0.4: introducing a general planner before we have a stable story ontology would turn an underspecified fiction problem into a brittle formalism rather than make it deterministic.
