# v0.7.1 Handoff — Temporal Recursive Deterministic Writing Pilot

## Canonical state

This tree is the current pilot-ready deterministic fiction runtime. One underlying model may perform every generative phase. The runtime owns authority, chronology, branching, context compilation, contracts, retry budgets, repair routing, and accepted outputs.

## Verified locally

- Python compileall — PASS
- retext JavaScript syntax — PASS
- Bash setup/install wrappers syntax — PASS
- `python -m pytest -q` — **64 passed**
- canon schema v5 rebuild — PASS
- narrative-state schema v3 rebuild — PASS
- main/retcon state diff smoke — PASS
- branch-specific canon fact/reveal/mechanic smoke — PASS
- temporal pilot controller `--prepare-only` — PASS
- no GitHub Actions/hosted runners used

PowerShell is not available in the build container, so `.ps1` wrappers are present but must be exercised on the target Windows machine.

## Major v0.7 changes

1. **Temporal branches.** Immutable `timeline_branch` history replaces destructive rewind. Ancestors are visible only through child fork points.
2. **Three temporal axes.** Fact validity, character knowledge acquisition, and timeline branch remain separate.
3. **Branch-aware mechanics.** Attached mechanics are versioned by branch/time; a retcon cannot inherit obsolete mechanical rules through the author context.
4. **Branch-contract plans.** `ChapterPlan.timeline_branch` is fixed by request manifests and carried into writer surfaces. Stale main-timeline plans fail if retcon state invalidates their preconditions.
5. **Chronobreak CLI.** `write_runtime.py chronobreak` creates a non-destructive YAML branch overlay and refuses silent overwrite.
6. **Temporal inspection.** `state-branches`, `state-history`, and `state-diff` expose branch replay/differences mechanically.
7. **Automated Hermes install.** Git checkout installer resolves/detaches a commit, verifies required runtime files, records the source commit, and runs bootstrap.
8. **Pilot controller.** `integrations/hermes/pilot_controller.py` executes plan -> finite plan repair -> disclosure epochs -> finite prose repair using fresh Hermes subprocess calls.
9. **Open-source wheel gate.** Permissive maintained components must be evaluated before growing another subsystem; Bookwright is an external benchmark, not a dependency.

## Temporal pilot fixture

`retcon.bind_fixed_dc` forks `main` at `book1/ch05`.

- `main`: Sable Bind later reveals contested resistance and Mara retains the knife.
- retcon branch: resistance is fixed DC 17 from the fork and knife ownership is removed.
- branch-specific mechanic resolution also changes to fixed DC 17.

A stale copy of the main example plan moved onto the retcon branch is intentionally rejected because its knife-possession precondition no longer holds.

## Execution modes

- **fresh_call**: required for strong disclosure isolation and the pilot controller. Same model is fine; every generative call starts empty and is discarded afterward.
- **persistent_safe**: degraded interactive fallback. Hidden author truth is withheld from every prompt; multi-epoch isolation is refused.

## GitHub/public install boundary

The runtime contains a deterministic clone/install script, but the connected GitHub API exposed to this build does not provide repository visibility mutation. The existing `Laeveteinn/llm-story-companion` repository therefore cannot be made public by this runtime. Once the repository is public *and contains the expanded source tree*, Hermes/user setup can be one unattended install command. No GitHub compute is needed.

## Bookwright benchmark

Bookwright's published CLI can be installed via `uvx --from bookwright-cli ...`, but this build container cannot resolve/install the package over the network. No benchmark result is claimed. `benchmarks/bookwright/README.md` defines planted comparison failures for a target-machine run.

## Read next

- `docs/TEMPORAL_MODEL.md`
- `docs/HOSTILE_REVIEW_V7_TEMPORAL.md`
- `docs/HOSTILE_REVIEW_V7_OPEN_SOURCE_WHEELS.md`
- `docs/SEMANTIC_NARRATIVE_STATE.md`
- `docs/HOSTILE_REVIEW_V6_HERMES.md`
- `integrations/hermes/README.md`
