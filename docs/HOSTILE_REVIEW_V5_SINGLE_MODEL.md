# Hostile Review v0.5 — One Model, Many Phases

## Premise

The runtime must assume that planning, drafting, repair, and any model-side "controller" work may all be performed by the **same model**. Role names are conveniences, not independent judges and not security boundaries.

The deterministic runtime is the controller. The model only proposes artifacts.

## Critical flaw found in v0.4

v0.4 correctly removed hidden author information from the *writer prompt*, but it implicitly assumed the writer had not already seen that information. If one continuing model conversation first receives author-only canon during planning and later receives a writer-safe packet, the secret is still in model context.

A prompt firewall cannot make a model forget previous turns.

Therefore this configuration is unsupported as a security/disclosure claim:

```text
one persistent context
  -> show hidden author truth during planning
  -> later say "writer phase: forget the hidden truth"
```

No amount of prompt wording makes that isolation real.

## Supported execution modes

### `fresh_call` — preferred

The **same model weights/binary may be reused for every phase**, but every model invocation starts with an empty inference/conversation context and is discarded after the response.

Consequences:

- planning may receive author-only canon/state;
- drafting receives only the mechanically lowered writer packet;
- repair receives only current source + compiled deterministic findings;
- rejected model explanations/output history is never forwarded as conversational history;
- call manifests explicitly mark `requires_fresh_context=true` and `discard_context_after_response=true`.

This is the strongest available isolation without separate models.

### `persistent_safe` — degraded fallback

A single continuing model context is permitted only if **author-only/hidden runtime data is never injected into it at all**.

Consequences:

- planning uses POV-safe canon rather than author-scope canon;
- planning state is restricted to `writer_safe` state;
- the full canon inventory is withheld because entry names can themselves be spoilers;
- invalid plan repair redacts literal protected triggers before re-showing the plan;
- repair budgets are reduced because the model remains anchored to its own prior outputs;
- manifests mark `isolation_grade=degraded`.

This mode cannot provide author-aware planning for secrets the model is forbidden to know. That is a real capability tradeoff, not something prompts can solve.

## Unsupported mode

`persistent_author_aware` is intentionally not implemented.

It would mean the same continuing model context sees hidden truth and later writes POV-limited prose. The runtime could still detect many literal leaks after generation, but it could not claim prevention and could not detect arbitrary semantic paraphrases of remembered secrets reliably.

## Same-model failure modes and mechanical mitigations

### 1. Self-anchoring

The same model tends to preserve its own earlier structure and errors when asked to revise.

Mitigations:

- deterministic findings, not model critique, drive retries;
- previous rejected explanations are never forwarded;
- exact candidate/evidence cycles are detected;
- `persistent_safe` gets a smaller rewrite budget;
- repeated/no-progress failure escalates to Occam salvage rather than another whole rewrite;
- salvage freezes good paragraphs and only regenerates bounded holes.

### 2. Planning-language contamination

A model may copy its own plan wording directly into narration.

v0.5 adds `plan.prose_plan_echo`, a deterministic exact n-gram detector over writer-facing plan fields. It is evidence, not a hard literary law, but it makes obvious plan-to-prose leakage measurable.

### 3. Reinjection bloat

Giving the full plan back on every repair makes the same model repeatedly anchor on irrelevant instructions.

v0.5 slices writer-plan reinjection to the affected scene/beat neighborhood when hash-bound provenance identifies one. The complete accepted plan remains authoritative outside the model.

### 4. Recursive grade gaming

If the model sees score formulas or is allowed to explain why it should pass, it can optimize the representation rather than the story.

Mitigations:

- the model does not decide pass/fail;
- thresholds remain runtime policy, not rewrite objectives;
- reinjection uses fixed directive templates rather than raw analyzer prose;
- prompts explicitly forbid score optimization;
- contract validation rejects plans/explanations in prose slots.

### 5. Oscillation

A model can alternate between two bad solutions indefinitely.

