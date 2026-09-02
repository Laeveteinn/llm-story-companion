# Hostile review of v0.1

The first deterministic reset was directionally correct and technically underpowered.

## Canon problems that required immediate correction

### YAML as runtime state
Fine for 1–50 records; poor as the long-term library. It offers no indexed joins, referential integrity, transactional updates, graph queries, or efficient full-text search.

**v0.2:** YAML is authoring input. SQLite is runtime truth.

### Fake chronology
v0.1 compared timeline keys as strings. That works accidentally for zero-padded/simple `book1/ch03` examples and fails as soon as naming changes, chapters reach inconsistent widths, interludes branch, or real dates/times appear.

**v0.2:** all used timeline points resolve to explicit integer ordinals.

### POV leakage
v0.1 always surfaced current canonical state even when a historical viewpoint was requested. A writer model could therefore see the secret answer while being told the POV did not know it.

**v0.2:** `writer` and `pov` surfaces are distinct. POV scope cannot retrieve hidden canon or mechanics.

### Blob-shaped facts
The old `state` object could not answer useful questions such as “which fact changed?”, “what was true at chapter 8?”, or “which reveal corresponds to this fact?” without parsing arbitrary YAML structure.

**v0.2:** facts, knowledge, reveals, mechanics and relationships have distinct relational storage.

### Trigger scan scalability
v0.1 scanned every entry and phrase. This is acceptable for small projects but should not be confused with a knowledge engine. v0.2 keeps the same auditable literal semantics, now indexed/stored relationally. A trie/Aho–Corasick matcher can replace the scan later without changing semantics if the library becomes large enough to matter.

## Prose analyzer problems still present

These are deliberately *not* papered over in v0.2.

### Regex tokenization and sentence splitting are toy grade
Quotation, abbreviations, initials, ellipses, nested punctuation and dialogue make regex boundaries unreliable. Mature parsers already solve most of this.

### Syllable counting is crude
Flesch scores built on a heuristic syllable counter compound measurement error. CMUdict gives actual phoneme/stress sequences for a large English lexicon and should be the primary source with a fallback heuristic only for OOV words.

### “weak verbs” is a bad ontology
Copulas are not objectively weak. High copular density can be a useful descriptive signal for static/expository passages, but a blacklist framed as “weak verbs” imports workshop folklore into supposedly objective instrumentation.

**Planned:** rename to descriptive POS/lemma distributions and calibrate against scene modes.

### `-ly` adverb density is not quality
Useful as an observable feature; indefensible as a generic writing defect. Same for em dashes, semicolons, sentence length and most style-guide shibboleths.

**Rule:** descriptive metrics may be calibrated; prescriptive rules must cite a rule source and remain individually switchable.

### Repeated bigrams are noisy
Function-word bigrams dominate and dialogue naturally repeats. Repetition needs lemmatization, stopword-aware variants, span locations, and separation of intentional refrains from accidental local recurrence.

### Readability is not literary quality
Flesch/Kincaid estimates reading difficulty. It does not measure tension, beauty, voice, imagery, characterization or narrative coherence.

### Aggregate fit score invites metric gaming
Even with a warning label, a single 0–100 number encourages the rewrite loop to optimize the score rather than the prose.

**Planned:** replace the scalar as the primary gate with a vector of explicit constraints, deviations and local spans. Hard gates and soft diagnostics should be separate.

### Corpus calibration can lie
Percentiles from a tiny or mixed corpus are unstable. Action, dialogue, introspection and exposition have different distributions. Document length also changes several lexical metrics.

**Planned:** minimum sample counts, fixed-size windows, scene-mode profiles, bootstrap confidence intervals, and held-out validation.

## Process failure to avoid

The dangerous pattern is rebuilding mature language technology because writing “feels bespoke.” It is not. Tokenization, dependency parsing, lexical frequency, pronunciation, grammar checking, cohesion, lexical diversity and syntactic-complexity measurement all have existing bodies of work.

Our custom code should concentrate on the parts existing tools do not know:

- project canon and disclosure state
- story chronology
- fictional mechanics
- house-specific profile calibration
- deterministic orchestration and convergence rules
- narrative-specific measurements not covered by available tools
