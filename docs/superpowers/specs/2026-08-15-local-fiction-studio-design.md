# Story Companion Studio 1.0 — Product and Architecture Design

Date: 2026-08-15
Status: Approved design
Repository: `D:\MyWork\llm-story-companion\llm-story-companion`

## 1. Product definition

Story Companion Studio is a fully local Windows application for planning, drafting, validating, and maintaining long-form fiction. Its primary success case is one user action that produces an acceptable chapter, arc, or book without requiring approval between internal stages.

“First time” means one completed production run, not one raw model completion. A run may plan, draft, run deterministic checks, obtain a blinded reader reconstruction, make bounded targeted repairs, and revalidate. Execution state and promotion outcome are separate:

- a stage attempt is `queued`, `running`, `succeeded`, `failed`, or `cancelled`;
- a chapter run is `queued`, `running`, `succeeded`, `failed`, or `cancelled`, with promotion outcome `pending`, `completed`, `needs_review`, `completed_with_waiver`, or `accepted_text_state_pending`;
- an arc/book run is `queued`, `running`, `paused`, `completed`, `partial_needs_review`, `failed`, or `cancelled`, and records `committed_through_chapter` plus `blocked_at_chapter`.

Atomicity is per chapter. A `needs_review` chapter remains unpromoted, but earlier chapters from the same longform run remain accepted. A hard failure or review requirement stops downstream generation. `accepted_text_state_pending` records an explicit editorial acceptance of the prose without advancing the accepted manuscript or continuity head; it blocks all dependent generation until its state ledger is reconciled and promoted.

The system optimizes for good first-run results but does not claim that every premise, model, seed, or genre will produce publishable prose. Literary quality is tested comparatively against frozen baselines; continuity, authority, provenance, transaction safety, and information isolation are enforced as product contracts.

Normal inference, retrieval, tool execution, storage, evaluation, and telemetry stay on the local machine. The application remains usable with networking disabled after installation.

## 2. Chosen approach

The product will be built fresh in the clean nested Git repository and will selectively reimplement or migrate proven behavior from the existing projects.

### Alternatives considered

1. **Extend the KoboldCpp fork.** Rejected because inference, MCP, workflow, state extraction, and critique are coupled inside a very large launcher; the local fork also has substantial uncommitted changes. Direct code reuse would add an AGPL boundary and ongoing upstream-merge cost.
2. **Extend the unversioned outer Story Companion.** Rejected as the final boundary. It is the best UI and writing-pipeline prototype, but it is tied to LM Studio, conflates author knowledge with writer-visible context, promotes weakly grounded model deltas, and cannot own model lifecycle or safe tools.
3. **Fresh modular studio with selective migration.** Chosen. It preserves proven UX and process ideas while repairing runtime, authority, transaction, provenance, and information-flow boundaries.

The application is all-in-one to the user and modular internally. The GUI, local API, workflow engine, project store, tool host, and inference runtime communicate through explicit interfaces and can be tested independently.

## 3. System architecture

```text
Browser GUI (React/TypeScript)
            |
      loopback HTTP/SSE
            |
Local Studio Service (Python/FastAPI)
  |          |           |            |
Projects   Workflow    Tool Host    Runtime Manager
  |          |           |            |
SQLite +   role-scoped  reviewed     pinned llama-server
files      artifacts    manifests    external adapters
  |                                      |
FTS + local embeddings              CUDA / RTX 4080
```

The repository is a small monorepo:

```text
apps/
  server/                 Python service and packaged entry point
  web/                    React/TypeScript GUI
packages/
  narrative/              authority, canon, context, causality, retrieval
  workflows/              persistent DAG and writing stages
  runtimes/               llama.cpp, LM Studio, KoboldCpp adapters
  tools/                  capability manifests and reviewed tool host
  policies/               generic-fiction and LitRPG policy packs
  evaluation/             deterministic and blinded quality harness
tests/
  unit/ integration/ golden/ live/
runtime-manifests/         pinned binaries, hashes, capabilities
docs/
```

The Python service is a modular monolith, not a collection of network services. FastAPI provides typed local APIs and streaming; Pydantic defines boundary schemas; SQLite provides transactions, FTS5, and durable jobs. The frontend uses React, TypeScript, Vite, TanStack Query, and accessible headless primitives. Production builds are served by the Python service and opened automatically in the default browser. A packaged Windows executable is an output of the same service rather than a separate desktop implementation.

### 3.1 Loopback security contract