Mitigation: bounded state machines plus evidence/candidate cycle fingerprints. Recursion is finite even when the model keeps producing plausible but non-improving variants.

### 6. Same-model "review" is not independent evidence

A model criticizing its own output is not counted as a deterministic sensor and cannot add independent consensus weight. Only mechanical tools, typed stores, and explicit corpus measurements contribute to the evidence bus.

## Reinjection rule

The next model call is compiled from:

```text
authoritative source-of-truth records
+ current candidate/source material
+ allowlisted deterministic issue codes
+ typed scalar evidence
+ localized provenance
+ fixed repair templates
```

It is **not** compiled from:

```text
previous model explanation
previous critic prose
raw linter messages
free-form summaries of failures
hidden validator terms
unbounded conversation history
```

This is the core contamination defense.

## Remaining hard limit

Fresh prompts can be enforced by an orchestrator, but the Python runtime cannot cryptographically prove that an external model client actually cleared its KV/conversation context. v0.5 therefore emits hash-bound call manifests describing the required context contract. Hermes/Codex/local API adapters must honor that contract.

If the executor cannot create a fresh context, it must select `persistent_safe`; it must not pretend `fresh_call` happened.

## Disclosure-epoch follow-through

The within-chapter priming problem is now implemented rather than left as a proposal.

When a protected fact first becomes available at the chapter's timeline ordinal and the accepted plan assigns it to a `reveal_facts` beat:

- `plan.future_reveal_priming` rejects literal fact triggers in chapter/scene/beat writer fields before that beat;
- `draft-prompt` refuses monolithic generation;
- `draft-epochs` splits the chapter at knowledge changes;
- pre-reveal packets remove the scheduled future fact from POV-safe canon and knowledge surfaces;
- the reveal epoch explicitly unlocks the fact;
- the private manifest retains future literal triggers for response validation without showing them to the model;
- multi-epoch generation requires `fresh_call` and refuses `persistent_safe`;
- software reassembles independently returned beat blocks in accepted plan order.

This prevents a configured future fact from entering an earlier prompt. It does **not** solve unrestricted semantic equivalence: if a secret can be paraphrased without any configured trigger or typed representation, a deterministic text gate cannot know that arbitrary sentence means the same hidden thing.

## Further hostile conclusions

### Role prompts are not diversity

Running `planner`, `critic`, and `writer` prompts against the same model does not create independent evidence. At best it changes conditioning. No same-model critique is counted as independent consensus in the evidence bus.

### More recursion can reduce information

Every generative rewrite is destructive as well as constructive. Therefore recursion is not a default quality strategy. The router spends a small rewrite budget, detects no-progress/cycles, then narrows the writable surface through Occam salvage. "Think/rewrite again" is never an unbounded fallback.

### The plan is not a memory

Accepted plan JSON is a typed constraint artifact, not a conversational summary of what the model previously thought. Repairs receive only an allowlisted slice derived from current failures and hash-bound provenance. Rejected plan prose and model rationales are disposable.

### Mechanical evidence can still be wrong in aggregate

Ten correlated style linters do not equal ten independent witnesses. Evidence is grouped/bounded by source/family, and subjective sensors remain low weight. Hard failure is reserved for contracts, canon/disclosure, typed state/causality, and explicit plan obligations.

### The controller cannot prove executor honesty

A call manifest can require a fresh context and hash-bind the exact prompt, but an external client can still lie or accidentally reuse KV/chat state. The runtime must fail closed when an adapter cannot guarantee a new session; it cannot infer freshness from a model's behavior.

## Remaining frontier

The next useful mechanical frontier is **semantic-state coverage**, not more role prompts: richer explicit scene state, causal pre/postconditions, entity possession/location, knowledge acquisition routes, and high-value semantic equivalence rules for secrets whose leakage cannot be represented adequately by literal triggers alone. Formal solvers (for example Z3) become useful only where those constraints are actually formalized; they should not be used to fake deterministic understanding of aesthetics or emotion.
