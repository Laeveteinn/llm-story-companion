# Hostile Review v0.7 — Permissive wheels before home-grown machinery

The question is not whether a professional product exists. The question is whether a maintained, model-agnostic, locally controllable component can remove a whole class of code without importing unacceptable licensing/runtime constraints.

## Integrate or adapt directly when useful

- **eventsourcing** — BSD-3-Clause Python event-sourcing infrastructure. Candidate if replay/persistence becomes materially more complex.
- **novel-hint** — MIT, plain JSON/Markdown foreshadowing/book-bible/continuity skill conventions. Useful schema/workflow prior art and potentially directly reusable skill material with attribution.
- **RDFLib + pySHACL** — BSD-3-Clause + Apache-2.0. Use if semantic relations/invariants outgrow simple typed state rows.
- **JsonLogic implementations with permissive licenses** — candidate if our condition syntax begins turning into a language.
- Existing language stack (Vale/Harper, spaCy, TextDescriptives, RapidFuzz, wordfreq, CMUdict, CSpell, retext) remains preferred over home-grown English analysis.

Permissive open source does not require clean-room reimplementation. Use the dependency or adapt source while retaining required notices.

## Benchmark/study, do not make pilot dependencies

- **Bookwright** — installable CLI and unusually close continuity/graph validation prior art, but EUPL-1.2 and its own project representation. Benchmark against planted failures before copying any implementation idea into code.
- **Canon AI** — highly relevant branch/time/knowledge assertion architecture, but heavier infrastructure and no permissive-license assumption should be made without explicit verification.
- **AGPL projects** — useful behavior/design references; avoid source reuse if the project wants to remain permissively distributed.

## Clean-room rule

When avoiding a copyleft implementation, document observable behavior/public interfaces separately from implementation, then build from our own requirements/tests. Do not copy source, tests, comments, distinctive schema text, or expression. This is an engineering policy, not legal advice.

## Kill switch against wheel reinvention

Before adding >~200 lines or a new database subsystem, record:

1. problem/evidence class;
2. maintained candidate libraries/services;
3. license and local/model-control constraints;
4. smallest adapter benchmark;
5. why integration was rejected.

If a permissive library passes most planted failures, delete our implementation rather than preserving it for pride.

## Bookwright benchmark status in this build environment

Runtime benchmark could not be executed because this container cannot currently resolve/install the PyPI package over the network. The pilot therefore does not claim comparative results. A target-machine benchmark recipe is provided separately; this is explicitly deferred rather than guessed.
