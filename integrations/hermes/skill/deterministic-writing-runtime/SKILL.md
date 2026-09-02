---
name: deterministic-writing-runtime
description: Run deterministic fiction planning and repair gates.
version: 0.7.0
author: Project-local
license: MIT
platforms: [windows, linux, macos]
allowed-tools: terminal, read_file, write_file, search_files
metadata:
  hermes:
    tags: [fiction, writing, deterministic, canon, continuity]
    requires_toolsets: [terminal]
---

# Deterministic Writing Runtime

## When to Use

Use this skill for chapter planning, drafting, canon-sensitive revision, continuity repair, prose-gate diagnosis, or any request to run the project's recursive writing loop.

Do **not** use it for casual discussion of writing craft when no project files are being changed.

## Workspace Requirement

The working directory must be the project root containing `write_runtime.py`, `canon_source/`, `state_source/`, and `config/`.

If those are missing, stop and tell the user to launch Hermes with the project's `integrations/hermes/start-project.ps1` / `.sh` wrapper. Do not guess another checkout.

## Core Procedure

1. Run the relevant deterministic preflight (`state-audit`, `plan-check`, `quality`, or `doctor`) before asking the model to repair anything.
2. Use only prompt files emitted by `write_runtime.py` for recursive plan/prose repair. Never turn raw lint output into your own ad-hoc rewrite prompt.
3. Respect process exit codes. A hard failure remains a failure until the deterministic gate changes state.
4. For drafting, use `draft-prompt` only when it permits monolithic drafting. If it refuses because of a disclosure boundary, use `draft-epochs` and fresh model calls.
5. Apply responses only through `plan-apply`, `plan-salvage-apply`, `draft-apply`, `draft-epochs-apply`, `rewrite-apply`, or `salvage-apply` as appropriate.
6. Use `plan-repair-next` / `repair-next` for recursion routing. Do not invent extra critique loops after the runtime says `human_review`.
7. Preserve immutable anchors during Occam salvage. The runtime, not the model, reassembles accepted text.

## Same-Model Rule

Phase names are not trust boundaries. Planner, writer, and repairer may be the same model.

If hidden author truth has entered the current conversational context, do not use that context for disclosure-sensitive prose. Use the parent-side fresh-call wrapper described in `references/HERMES_EXECUTION.md`.

## Verification

Before declaring a project operation complete, run the deterministic gate that owns that artifact and report its actual pass/fail state.
