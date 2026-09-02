# Hermes integration — v0.7.1

Hermes is the conversational operator. The Python runtime is the controller. Fresh child Hermes processes are candidate generators.

## Normal user experience

After bootstrap, launch Hermes through the project wrapper:

```powershell
.\integrations\hermes\start-project.ps1
```

or:

```bash
./integrations/hermes/start-project.sh
```

The launcher refreshes the installed `deterministic-writing-runtime` skill from the current checkout every time, pins the project working directory, and preloads the skill.

Once inside Hermes, the intended interface is normal conversation. Examples:

```text
Start a writing pilot using the current fixture.
```

```text
Start a writing pilot for book1/ch12 on main from Mara's POV. Aim for 2500 words. She reaches the observatory expecting to find Ilya, but discovers the room has been abandoned in a hurry. The chapter should end with a concrete choice rather than a passive revelation.
```

```text
Chronobreak from book1/ch08 because the pact never happened, then show me what existing plans/state become invalid before we rewrite anything.
```

For an end-to-end writing request, interactive Hermes should save the user's brief and invoke `integrations/hermes/pilot_controller.py`. It should **not** manually perform planning/drafting/critique in the current conversation. The controller owns planning, fresh model calls, disclosure epochs, deterministic validation, bounded repair, Occam salvage, and acceptance/human-review routing.

The interactive session should also avoid reading hidden author-scope plan packets merely to narrate progress. Fresh child calls provide the actual generative isolation.

## Current fixture conversational shortcut

When the user explicitly says to use the current/example/first pilot fixture, Hermes uses:

```text
plan-id:      pilot.first.ch05
chapter-key:  book1/ch05
at:           book1/ch05
branch:       main
viewpoint:    Mara
workdir:      runtime_state/pilot-first
output:       runtime_state/pilot-first/final-chapter.txt
```

So after launching Hermes, this is sufficient:

```text
Start the first real writing pilot using the current fixture. Write roughly 2000-2500 words. Make the scene action-driven and consequential; don't explain mechanics Mara doesn't know. Use the deterministic controller and stop if it reaches human_review.
```

## Automated install from GitHub

The public expanded source tree is the installation authority. Root `install-hermes.ps1`/`.sh` resolves a mutable ref once to an immutable commit, then installs/checks out that exact source revision and runs bootstrap. No GitHub Actions or hosted runners are required.

Windows one-liner:

```powershell
iex (irm https://raw.githubusercontent.com/Laeveteinn/llm-story-companion/main/install-hermes.ps1)
```

For an existing local checkout:

```powershell
.\integrations\hermes\bootstrap.ps1
```

## Manual/controller-level invocation

Manual CLI remains available for debugging or non-interactive automation:

```powershell
python integrations\hermes\pilot_controller.py .\brief.txt `
  --plan-id book1.ch05 `
  --chapter-key book1/ch05 `
  --at book1/ch05 `
  --branch main `
  --viewpoint Mara `
  --skip-setup
```

The controller rebuilds canon/state, compiles an author-aware plan request, invokes Hermes in a fresh one-turn process, mechanically validates/repairs the plan, drafts all disclosure epochs in separate fresh processes, assembles them in software, and obeys the finite prose-repair router until `accept` or `human_review`.

Use `--prepare-only` to validate packet generation without model calls.

## Strong fresh-call primitive

For custom orchestration, `hermes_fresh_call.py` pins the project root, never resumes/continues an old Hermes session, uses one turn, can use Hermes safe mode, and verifies request prompt hashes when given a manifest.

## Temporal rule

Every pilot request carries `timeline_branch`. Never repair a child branch using an abandoned parent's future context. A time traveler arriving from a future must receive explicit branch-local carried state/knowledge; the runtime does not inherit the future automatically.