“Local” is not treated as authentication. The Studio service and managed runtime bind to `127.0.0.1` on reserved ephemeral ports, not wildcard interfaces. The launcher opens a one-time bootstrap URL; the server consumes its unguessable secret, redirects to a clean URL, and issues an `HttpOnly`, `SameSite=Strict` session cookie plus an in-memory CSRF token. Mutating APIs require the CSRF token and an exact same-origin `Origin`; all requests require an exact `Host`. CORS is disabled, the frontend uses a restrictive Content Security Policy, secrets are redacted from logs, and a new capability secret is generated each launch.

The managed llama server uses a separate random API key known only to Studio, exposes no browser UI, and binds to its own loopback port. Studio launches it from an allowlisted argument builder with parallelism one and without router auto-loading, model-directory serving, built-in tool execution, MCP, or file/media features not required by the adapter. The threat model reduces attacks from hostile webpages, DNS rebinding, and accidental network exposure; it does not claim protection from another process already running as the same Windows user.

## 4. Runtime and model management

### 4.1 Primary runtime

The first-class runtime is a pinned official Windows CUDA build of [`llama-server`](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md). It runs as a supervised child process and is never imported into the application. Each runtime manifest records upstream version, every required archive and DLL, download URL, SHA-256, license/notice, supported flags, and probe results. The repository and normal installer do not redistribute the large runtime bundle: first-run setup explicitly downloads the pinned official artifacts or imports an offline bundle, verifies every hash, and extracts into a versioned application-data cache. A successful cache can be exported for offline reinstall. Hash or license failure deletes only the incomplete temporary extraction and leaves prior runtimes intact.

Automatic llama self-update is disabled. Upgrades require a new reviewed manifest, install beside the old runtime, and invalidate affected profiles; “latest” is never substituted silently for a tested build.

LM Studio and KoboldCpp remain external compatibility/baseline adapters. The managed llama.cpp path is the only required 1.0 runtime. An external adapter is advertised as supported only after its conditional live suite passes on an installed instance; its absence or an explicitly unsupported capability does not block the managed-runtime release.

### 4.2 Adapter contract

Every runtime adapter reports a typed capability matrix and exposes the operations it supports:

- capability and version probing;
- model discovery and stable model identity;
- load, unload, start, stop, health, cancellation, and crash diagnostics when supported;
- streamed chat/structured generation;
- embeddings and reranking when supported;
- effective context, batch, GPU-layer, KV-cache, Flash Attention, and sampler settings;
- observed prompt/decode speed, peak memory, provable placement signals, and finish reason.

Unsupported lifecycle or telemetry operations return a typed `unsupported` result and cannot be selected by workflows that require them.

Only one GPU generation job runs at a time, and the managed server is launched with parallelism one. Multiple resident writer models are not assumed on a 16 GB card. Role-specific model switching is supported, but a profile enables it only when benchmarked quality gain outweighs reload cost.

### 4.3 Calibration, not guessed “best settings”

Hardware fit and creative quality are separate problems.

The calibrator reads GGUF metadata without loading tensors, measures current GPU/driver/display reservation for five seconds, and proposes bounded configurations. It then performs a real trial load plus representative prefill/decode and context-stress probes. Profiles are keyed by model hash, runtime build, GPU identity, driver, and memory envelope.

The default fit policy is:

1. target a 1.5 GiB physical-VRAM reserve; a stress-tested `tight` profile may use a reserve down to 512 MiB, while anything smaller is rejected;
2. prefer full model and KV residency on GPU;
3. enable Flash Attention when the capability probe passes;
4. lower requested context to the operation's measured need before sacrificing GPU layers;
5. try Q8 KV, then a quality-qualified Q4 KV profile;
6. reduce batch sizes before partial model offload;
7. reject silent shared/system-memory spill;
8. offer CPU offload only as a visibly labeled slow-mode override.

Calibration samples NVML/NVIDIA process counters, Windows GPU Process Memory dedicated/shared counters, host working set, and version-specific llama startup logs every 250 ms from pre-load baseline through the stress probe. A profile is invalid when the runtime reports CPU model layers or host KV contrary to policy, when shared GPU usage rises more than 64 MiB above baseline for two seconds, or when required counters/log fields are unavailable. Unverifiable profiles are never chosen by Auto. The UI distinguishes observed dedicated/shared memory from placement inferred from runtime logs; it does not claim an unavailable per-buffer hardware measurement.

