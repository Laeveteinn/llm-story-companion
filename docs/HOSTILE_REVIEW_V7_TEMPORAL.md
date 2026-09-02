# Hostile Review v0.7 — Time will break a linear fiction harness

## Finding 1: destructive rewind is unacceptable

If Chapter 3 is rewritten after Chapters 4–20 exist, mutating the current state backwards destroys provenance and makes it impossible to distinguish old consequences from new ones. The correct primitive is an immutable branch at the earliest changed point.

## Finding 2: chapter number is not enough forever

The pilot uses explicit integer timeline ordinals. If a project needs multiple causal moments inside one chapter, declare finer timeline points (scene/beat/event keys). Do not encode ordering in lexicographic strings.

## Finding 3: truth time and knowledge time are different

A secret being true does not make it known. A retcon altering truth does not automatically alter every character's knowledge. Canon facts and reveals stay separate and both are branch-aware.

## Finding 4: a child must not inherit the parent's abandoned future

The branch replay window deliberately caps each ancestor at the next fork. This prevents Chapter 9 facts/events from leaking into a branch forked at Chapter 5.

## Finding 5: time travelers are contamination machines

A traveler arriving from a future must not cause the branch to inherit the entire future context. Carried objects, injuries, memories, or facts are explicit branch-local events/reveals at arrival. This gives the disclosure engine something deterministic to police.

## Finding 6: plans are temporal artifacts

A validated plan is not universally reusable. It belongs to a timeline branch and starting state. Chronobreaks invalidate plans whose preconditions changed. This is desirable collateral damage.

## Finding 7: automatic branch merge is postponed

Story branches are not source-code branches: two individually consistent alternatives can be narratively incompatible without a mechanically obvious merge answer. An automated merge would smuggle semantic judgment back into the deterministic layer. Pilot rule: branch, replay, diff, regenerate, then explicitly promote later.

## Finding 8: event sourcing is prior art, not an automatic dependency

The BSD-licensed Python `eventsourcing` library is mature and should be the first migration target if our persistence/replay layer grows complex (snapshots, projections, concurrency, durable aggregate versioning). For the pilot, our domain event tables plus branch windows remain much smaller than the abstraction cost. Re-evaluate before adding more persistence machinery.
