# v0.5.0 Handoff — Single-Model Deterministic Runtime

## Canonical state

This tree is the current clean-room deterministic writing harness. It assumes **one underlying model may perform planning, drafting, and every repair attempt**. Phase labels are not trust boundaries. The Python runtime is the controller; the model only proposes typed plans or bounded prose candidates.

## Verified locally

- `python -m compileall -q writing_runtime` — PASS
- `node --check tools/retext-lint.mjs` — PASS
- `bash -n setup.sh` — PASS
- `python -m pytest -q` — **46 passed**
- two-epoch disclosure compile smoke — PASS
- pre-reveal prompt contains no later fact triggers — PASS
- multi-epoch `persistent_safe` refusal — PASS
- epoch response validation + software assembly — PASS

No GitHub Actions/hosted runners are required or intended.

## Major v0.5 changes

1. **Same-model threat model.** Planner/writer/controller are phases executed by one potentially identical model. Independent-model review is not assumed anywhere.
2. **Context contracts.** `fresh_call` permits author-only planning but requires an empty context for every generation/repair call and discard afterward. `persistent_safe` withholds author-only truth from every prompt and uses reduced retry budgets.
3. **Cycle/no-progress detection.** Candidate SHA-256 and deterministic evidence fingerprints stop A/B oscillation and repeated identical failures from consuming the full rewrite budget.
4. **Localized reinjection.** Hash-bound scene/beat provenance slices the accepted writer plan to the failing beat neighborhood instead of reinjecting the whole plan on every repair.
5. **Plan-language echo evidence.** Exact plan-to-prose n-gram copying is mechanically observable as evidence.
6. **Disclosure epochs.** A fact first revealed mid-chapter is physically absent from earlier generation packets. `draft-prompt` refuses unsafe monolithic drafting; `draft-epochs` produces fresh-call epoch prompts and `draft-epochs-apply` validates/reassembles them.
7. **Future-reveal priming gate.** Literal protected fact phrases in writer goals/directives before their scheduled reveal beat are hard plan failures.

## Trust rules

- YAML is editable source; compiled SQLite is runtime canon/state.
- A model-authored plan is untrusted until `PlanGate` passes.
- Raw analyzer messages never become model instructions.
- Hidden validator phrases remain private; bad source literals are redacted before reinjection.
- A model response never writes directly to accepted text. Contracts and software extraction/reassembly sit in front of mutation.
- Previous model explanations/critic prose are not recursion state.
- Every plan/prose repair state machine is finite.
- A fresh prompt manifest cannot prove an external client actually cleared KV/chat state; the executor must honor it.

## Preferred execution

```text
fresh model call -> plan candidate -> deterministic plan gate
fresh model call(s) -> disclosure epoch prose -> deterministic assembly/gate
fresh model call -> bounded rewrite if needed -> deterministic gate
fresh model call -> Occam gap fill if needed -> deterministic gate
stop: accept or human_review
```

The same GGUF/model/runtime may be reused for every arrow.

## Optional analyzers

The intended deterministic sensor stack remains Vale/Harper/proselint/AiTells, retext, CSpell, plain-english, Slopless, spaCy, TextDescriptives, wordfreq, CMUdict, RapidFuzz, plus optional standalone LanguageTool. Missing optional sensors do not disable canon/plan/contracts/state/repair core behavior.

The container used to build this handoff cannot resolve the full npm/Vale installation, so do **not** treat its partial environment as the production tool lock. The first successful target-machine setup should create `package-lock.json`; subsequent installs use `npm ci`.

## Read next

- `docs/HOSTILE_REVIEW_V5_SINGLE_MODEL.md`
- `docs/SINGLE_MODEL_EXECUTION.md`
- `docs/DISCLOSURE_EPOCHS.md`
- `docs/REINJECTION_FIREWALL.md`
- `docs/DETERMINISTIC_REPAIR.md`
- `docs/HERMES_WORKFLOW.md`
