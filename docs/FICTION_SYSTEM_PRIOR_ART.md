# Fiction-system prior art to benchmark before expanding the runtime

This file exists because the first resource sweeps were not hostile enough.

## Bookwright — highest-priority replacement/adapter candidate

Current public Bookwright is a spec-driven long-form authoring CLI. It installs as `bookwright-cli`, builds a derived GOLEM knowledge graph, and exposes deterministic `bookwright graph build` / `bookwright validate` commands for continuity. It also separates deterministic graph validation from semantic/LLM-assisted manuscript checks.

Why it matters: this overlaps directly with canon/chronology/focalization validation we are building. Before adding major graph/ontology complexity, create a fixture-level comparison:

- can our canon YAML/state be losslessly represented in its source documents/GOLEM graph?
- can its deterministic validator catch our planted location/knowledge/possession/timeline failures?
- can we invoke it as an external oracle without forcing our whole project into its authoring format?
- is adopting its EUPL-1.2 runtime boundary acceptable for the intended distribution?

Do not vendor/copy its code casually. Treat it as an external CLI/replacement candidate.

## Canon AI — temporal assertion doctrine

Canon AI is a serialized-fiction continuity engine centered on temporal, branch-aware assertions with scene citations and deterministic SQL checks. Its strongest ideas overlap our disclosure/state goals: truth-at-time, who-knows-what-when, source-backed findings, and deterministic queries instead of model recall.

It is not a drop-in dependency: it is Postgres/Supabase-oriented, screenplay-first, and includes LLM extraction stages. Use it as prior art and a benchmark for our assertion/check design.

## Novel Studio AI — acceptance/promotion prior art

Novel Studio AI is a local-first full application using SQLite character states, relation triples, timelines, context packs, and accepted-chapter promotion. Most relevant rule: drafts do not update canon; accepted chapters do. That matches the v0.6 semantic-state boundary and is further evidence that plan effects must not be promoted simply because they were intended.

## Other useful references

Interactive-fiction engines such as Quilltale validate structured world transitions before narration. They are useful prior art for inventory/location/action preconditions but optimize for game turns rather than long-form prose.

## Benchmark-first rule

A new fiction-specific subsystem should start with a search/benchmark task, not implementation. If a maintained system already solves 80–90% of the same deterministic problem, prefer:

1. external invocation/adapter;
2. file-format bridge;
3. selectively adopting its public data model/concepts where licensing permits;
4. replacement;

before writing a parallel implementation.

## v0.7 permissive components

The pilot should prefer locally controllable permissive components when they remove a complete evidence class:

- `pyeventsourcing/eventsourcing` (BSD-3-Clause): mature event-sourcing persistence/replay if our branch ledger outgrows the current thin SQLite implementation.
- `chianglianglin/novel-hint` (MIT): plain JSON/Markdown hint ledger, book-bible, continuity, and voice skill conventions; useful directly or as schema/workflow prior art.
- RDFLib (BSD-3-Clause) + pySHACL (Apache-2.0): candidate if relation/invariant logic becomes an ontology rather than a small state table.
- MIT JsonLogic implementations: candidate if condition expressions begin becoming a bespoke language.
- Novalist/Novel Studio are useful MIT application prior art but are not pilot dependencies because integrating whole desktop applications would add more surface than they replace.

Bookwright remains the closest turnkey continuity validator found so far, but its EUPL-1.2 license and project-format ownership make it a comparison target rather than a required component for this pilot.