WeirdCompound may remain a comparison or explicit slow-mode model if no verified no-spill profile fits the actual desktop envelope. In that case Model Lab recommends a lower quantization of the same model or another benchmarked writer rather than weakening the resource contract.

The role benchmark separately scores models/settings for drafting, structured extraction, cold reading, and critique. WeirdCompound is the frozen creative baseline, not a presumed winner. Speculative decoding is opt-in and retained only when measured prose workloads improve end-to-end throughput without a quality regression.

## 5. Project, authority, and provenance model

Each project is a self-contained directory. SQLite is the transactional authority; Markdown and JSON files are materialized, human-readable views and export surfaces. `project.json` is only the portable bootstrap manifest: project identity, schema version, database path, materialization paths, and required application version. It does not duplicate mutable canon or workflow state.

```text
project.json
studio.db
manuscript/
knowledge/
voice/
policies/
artifacts/runs/
snapshots/
exports/
```

Accepted prose, structured facts, and revisions live as immutable revisions in SQLite. A materializer writes chapter Markdown after a successful transaction. Direct file edits are detected by hashes and imported as candidate divergences requiring reconciliation; they never overwrite accepted prose or canon silently.

### 5.1 Authority precedence

Facts carry authority, epistemic status, visibility, provenance, and supersession metadata. Precedence is:

1. explicit accepted user rule or retcon;
2. accepted manuscript evidence;
3. explicit user-authored world canon not yet contradicted by the manuscript;
4. structured observed state derived from accepted manuscript evidence;
5. approved future outline and current scene contract;
6. project reference material;
7. proposed extraction or model invention.

Accepted manuscript evidence defeats a conflicting derived state record. A user-authored world rule that conflicts with accepted prose creates a reconciliation conflict; only an explicit retcon can override the prose. Plans never become observed facts merely because a chapter was intended to contain them. Reviews, summaries, retrieved sources, and model memory cannot promote canon.

Initial imports are staged with source hashes and an authority preview. Material explicitly accepted as user-authored canon enters at rank 3; imported manuscript enters at rank 2; extracted structure enters only at rank 4 after grounding. Promotion rechecks the accepted project revision and every source hash used by the candidate.

### 5.2 Core records

The schema includes:

- projects, settings, revisions, chapters, scenes, and immutable run artifacts;
- entities, aliases, attributes, relationships, locations, items, and ownership;
- events with time windows, location, participants, preconditions, effects, and causal edges;
- character-knowledge claims with acquisition route, precision, evidence, and retransmission limits;
- open threads, promises, questions, setups, payoffs, and outline beat identities;
- sources, hashed chunks, citations, FTS terms, embeddings, and retrieval decisions;
- fact proposals, conflicts, retcons, supersession links, and promotion transactions;
- jobs, stages, attempts, tool calls, model calls, settings, timings, and resource telemetry.

### 5.3 Visibility lanes

Records and artifacts are assigned one or more explicit lanes:

- `accepted_canon`
- `author_only`
- `controller_only`
- `writer_eligible`
- `critic_only`
- `external_reference`
- `hidden_future`
- `quarantined`

Visibility is enforced by queries and schemas, not prompt instructions. Cross-project identifiers are included in every cache/index key and validated before prompt assembly.

### 5.4 Schema, backup, and retention

Every database migration is forward-only, transactional where SQLite permits, and preceded by a byte-for-byte database backup plus manifest hash. Exports contain a versioned schema manifest and lossless JSONL representations of structured records alongside manuscript files. Import migration never modifies the source archive.

Accepted prose, canon revisions, retcons, promotion records, and benchmark results are never removed automatically. 1.0 performs no destructive background culling. The UI reports storage use and offers an explicit prune action for failed-attempt streams, temporary indexes, and regenerated caches; it creates a backup before pruning durable run evidence.

## 6. Retrieval and context compilation

Retrieval is local, provenance-first, and role-scoped. 1.0 ingests UTF-8 Markdown, plain text, JSON, and the application's exported archive format. Source files are hashed and chunked along semantic boundaries while preserving line/offset locations.

Candidate retrieval combines SQLite FTS5 with local embeddings. The pinned default is the official Apache-2.0 [`Qwen/Qwen3-Embedding-0.6B-GGUF`](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF) Q8_0 model, run through the same pinned llama.cpp bundle with GPU layers disabled. It produces 1024-dimensional embeddings and supports 32K input; setup downloads it only after showing its license and verifying a manifest hash, or imports it from an offline bundle. The model remains CPU/RAM-resident so it does not evict the writer from VRAM.

