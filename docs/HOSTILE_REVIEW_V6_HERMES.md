# Hostile Review v0.6 — Hermes as executor

## Finding: a Hermes skill is not a control plane

A skill is excellent packaging for instructions and CLI knowledge. It is not an execution guarantee. `.hermes.md` is stronger project-local context because Hermes loads it from the workspace, but it is still model context. Neither can prove that a continuing model session invoked the correct command, cleared prior hidden information, stayed in the correct directory, or respected a finite recursion budget.

Therefore the integration has three layers:

1. `.hermes.md` — project-local interactive policy and obvious startup affordance.
2. `integrations/hermes/skill/deterministic-writing-runtime/` — installable skill for interactive/manual Hermes use.
3. `integrations/hermes/hermes_fresh_call.py` — parent-side process boundary for the strong path.

The third layer is authoritative for automation.

## Strong execution path

`hermes_fresh_call.py` launches Hermes itself; Hermes does not decide whether to launch the harness. The wrapper:

- pins `cwd` to the project root;
- invokes `hermes chat -Q` as a new process;
- explicitly uses `--ignore-rules` so unrelated memory/SOUL/project prompt state is not inherited into the child call;
- never emits `--resume` or `--continue`;
- uses `--max-turns 1`;
- defaults to a minimal toolset;
- optionally adds `--safe-mode` for the strongest Hermes-side isolation (user config/plugins/MCP/hooks disabled) when the selected provider/runtime does not depend on those customizations;
- accepts a hash-bound fresh-call manifest and rejects stale prompts;
- captures stdout rather than allowing direct manuscript mutation;
- records prompt/response hashes and invocation metadata.

The same underlying model/runtime can be reused. The guarantee is **fresh context**, not different weights.

## Interactive path is weaker

`start-project.ps1` / `.sh` pins the workspace and preloads the skill. It is convenient for a human-driven session but does not establish disclosure isolation across turns. If the interactive conversation has seen author-only truth, it is contaminated for disclosure-sensitive prose generation. No prompt can make that context forget.

## Why not hand Hermes the ZIP and say “set yourself up”?

Because setup then becomes another stochastic model action. Paths, versions, package managers, working directory, and skill placement become suggestions rather than facts. Use `bootstrap.ps1` / `bootstrap.sh` to install dependencies and copy the skill deterministically. The AI may explain or invoke those scripts; it should not improvise their effects.

## Multi-file skill installation

The project installs the skill by local directory copy rather than depending on remote skill-install behavior. This preserves the `references/` support file as a unit and makes the installed bytes inspectable/versionable.

## Remaining weak spots

- The wrapper can prove which process/arguments/prompt it launched, but cannot inspect a third-party provider's internal KV/cache implementation. A local Hermes/runtime adapter should therefore be configured so each process/call is stateless as documented.
- `--ignore-rules` intentionally means the child call does not get ordinary Hermes memory/rules. The parent prompt compiler must provide the complete allowed context.
- An interactive Hermes session can still edit project files if given filesystem tools. Deterministic mutation commands and version control remain the authority boundary.
- The current wrapper owns individual fresh candidate calls, not the entire chapter orchestration lifecycle. A future `run-chapter` supervisor could own plan -> epoch draft -> gate -> repair -> salvage end-to-end and use Hermes only as a child generator.

## Decision

For serious unattended production: **executable first, skill second**. The skill documents how to use the executable; it must never be the thing that guarantees the executable is used.
