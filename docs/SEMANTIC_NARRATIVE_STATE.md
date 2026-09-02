# Semantic narrative state

v0.6 adds a deterministic semantic layer on top of the existing replayable state engine. The goal is not to understand arbitrary prose. The goal is to make common continuity-changing intentions executable before prose is generated.

## Typed subjects

`state_source/*.yaml` may declare subjects as characters, items, locations, factions, objects, concepts, or other. SQLite stores this registry with writer-safety metadata. State remains keyed data, so unusual project-specific rules do not require a new schema.

## Typed semantic actions

Plans may use:

- `move`
- `acquire`, `transfer`, `consume`
- `injure`, `heal`
- `disable_capability`, `enable_capability`
- `spend_resource`, `gain_resource`
- `learn_fact`
- `make_promise`, `resolve_promise`
- `enter_scene`, `leave_scene`

The runtime derives preconditions and low-level state mutations. Examples: transfer requires current possession; spending cannot underflow a resource; a blocked `move` capability prevents movement; a resolved promise must be open; an unauthorized `learn_fact` is rejected by the canon/disclosure gate.

## Cross-record audits

After semantic effects, the gate mechanically checks invariants including duplicate possession, item-owner/inventory disagreement, item/owner location disagreement, negative resources, impossible promise state, and invalid registered locations. Beat kinds also imply capability requirements (`dialogue -> speak`, `reflection/decision -> think`, `action/conflict -> act`, `transition -> move`).

Run an independent snapshot audit with:

```powershell
python write_runtime.py state-audit --at book1/ch05 --json
```

## Critical boundary

A valid plan is still **intended state**, not automatically observed manuscript truth. Passing a plan must not silently promote its effects into accepted long-term state merely because prose was supposed to realize them. Promotion needs accepted manuscript provenance plus deterministic/explicit reconciliation. Until robust semantic extraction exists, the authoritative persistent ledger should advance only through an explicit acceptance/reconciliation step.

This is deliberate. The runtime can prove that a proposed plan is internally executable; it cannot deterministically prove that arbitrary literary prose semantically enacted every intended effect.

## Escape hatch

Project-specific magic, economics, combat, social rules, and other unusual mechanics continue to use generic typed conditions/effects. Do not grow the semantic action vocabulary merely to encode every fictional verb. Add a semantic primitive only when it eliminates repeated low-level bookkeeping and has crisp deterministic preconditions/effects.