The initial vector implementation stores normalized float16 vectors in a generation-stamped memory-mapped matrix and uses NumPy float32 cosine scoring. It supports at most 100,000 active chunks per project in 1.0. Index identity includes source hashes, embedding model hash, tokenizer, instruction, dimensions, and chunker version. Rebuild writes a new generation and atomically swaps the active pointer only after count/hash verification. SQLite FTS5 and structured entity/causal queries remain available if the embedding process is offline; Auto marks semantic recall degraded rather than silently pretending equivalent retrieval. Optional reranking occurs only in controller context.

Search locates evidence; it does not merge authority. Each result retains source, span, hash, authority, visibility, chronology, and reason selected. Conflicting sources are surfaced to the controller and resolved by precedence or marked disputed.

The deterministic context compiler admits only information required by the current scene:

- scene contract: POV, tense, voice, length, goal, conflict, required beats, and exit state;
- relevant cast/location/item state;
- causally required prior events and preconditions;
- character-knowledge boundaries;
- open promises due in this scene;
- local prose lead-in and a small set of project-owned voice examples;
- current-scene constraints derived from the approved outline; future beat text remains controller-only.

It budgets with the target tokenizer, records every admitted and rejected item, and reduces lower-priority evidence rather than truncating canon silently. Large context is not an objective; smallest sufficient context is.

## 7. Contamination firewall

The LitRPG process is generalized as typed information flow, not copied as a universal prompt.

The controller may inspect canon, references, tools, plans, conflicts, and hidden material. The writer cannot. Durable visibility is only the upper bound on access: writer admission is a per-run grant keyed by `{project_id, accepted_revision, run_id, stage, scene_id, pov}` and re-evaluated against chronology and character knowledge. No record is globally “writer safe” for every scene.

The workflow has distinct versioned manifest schemas for controller, writer, critic, blind reader, repair, and state clerk. The writer receives a host-compiled packet containing plain declarative facts with anonymous source IDs, must/must-not constraints, the local lead-in, project-owned voice evidence, and at most one selected craft protocol. Voice excerpts require an explicit project-owner authorization record, source hash, and quote budget; external/library prose cannot be authorized as voice evidence by default.

The writer never receives:

- raw external prose or research passages;
- source titles/authors unless narratively required;
- controller reasoning or tool traces;
- router/policy vocabulary;
- raw critic findings or audit-policy vocabulary;
- hidden future beats or unrestricted character secrets;
- other projects' records.

Critic results are converted by host code into span-specific plain repair instructions containing the observable problem, required fact/outcome, and permitted edit scope. The repair model never sees raw critic prose or scores.

The firewall is tested with seeded sentinels, cross-project canaries, required-fact round trips, prompt-manifest snapshots, repeated-phrase scans, and lexical/semantic similarity warnings against external reference sources. These checks reduce information-flow and copying risk; they do not claim to detect a model's training-data contamination.

## 8. Writing workflow

### 8.1 Persistent stage graph

Each chapter is a durable workflow. Deterministic stages are reusable only under an exact fingerprint; stochastic model calls are immutable attempts, not assumed idempotent:

1. **Preflight** — verify project version, runtime profile, source hashes, policy pack, and resource headroom.
2. **Plan** — create or refine a hierarchical chapter contract within the approved book/arc outline.
3. **Route** — apply positive policy triggers and select only relevant protocols and deterministic tools.
4. **Resolve** — run selected host tools and continuity/causality queries; record decisions and replay data.
5. **Compile** — build and validate the writer-safe context manifest.
6. **Draft** — generate prose with the selected creative profile.
7. **Deterministic audit** — verify artifacts, required constraints, repetition, known entity/state rules, chronology, spatial/inventory bounds, knowledge routes, and contamination sentinels.
8. **Semantic audit** — invoke a structured critic only for material questions deterministic checks cannot resolve.
9. **Blind reader** — provide only the prose and ask what happened, why, what changed, and what remains unclear.
10. **Repair** — make evidence-directed repairs. Default budget: one structural reconstruction when a gate explicitly returns `RECONSTRUCT_SCENE`, followed by at most two span-scoped repairs.
11. **Final audit** — rerun every hard check against the actual candidate.
12. **State proposal** — partition the final normalized prose into a gap-free, non-overlapping span ledger with deterministic paragraph and sentence IDs and exact code-point offsets. Classify every ledger entry as `state_change`, `no_state_change`, or `unresolved`; attach one or more exact-span delta proposals to every `state_change` entry.
13. **Promote** — commit final prose, the complete span ledger, state revisions, provenance, and workflow result in one recoverable transaction.
14. **Summarize** — optionally build a post-promotion derived summary whose individual claims cite accepted prose spans and state revision IDs. Summaries are rebuildable views, never authority, and remain unavailable to retrieval or context compilation until `summary.grounded` passes.

