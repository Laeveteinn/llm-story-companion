# Resource stack: use existing machinery before inventing ours

This document separates **runtime libraries**, **language/reference datasets**, **corpora**, and **academic analyzers**. The project should pin exact versions/checksums and record licenses for every imported artifact.

## Tier A — adopt early

### SQLite + FTS5 + JSON
Already adopted for canon. FTS5 supplies indexed phrase/full-text search; SQLite JSON/JSONB functions let leaf fields remain flexible without sacrificing a relational core.

Use for: canon, provenance, local reference indexes, metric/corpus caches, experiment results.

### spaCy (or Stanza as an alternate parser)
Use a pinned English model for deterministic inference of tokenization, lemmas, POS tags, dependency trees and named entities.

Use for: clause/syntax metrics, entity continuity, dialogue/action-beat analysis, verb distributions, dependency depth, repeated syntactic shapes.

Do not allow parser-version drift inside a calibrated profile; a model upgrade changes measurements.

### Vale as the lint orchestration layer
Vale is a cross-platform, offline prose linter with custom YAML rules, structured scopes, fixes, JSON output, and installable style packages. It can host house rules plus packaged `proselint`, readability rules, `write-good`, and a large Vale port of Harper grammar checks. This is a better center of gravity than hand-coding dozens of regex lint rules in Python.

Use for: one normalized diagnostic stream with stable rule IDs, spans and severity. Pin Vale and every style package version. Fiction-hostile rules must be individually disabled rather than blindly inherited.

### Harper grammar (directly or through Vale)
Harper is a fast, local, Apache-2.0 English grammar checker. The current Vale-compatible Harper package exposes hundreds of rules and machine-readable fixes.

Use for: grammar/copyediting without sending manuscript text to a cloud service. Prefer it as the first grammar engine to evaluate because it is lighter than a full LanguageTool + n-gram deployment.

### LanguageTool as a second grammar oracle
LanguageTool remains useful because it has a large mature grammar/style rule ecosystem and can run locally. Treat it as an optional second engine for differential testing rather than automatically making two grammar engines rewrite against one another.

### proselint rules
proselint explicitly aggregates advice from major editors/writers and usage guides. It can run directly, but Vale also ships a compatible package, which may simplify orchestration.

Use for: individually enabled prescriptive lint rules. Never fail prose merely because “proselint count > 0”; every active rule should be a deliberate house choice.

### wordfreq / SUBTLEX-derived frequency
Provides Zipf-like frequency estimates built from multiple corpora, including subtitle frequencies.

Use for: rare-word density, dialogue vocabulary plausibility, accidental thesaurus-register spikes, lexical accessibility distributions.

Caution: wordfreq's underlying snapshot is mostly through ~2021. Excellent for stable language frequency; not a live slang oracle.

### Open English WordNet
Open lexical graph: synsets, sense distinctions, hypernyms, antonyms, meronyms and related lexical relations.

Use for: lexical repetition families, semantic alternatives, sense-aware vocabulary checks, concept relations. This should inform diagnostics; it should not auto-thesaurus prose.

### CMU Pronouncing Dictionary
Pronunciations and lexical stress for a large North-American-English word list.

Use for: syllable counts, stress sequences, alliteration/assonance proxies, sentence rhythm and phonetic repetition. Fall back to heuristics only for out-of-vocabulary words.

## Tier B — steal the *science*, inspect licensing before bundling code/data

### TAACO — cohesion
Measures ~150 local/global cohesion indices, including lexical overlap, connectives, sentence/paragraph overlap and semantic similarity.

Use for: build our cohesion feature family and validate it against an established implementation.

License note: current TAACO is CC BY-NC-SA; do not casually copy it into a commercial/distributable runtime.

### TAALES — lexical sophistication
Hundreds of indices covering lexical frequency/range and other sophistication constructs.

Use for: identify which lexical sophistication measurements have literature behind them instead of inventing arbitrary “fancy vocabulary” metrics.

License note: CC BY-NC-SA.

### TAALED / Lexical Diversity
Established lexical-diversity indices beyond raw TTR/MSTTR; important because many diversity measures are text-length sensitive.

Use for: MTLD, HDD and related robust diversity measures, with explicit minimum-window requirements.

