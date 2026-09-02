# Hermes Execution Modes

## Strong path: parent-owned fresh calls

Use `integrations/hermes/hermes_fresh_call.py`. It launches a new `hermes chat` process without `--resume`/`--continue`, pins cwd to the project root, uses `--ignore-rules` so global memories/context files cannot leak into the child call, and captures only the resulting candidate for deterministic validation.

This is the preferred path for disclosure epochs and recursive repairs.

## Interactive path

Use `integrations/hermes/start-project.ps1` or `.sh`. The wrapper changes to the project root and preloads this skill. `.hermes.md` is then discovered automatically by Hermes.

This is convenient but not equivalent to a hard execution guarantee: the interactive model can still choose poorly. Deterministic gates remain authoritative.

## Gateway / cron

Pin Hermes `terminal.cwd` to the project root in its config. Do not rely on whatever directory happened to launch the gateway. The project `.hermes.md` is only auto-discovered when Hermes resolves the workspace correctly.