Malformed critic, reader, or extraction output fails closed. Deterministic repair is limited to lossless syntax normalization such as removing a code fence or a trailing comma when the same fields and values remain. Missing or semantically invalid fields require a constrained retry or `needs_review`; repair never invents an approval, finding, or canon value.

Host code cross-checks the span ledger against the blind reader's independently produced `observed_state_changes` and deterministic signals for entity introduction/identity, numbers and quantities, death/status, location and inventory transfer, injury/condition, relationship changes, and knowledge acquisition or disclosure. A signal without a matching ledger classification and grounded delta, a reader observation without a matching delta, or disagreement between either source and a `no_state_change` classification converts the affected entry to `unresolved`. The ledger-coverage contract proves that no prose is omitted from review; detector recall is measured separately and is not represented as semantic infallibility.

### 8.2 Gate registry and promotion decision

Gates are data, not scattered conditionals. A versioned registry defines `gate_id`, stage, input revision, output schema, severity, blocking predicate, retry/repair action, budget, waiver policy, and terminal outcome. Every result cites source spans or deterministic evidence.

| Gate | Auto-promotion condition | Exhausted action |
| --- | --- | --- |
| `artifact.valid` | Prose and required artifacts are complete, parseable, and within configured length bounds | `failed`; never waivable |
| `tool.required` | Every positively selected required tool completed with a valid replay artifact | `failed`; never waivable |
| `firewall.isolation` | No cross-project/forbidden sentinel appears and the manifest contains only granted fields | `failed`; never waivable |
| `contract.reconstruction` | The blind reader supports every required literal outcome and exit-state predicate with prose evidence | repair, then `needs_review` |
| `continuity.critical` | No unresolved critical identity, state, chronology, spatial, inventory, or relationship contradiction | repair, then `needs_review` |
| `causality.critical` | Every consequential transition has required preconditions, mechanism, and effect | repair, then `needs_review` |
| `knowledge.boundary` | Character belief/action does not exceed its evidenced acquisition route and precision | repair, then `needs_review` |
| `state.coverage` | The ledger is a gap-free partition of the final prose; every entry is classified, every independent reader/deterministic signal is matched, and none is `unresolved` | extraction retry, then `accepted_text_state_pending`; never waivable for continuity-head advancement |
| `state.delta` | Every `state_change` entry has complete schema-valid, exact-span-grounded, chapter-idempotent deltas | extraction retry, then `accepted_text_state_pending`; never waivable for continuity-head advancement |
| `authority.resolved` | Every proposed delta resolves cleanly under the recorded authority hierarchy, including conflicts among accepted prose, retcons, and explicit canon | reconciliation, then `accepted_text_state_pending`; never waivable for continuity-head advancement |
| `summary.grounded` | Every summary claim admitted to retrieval cites accepted prose spans and/or state revisions that entail it | discard and rebuild the derived summary; never waivable for context admission |

Repetition, similarity, pacing, and noncritical prose findings are advisory unless a policy pack promotes a specific threshold into the versioned registry. The semantic critic runs only when a deterministic gate produces a material unresolved question or when blind-reader evidence conflicts with the contract.

The blind-reader schema contains ordered literal events, causal answers, observed state changes, unclear spans, and evidence quotes/offsets. The scene contract stores required outcomes as explicit predicates. Host code compares them; unsupported or ambiguous material predicates consume the repair budget and then produce `needs_review`.

Auto mode cannot waive a hard gate. A user may manually promote selected content-gate failures with a recorded gate ID, reason, and snapshot, producing `completed_with_waiver`. Artifact, required-tool, firewall/cross-project, schema-integrity, transaction, `state.coverage`, `state.delta`, and `authority.resolved` failures are non-waivable for any promotion that advances the accepted manuscript and continuity head. Accepting prose while any of the last three remain unresolved produces only `accepted_text_state_pending`; downstream compilation and generation fail closed until reconciliation creates a new candidate that passes them.

### 8.3 Stage identity and invalidation