### TAASSC — syntactic sophistication and complexity
Measures clause subordination, phrasal elaboration, construction usage and lexicogrammatical variation using parsed text and corpus norms.

Use for: replace our crude `subordinator_per_sentence` proxy with defensible syntax families.

License note: CC BY-NC-SA; TAASSC 2.x itself moved away from COCA because COCA frequency lists were not redistributable.

### SEANCE and related social/affective indices
Potentially useful for affect, polarity and social-cognitive lexical distributions.

Use carefully: these can measure language-associated affect; they cannot determine whether a scene is emotionally effective.

## Tier C — open/reference data packs

### Wikidata
CC0 structured data. Good general-purpose entity/relationship source and offline snapshots are available.

Use for: dates, places, entity attributes, scientific/historical relationships when world research needs structured facts.

Never mix external facts into fictional canon without provenance and an explicit import/approval step.

### Wikipedia / Wikimedia dumps
Large general-reference corpus under Wikimedia licenses.

Use for: offline explicit reference search and source discovery, not automatic canon.

### Wiktionary dumps
Definitions, senses, etymologies, pronunciations and usage information. Powerful but parsing is substantially more complex and license obligations matter.

Use for: etymology/anachronism research, sense/usage labels, morphology, additional pronunciations.

### ConceptNet
Commonsense concept graph (data CC BY-SA).

Use for: explicit commonsense relation queries and semantic feature experiments. Avoid treating crowd-sourced relations as authoritative facts.

### PropBank / semantic frames
Predicate/argument frame resources are useful for analyzing action/verb patterns and who-does-what-to-whom structures.

Use for: repetitive action syntax, agency distributions, scene action density.

## Tier D — calibration corpora

### Standard Ebooks
Especially attractive: public-domain texts, heavily proofread, normalized and semantically marked up; project-produced material is dedicated to the public domain. Better calibration input than random OCR dumps.

### Project Gutenberg
Huge public-domain-oriented library with tens of thousands of texts. Quality/markup varies more than Standard Ebooks.

### Google Books Ngrams / English Fiction corpus
Useful for phrase-frequency history, collocations and period plausibility. It is statistics, not prose examples.

### User-supplied / rights-cleared modern fiction
Best source for the *target* prose distribution. Store derived measurements and short diagnostic fingerprints rather than redistributing copyrighted books.

Do not ship modern authors' novels as a training/calibration pack just because they are technically easy to obtain.

## Recommended three-library architecture

### 1. `canon.sqlite3` — authoritative fictional truth
Hard, project-owned, versioned. Automatic keyword injection may query this.

### 2. `language.sqlite3` — lexical/linguistic measurements
Imported/pinned WordNet, pronunciation, frequency, psycholinguistic norms and derived corpus statistics. Read-only during writing. Used by analyzers, not dumped into context.

### 3. `reference.sqlite3` — external research snapshots
Source/document/provenance tables + FTS5. Wikipedia/Wikidata/research notes can be indexed here. Explicit search only unless a project rule deliberately promotes a fact into canon.

This separation matters. A Wikipedia statement is evidence; a canon statement is law.

## Deterministic convergence policy

A mechanical rewrite loop still needs a stopping rule or it becomes an optimizer that mutilates prose.

Recommended order:

1. Canon/disclosure/mechanics hard failures -> must reach zero.
2. Grammar/spelling rules chosen as hard -> must reach zero.
3. Targeted local style/cadence deviations -> rewrite only flagged spans.
4. Re-run and reject any rewrite that regresses a protected metric beyond tolerance.
5. Maximum rewrite passes per span (e.g. 2–3), then escalate to aesthetic/human judgment instead of looping forever.
6. Never optimize an aggregate prose score. Optimize named defects while protecting already-good dimensions.

## v0.6 fiction-system prior art

Do not expand the fiction graph/continuity layer without first benchmarking `bookwright-cli` (external CLI candidate), Canon AI's temporal assertion/check model, and comparable maintained systems. Bookwright is especially important because it already exposes deterministic graph build/validate commands; treat it as a potential adapter/replacement, not a library to copy. See `FICTION_SYSTEM_PRIOR_ART.md`.
