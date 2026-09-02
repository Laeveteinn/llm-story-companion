# Temporal model — v0.7

The runtime treats chronology as immutable history plus explicit branches. It never rewinds a database in place.

## Three independent axes

1. **Truth time** — when a fact/state is true (`valid_from` / `valid_to`, state event ordinal).
2. **Knowledge time** — when a character learns a fact (`canon_reveal.at` / semantic `learn_fact`).
3. **Timeline branch** — which history the truth/knowledge belongs to (`timeline_branch`).

Conflating these is a continuity bug. A fact can have been true for years but learned today; a retcon branch can replace that fact from Chapter 5 onward without altering the main branch.

## Chronobreak

A chronobreak is a non-destructive branch fork:

```powershell
python write_runtime.py chronobreak `
  --id retcon.ch05 `
  --parent main `
  --at book1/ch05 `
  --kind retcon `
  --out canon_source/retcon.ch05.yaml
```

Then rebuild canon/state. The parent remains intact. The child sees parent events/facts only through its fork point, then its own history. Parent future after the fork is not inherited.

This is deliberately Git-like rather than undo-like.

## Supported temporal uses

- **Editorial rewrite/retcon:** fork at the earliest changed timeline point; repair forward on the child.
- **Alternate history / simulation:** fork with another `kind`; same replay rules.
- **Flashback:** query an earlier ordinal on the same branch; no branch required.
- **Literal time travel that changes history:** fork a `time_travel` branch at the arrival point and encode carried state/knowledge explicitly on that branch.
- **Closed-loop time travel:** may remain one branch, but any earlier knowledge/state still needs an explicit acquisition/event at the earlier ordinal.

## Intentionally unsupported in the pilot

- automatic merge of divergent story branches;
- automatic inference of which consequences survive a retcon;
- inheriting abandoned-future knowledge into a past branch;
- semantic equivalence inference for unencoded secrets;
- destructive rewrite of accepted history.

A later branch promotion/merge must be an explicit transaction with conflicts surfaced rather than silently resolved by an LLM.

## Stale-plan protection

`ChapterPlan.timeline_branch` is contractual. State/canon checks run on that branch. A main-timeline plan reused on a retcon branch is rejected if its preconditions are no longer true. Writer surfaces and provenance carry the branch ID so downstream repair cannot accidentally switch histories.

## Pilot fixture

The bundled fixture contains `retcon.bind_fixed_dc` at `book1/ch05`. On `main`, Sable Bind resistance is later revealed as contested and Mara still owns the knife. On the retcon branch, resistance becomes fixed DC 17 at the fork and the knife ownership is removed. `state-diff` demonstrates the divergence.
