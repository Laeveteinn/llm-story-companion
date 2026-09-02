# Design: deterministic first, model judgment last

## Three distinct knowledge classes

The runtime should not build one giant RAG soup.

- **Canon:** authoritative fictional truth. Strongly typed, versioned, disclosure-aware, allowed to auto-inject through explicit deterministic triggers.
- **Language knowledge:** dictionaries, lexical networks, frequency tables, pronunciation/stress and linguistic models. Used mechanically by analyzers; normally not injected as prose context.
- **External reference:** research evidence and general-world information. Provenance-heavy, searchable, non-authoritative until deliberately promoted into canon.

## Canon is compiled state

Human-authored YAML is analogous to source code. `canon-build` validates and compiles it into SQLite. The runtime reads only the compiled library.

Important invariants:

- stable canon IDs
- explicit timeline keys and integer ordering
- per-fact validity intervals where needed
- per-actor knowledge and timestamped reveal events
- mechanics stored as executable/data specifications only when intentionally implemented
- literal deterministic trigger semantics
- explicit FTS search kept separate from automatic injection

## Disclosure firewall

`--scope writer` returns authoritative truth/mechanics plus requested viewpoint knowledge. This is useful for simulation and drafting.

`--scope pov` returns only what the viewpoint is allowed to know. It intentionally withholds current truth and mechanics that could leak into narration.

A future validator should add `protected_phrases`/semantic leak rules for facts whose wording must not appear before revelation.

## No scalar “literary quality” objective

The current profile fit score is legacy v0.1 behavior and should not become the optimization target. Great prose is multi-dimensional and several measurable dimensions trade off against each other.

The target architecture is:

1. hard correctness constraints
2. deterministic parser/rule/corpus measurements
3. local anomaly spans with named reasons
4. bounded rewrite attempts on only those reasons
5. aesthetic judgment only after measurable problems are resolved

## Resource policy

Before adding a custom metric, ask:

1. Does a maintained library already calculate it?
2. Does an academic tool/paper define a better version?
3. Is there an open corpus/norm database that supplies the needed reference values?
4. Is the license compatible with how the harness will be used/distributed?
5. Can the resource be pinned by version/checksum so results remain reproducible?

See `RESOURCE_STACK.md`.
