# Hostile Review v0.3

## Thesis

The earlier writing harness overused model judgment for problems that already have deterministic representations or mature tooling. v0.3 reverses that default: **prove a need for LLM judgment before spending LLM judgment.**

## Failures found in our own earlier reset

### 1. Entry-level secret checking was too coarse

Knowing an entity existed effectively made every detail attached to it difficult to police. Fixed with fact-level disclosure states, fact-specific literal triggers, and timed actor reveals.

### 2. A detector pointed at prose, not situations

Deleting only the sentence that trips a rule can leave broken scene causality. Fixed with bounded context-radius culling and immutable-anchor gap reconstruction.

### 3. “Rewrite” was not a machine contract

Models can answer a rewrite request with a plan, notes, or an apology. Fixed with exact sentinels, length bounds, plan/list fingerprints, gap-ID validation, and write-only-after-valid extraction.

### 4. Iterative critic loops had no principled stop

A critic can always find something else to say. Fixed with finite rewrite/salvage budgets and deterministic no-progress escalation.

### 5. Homemade regexes were becoming pseudo-NLP

Sentence splitting and rough syntactic proxies are acceptable for a bootstrap, not a mature runtime. spaCy/TextDescriptives/CMUdict/wordfreq/retext/Vale now own the areas where they are stronger.

### 6. Tool installation without freezing is fake determinism

`latest` rule packs can change tomorrow. Setup now freezes synced Vale styles, npm/Python dependencies are pinned, and `tool-lock` hashes the resulting environment. Deliberate refresh changes the lock visibly.

### 7. Aggregate “quality scores” invite Goodhart's law

The runtime now calls its aggregate **suspicion/evidence** and preserves the issue vector. The score is a routing signal, not an optimization target.

## What the runtime can establish mechanically

Strongly:

- chronology ordering;
- literal canon triggers;
- POV/reveal state for authored facts;
- explicit fictional mechanics stored as structured data;
- spelling/terminology;
- repeated tokens/phrases;
- lexical bursts;
- exact and near-duplicate paragraphs;
- many grammar patterns;
- parse/readability/frequency/stress metrics;
- output-response shape;
- retry count/no-progress;
- how much salvage would destroy.

Weakly/as evidence:

- stylistic tendencies;
- “AI tell” patterns;
- passive/intensifier/adverb tendencies;
- corpus deviation;
- unusual sentence/rhythm distributions.

Not deterministically:

- beauty;
- emotional resonance;
- whether an image is memorable;
- character charisma;
- thematic depth;
- whether a surprising violation is artistically justified;
- arbitrary semantic paraphrases of a secret that were never authored as disclosure triggers.

The correct response to the last category is not to invent a fake score. It is to give the model the smallest residual judgment task possible and test everything around that task mechanically.

## Situational determinism

The most promising v0.3 concept is not another linter. It is deterministic **routing based on combinations of evidence**.

Example:

```text
paragraph 18
  3 unrevealed fact triggers       HARD
  "fromage" x20                   7.5
  repeated phrase                 3.0
  Harper grammar                  1.5
```

The runtime does not need to understand comedy to conclude that paragraph 18 is contaminated. If a rewrite repeatedly fails, it can deterministically cull paragraph 18 plus adjacent scene context and regenerate the hole while preserving all other prose.

That is an Occam-style fallback: cut the smallest bounded situation supported by evidence, even at the cost of some good local prose, rather than let a model repeatedly mutate an entire chapter.

## Remaining hostile concerns

1. Literal secret triggers need disciplined authoring. A hidden fact with no trigger phrases is invisible to the disclosure gate.
2. Tool consensus is correlated evidence, not independent scientific replication; rules may share assumptions.
3. FTS remains search only. It must never become a silent auto-injection mechanism.
4. `language.sqlite3` is still future work. WordNet/frequency/pronunciation resources should eventually be compiled into a pinned local language library rather than repeatedly loaded from package data.
5. Semantic near-duplicate detection remains lexical. A pinned local embedding model may be worth adding later as low-weight evidence.
6. Scene/plot invariants are not yet a first-class database. Canon covers world/fact truth; a future scene-state table could mechanically track “door is locked,” “weapon already drawn,” inventory, location, injuries, goals, and causal pre/postconditions.
7. Aesthetics remain the irreducible writer-model responsibility. The goal is to make that residual surface smaller, not pretend it does not exist.


## Late tooling sweep

A second search found more deterministic AI-prose linters (plain-english, Slopless, prosesmasher, WritingLint/SlopSift, and @veldica/prose-linter). We integrated **plain-english** and **Slopless** because both expose unattended machine-readable deterministic CLIs and add rhetoric/AI-pattern sensors. We did **not** install every discovered linter: overlapping scorers are documented and rejected unless they add a distinct evidence class.

Slopless' separate textlint stack is intentionally not allowed to become a second authority. Its findings share an evidence family with other AI-style sensors, so cross-tool agreement receives only a bounded consensus bonus.