Each stage fingerprint hashes canonical JSON containing the accepted project revision, all admitted source hashes, outline/scene contract, upstream artifact hashes, policy/tool manifests, prompt and schema versions, model hash, runtime/profile identity, sampler settings, and seed. A completed deterministic stage may be reused only when the fingerprint matches. A completed model response may be resumed as its immutable attempt; an interrupted model call always creates a new attempt ID.

Changing prose, canon, outline, source files, grants, policy, tools, prompts, model, runtime, or profile invalidates that stage and all descendants. Promotion repeats revision and source-hash checks under the database transaction, preventing a preflight race.

### 8.4 Candidate transaction

All generated material remains in a candidate revision. Promotion stores final prose, its exhaustive span ledger, and structured changes together inside SQLite, advances the accepted project revision and continuity head, then materializes Markdown through an atomic temporary-file replacement. A locked output file leaves the committed database revision intact with `view_sync_pending`; startup recovery recreates the view. If validation or the database transaction fails, neither prose nor canon advances.

`accepted_text_state_pending` is an editorial status on the immutable candidate, not rank-2 accepted-manuscript authority. It may be materialized in a clearly marked pending view, but it is excluded from accepted-manuscript retrieval and writer context. Resolving it creates a new candidate and reruns final audit, the full span ledger, and all non-waivable promotion gates; the original pending record remains in history.

Rewriting a chapter supersedes its earlier revision and derived events. Chapter and outline identities remain stable. All downstream chapters are conservatively marked stale unless complete recorded dependency coverage proves they are unaffected.

### 8.5 Arc and book operation

Books use editable hierarchy: premise/theme/voice → arcs and outcomes → chapters and causal purpose → scene contracts. Each chapter is its own promotion transaction. A failed or `needs_review` chapter records `blocked_at_chapter` and pauses downstream work; earlier `committed_through_chapter` state remains accepted. Pause finishes the current safe transaction. Cancel requires confirmed inference-slot cancellation/drain; if the runtime cannot prove cancellation, Studio restarts the supervised server before another job and preserves restartable artifacts.

Cross-chapter seam gates verify exit-to-entry location, time, participants, knowledge, unresolved pressure, and causal handoff. Book generation therefore remains resumable and inspectable instead of becoming one opaque prompt.

## 9. Tool and policy-pack design

Deterministic work runs outside the LLM. A tool manifest defines:

- stable name/version and JSON input/output schemas;
- permitted workflow stages and policy packs;
- read/write roots and network/process capabilities;
- deterministic status, seed, timeout, and cancellation behavior;
- artifact and replay requirements.

