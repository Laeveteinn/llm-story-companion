# Hostile Review v0.6 — Stop reinventing the wheel

The runtime's value is fiction-specific authority, disclosure, provenance, bounded repair, and narrative state. It should not become a 200-step imitation of mature NLP/editorial software.

## Deletion rule

A custom subsystem must survive three questions:

1. Does a maintained deterministic library/CLI already own this evidence class better?
2. Does our implementation add fiction-specific semantics rather than merely duplicate generic NLP/editorial behavior?
3. Would replacing it remove meaningful code/maintenance without weakening provenance or determinism?

If the answers favor the library, delete ours.

## Current decisions

| Problem | Mature machinery | Decision |
|---|---|---|
| Grammar/mechanical usage | Vale + Harper; optional LanguageTool | External tools own generic grammar. Custom code only normalizes evidence and adds fiction rules. |
| Editorial lint | Vale packages, proselint, retext, plain-english, Slopless | Use as low/medium-weight sensors; do not create ten correlated votes or treat stylistic advice as law. |
| Spelling/terminology | CSpell + canon dictionary export | External tool owns spelling. Runtime owns canonical term generation. |
| Tokenization/POS/dependencies/entities | spaCy | Do not grow regex substitutes. |
| Readability/descriptive/dependency/quality metrics | TextDescriptives | Use directly. v0.6 also requests information theory; semantic coherence is attempted separately so failure cannot disable core metrics. |
| Lexical frequency | wordfreq | Keep external. |
| Pronunciation/stress | CMUdict | Keep external. |
| Local fuzzy duplicate detection | RapidFuzz | Keep at chapter scale. |
| Book/corpus-scale near duplicates | datasketch/MinHash-LSH | Integrate only when O(n^2) comparison becomes material. Do not write our own LSH. |
| Relational storage/search | SQLite + FTS5 | Keep. It is exactly the right boring machinery. |
| Large graph/ontology constraint validation | RDFLib + pySHACL | **Future threshold:** if custom cross-record semantic audits become numerous/ontology-like, migrate those constraints to SHACL rather than creating our own ontology engine. Do not migrate today's small state just for fashion. |
| Generic policy expression language | JsonLogic-family implementation | Do not add yet. Our condition set is small/typed. If policy authorship grows into a DSL, replace rather than expand ours indefinitely. |
| Workflow finite-state machine | `transitions` | Reject for now: our bounded router is smaller than the dependency abstraction. Revisit if workflow becomes hierarchical/async. |
| Formal satisfiability/planning | Z3 / Unified Planning | Use once rules are genuinely formalized. Never use a solver to fake deterministic emotional/aesthetic understanding. |
| Professional-style calibration | approved/private corpus + lawful public-domain corpora + external metrics | There is no universal deterministic “professional prose” score. Calibrate measurable distributions; leave residual aesthetics to generation/human judgment. |
| Long-form fiction continuity CLI | **Bookwright** (`bookwright-cli`) | This is the closest current wheel we found: spec-driven canon, derived knowledge graph, deterministic `bookwright graph build` / `bookwright validate`, provenance, chronology/focalization checks. **Do not blindly duplicate it.** Before expanding our canon/state graph substantially, benchmark it against our fixtures. Its EUPL-1.2 code and its own project format make adapter/replacement evaluation preferable to copy-paste vendoring. |
| Serialized-fiction temporal canon engine | **Canon AI** | Strong prior art for timestamped/branch-aware assertions, knowledge timing, citations, and deterministic SQL checks. It is heavier (Postgres/Supabase, screenplay-oriented, LLM extraction) and not a drop-in library for our local SQLite harness, but its assertion/check doctrine should be treated as a reference implementation, not rediscovered from scratch. |
| Local AI novel workbench | Novel Studio AI | Strong prior art for accepted-chapter-only canon promotion, SQLite graph facts/character state/context packs. It is a full TypeScript application rather than a reusable validator; borrow architecture concepts, not another parallel app stack. |

## The embarrassing finding

The earlier hostile passes still missed several active fiction-specific systems. In particular, Bookwright already ships a CLI that derives a knowledge graph and runs deterministic continuity validation, while Canon AI implements temporal/knowledge assertions plus SQL continuity checks with source citations. That does **not** make either a drop-in replacement for this runtime, but it proves the field is further along than our first survey suggested.

New rule: before adding a new graph store, ontology layer, continuity query language, manuscript fact extractor, or large family of cross-record checks, first benchmark the corresponding mature fiction system/library against our fixtures. “We can code it ourselves” is no longer sufficient justification.

## Correlated-sensor trap

Five linters flagging the same passive construction are not five independent pieces of evidence. Evidence aggregation must remain family/source bounded. Tool count is not intelligence.

## The real product boundary

Libraries should own **language mechanics**. This project should own:

- authoritative canon and disclosure state;
- narrative chronology and semantic state;
- plan/prose provenance;
- context compilation and secret redaction;
- hard output contracts;
- finite recursion/cycle detection;
- deterministic routing and Occam salvage;
- project-specific policy and calibration.

Anything outside that list is presumed guilty of wheel reinvention until justified.