1.0 runs reviewed in-process tools and explicit-argument subprocesses without a shell. Bundled in-process tools are trusted application code; their manifests are routing/audit policy, not technical sandboxing. Subprocess tools receive a minimal explicit Windows environment allowlist, a fixed working directory, resolved-path validation, bounded output, and no network-capable manifest in 1.0. Managed runtimes and subprocess tools are assigned to [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, then terminated as a process tree on timeout or Studio exit. This is capability containment, not a claim of a complete Windows security sandbox.

The portable bundle includes timeline/causality validation, knowledge-route validation, repetition/contamination scanning, retrieval diagnostics, and deterministic random resolution. The LitRPG policy pack adds opt-in progression, encounter, economy/incentive, bestiary, and disclosure tools generalized from the existing harness. Availability never activates a tool; positive triggers and a persisted selection record do.

MCP and arbitrary user processes are deferred until a later capability layer can provide trustworthy manifests and stronger isolation. The runtime's native tool calling may produce validated tool requests, but the studio remains the only executor.

## 10. GUI and user experience

The interface uses progressive disclosure. Routine generation requires no terminal and no sampler expertise.

### 10.1 Primary surfaces

1. **First-run setup** — choose model folders, install/import and verify the pinned runtime plus embedding model, inspect privacy/offline guarantees, and run calibration.
2. **Model Lab** — searchable model inventory, compatibility, load status, observed VRAM/RAM, context, speed, role scores, profiles, and benchmark comparison.
3. **Projects** — create, import, export, duplicate, archive, and resume; each card shows latest chapter and health.
4. **Studio** — outline/navigation on the left, editor and generated prose in the center, collapsible run evidence on the right. Primary actions are Write Chapter, Write Arc, and Write Book.
5. **Canon & Knowledge** — structured facts, event/causal graph, character knowledge, source provenance, conflicts, retcons, and writer-visibility preview.
6. **Runs** — phase timeline, prompt/context manifests, retrieved evidence, tool traces, model settings, revisions, gate results, resource metrics, and restart/rollback actions.
7. **Settings** — tested presets first; advanced runtime, sampler, stage, policy, and path controls in labeled drawers.

### 10.2 Interaction contracts

- “Auto” always names the selected profile and explains why it was selected.
- Dangerous or slow settings show their consequence before launch.
- A run visibly distinguishes planning, drafting, checking, repairing, and committing.
- execution state, promotion outcome, `committed_through_chapter`, and `blocked_at_chapter` are displayed separately.
- The user can inspect every recorded workflow, retrieval, tool, setting, gate, and promotion decision, including the exact writer-visible packet and excluded controller material. The UI does not claim access to unreported model internals.
- Every accepted change can be rolled back without deleting its history.
- Technical detail is available but does not dominate the default writing workspace.

## 11. Failure handling and recovery

- **Unsupported/corrupt GGUF:** quarantine its profile, preserve metadata, and report the exact probe/load failure.
- **OOM or detected spill:** terminate the attempt, restore the last known-good runtime state, and retry only through recorded lower-context/KV/batch candidates. Partial offload requires explicit slow mode.
- **Runtime crash/stall:** watchdog terminates the process tree, preserves streamed output as diagnostic material, and resumes from the last committed stage when safe.
- **Context overflow:** the compiler recomputes admission under budget and reports exclusions; it never blindly truncates canon.
- **Conflicting sources:** keep both with provenance and authority status; fail the affected hard constraint when precedence cannot resolve it.
- **Malformed model JSON:** use grammar/schema-constrained retry and deterministic repair; never permissively scrape an approval or canon mutation.
- **Concurrent user edit:** optimistic revision checks reject stale promotion and preserve both versions.
- **Cancellation during promotion:** SQLite transaction and startup recovery guarantee the old or new revision, never a mixed state.
- **Book chapter failure:** mark downstream jobs blocked/stale and stop; do not compound a bad seam.
- **Index failure:** accepted source files and hashes remain intact; rebuild local indexes without changing canon.

## 12. Verification and release gates

### 12.1 Automated tests

- Unit tests for schemas, authority precedence, token admission, visibility, causal/state rules, gap-free span-ledger coverage, signal reconciliation, delta grounding, grounded-summary admission, transaction recovery, settings, and tool manifests.
- Property tests for chapter-idempotent updates, supersession, serialization, path containment, and crash recovery.
- Integration tests with fake runtimes for every workflow branch, retry cap, pause/cancel, restart, and malformed response.
- Golden prompt/context-manifest tests to detect writer-information leaks.
- Seeded contradiction suite: 100% recall for critical labeled contradictions, at least 90% overall, under 10% false positives.
- Retrieval suite: at least 90% recall@10 for answer-bearing chunks, with provenance preserved.
- Cross-project canary suite: zero cache, retrieval, prompt, output, or canon leakage.
- Migration and archive round-trip tests.
- Browser end-to-end tests for setup, calibration, project creation/import, generation, inspection, rollback, and resume.
- Required live Windows smoke suite for managed llama.cpp; conditional suites for LM Studio and KoboldCpp before either adapter is advertised as supported.

### 12.2 Performance gates on the target machine

- Calibration either produces a verified no-spill WeirdCompound profile or rejects it from Auto without silently enabling slow mode; a lower quantization or another resident writer then becomes the production candidate.
- Dedicated/shared GPU observations and runtime-reported model/KV placement are displayed with their evidence source and stored; unavailable per-buffer placement is not invented.
- For every managed-runtime profile advertised as equivalent to a KoboldCpp baseline, generation throughput is no worse than 10% below that baseline under the same model hash, prompt, context, sampler, seed, and output length.
- Profile invalidation occurs when model, runtime, GPU, driver, or memory envelope changes.
- Network-disabled chapter generation, recovery, and export succeed.

### 12.3 Writing-quality gates

The frozen benchmark contains exactly 12 initial chapter fixtures across progression/LitRPG and general fiction, three arcs of 3–5 chapters, and one short book of 8–12 chapters. Existing accepted LitRPG material supplies comprehension/state fixtures but is never placed in generic writer context. A benchmark manifest freezes fixture/source hashes, model/runtime/profile hashes, prompt/schema/policy versions, sampler settings, two chapter seeds, longform seeds, attempt budgets, and expected hard constraints. Long live generations run in an explicit release/nightly suite, not ordinary CI.

Outputs are compared blindly against the raw WeirdCompound/Kobold baseline and any alternative named in the frozen manifest. Evaluation records literal comprehension before subjective scores and covers causality, continuity, character voice, scene purpose, prose control, pacing, emotional effect, repetition/private symbolism, and desire to continue.

Automated triage requires two versioned local judge profiles, neither of which generated the pair. Each pair is shown as A/B and B/A. Order-disagreement is scored conservatively as a tie. Candidate score is `wins + 0.5 × ties`; non-inferiority means the 90% paired-bootstrap confidence interval for candidate-minus-baseline score has a lower bound greater than `-0.10`. Judge outputs and confidence calculations are reproducible artifacts, not human labels.

The 1.0 target is:

- zero critical canon contradictions in completed longform fixtures;
- at least 80% of chapter fixtures and every longform fixture finish without human intervention;
- no more than 20% of chapter fixtures and no longform fixture end with `RECONSTRUCT_SCENE` or `needs_review` after the fixed repair budget;
- blinded automated triage meets the defined non-inferiority calculation;
- the product includes a frozen blinded human calibration panel. A profile earns `human_quality_qualified` only after at least three raters complete at least 24 paired judgments, its median overall score is at least 4/5 with no rubric dimension below 3/5, and its 95% paired-bootstrap non-inferiority lower bound is greater than `-0.10`.

LLM judges remain triage signals. They do not override hard deterministic failures or represent universal proof of good writing. Core 1.0 can ship as a working starting point with reproducible automated results, but the UI must label role profiles `automated_only` until the human gate is actually populated; it cannot display the stronger quality-qualified claim.

## 13. Migration and reuse

The implementation preserves behavior through tests before porting it.

- From Story Companion: session UX, outline modes, phase logging, structured projection, repetition guard, blind reader, pause/resume semantics, and fake-runtime tests.
- From Kobold Writing Companion: durable artifact/control-plane patterns, retention, proxy-baseline concepts, checks, and migration tests.
- From LitRPG-Test: source-authority categories, selective positive routing, writer firewall, knowledge disclosure, cold-reader reconstruction, state-after-acceptance, causal seam checks, and deterministic tool contracts.
- From KoboldCpp: runtime capability expectations and an external compatibility adapter only. The dirty fork remains untouched.

Story-specific prompts, manuscript, secrets, logs, generated artifacts, and AGPL implementation code are not copied into the generic product. Importers read existing Story Companion sessions and project sources without mutating their originals. A machine-readable code-origin ledger records whether each migrated unit is clean-room reimplementation, owned source, permissively licensed source, or external process integration. Local prototypes without an explicit compatible license are behaviorally reimplemented unless ownership and reuse permission are recorded.

## 14. Delivery scope for 1.0

1.0 is complete when a nontechnical user can install/start the studio, discover and calibrate the existing local GGUF library, create or import a project, ingest provenance-backed knowledge, run reviewed tools, produce and transactionally accept a chapter, resume a multi-chapter arc/book, inspect every recorded decision, and recover or roll back without using a terminal.

Delivery is sequenced through vertical, releasable milestones:

1. **One safe profiled chapter:** managed llama.cpp only; setup/model scan/calibration; transactional project kernel; generic policy pack; writer firewall; required gates; Studio/Canon/Runs minimum UI; one live WeirdCompound or qualified-alternative smoke.
2. **Resumable mini-arc:** three chapter transactions; seam/staleness handling; persistent jobs; reviewed tools; LitRPG policy/import path; restart and kill tests.
3. **1.0 completion:** book queue and hierarchy; hybrid retrieval and pinned embedder; packaging/offline bundle; import/export; Model Lab; conditional external adapters; frozen quality suite and results.

The following remain outside 1.0:

- cloud inference or required online services;
- accounts, collaboration, remote hosting, or telemetry;
- arbitrary autonomous shell/MCP execution;
- training or fine-tuning model weights;
- universal document/runtime/model-format support;
- implicit slow inference for models whose working set exceeds VRAM;
- a claim that automation can guarantee commercial or universal literary success.

## 15. Decision record

The user approved the fresh modular architecture and delegated remaining design and implementation decisions. The design therefore chooses transactional auto-promotion after hard gates, local-only operation, a pinned llama.cpp core, optional external adapters, empirical calibration, a writer information firewall, policy packs, and comparative quality qualification as binding 1.0 constraints.
