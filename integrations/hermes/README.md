# Hermes integration — v0.7.1

Hermes is a candidate generator. The Python runtime is the controller.

## Automated install from GitHub

For normal public installation, prefer the root `install-hermes.ps1`/`.sh` bootstrap. It resolves or checks out an exact Git commit, validates the runtime layout, records provenance, then runs this project bootstrap. Do not ask an AI to invent an installation layout.

Windows:

```powershell
.\integrations\hermes\install-from-github.ps1 `
  -Repository https://github.com/Laeveteinn/llm-story-companion.git `
  -Ref main `
  -Destination "$HOME\WritingHarness-Deterministic"
```

For a reproducible deployment also pass `-ExpectedCommit <40-char-sha>`.

Bash uses environment variables:

```bash
WRITING_HARNESS_REF=main \
WRITING_HARNESS_HOME="$HOME/WritingHarness-Deterministic" \
./integrations/hermes/install-from-github.sh
```

The installer does `git fetch` + detached checkout, validates required files, records the resolved commit in `runtime_state/install-source.json`, then runs bootstrap. It does **not** use GitHub Actions or hosted runners.

## Existing local checkout

```powershell
.\integrations\hermes\bootstrap.ps1
```

This installs deterministic dependencies/stores and copies the project Hermes skill. Interactive convenience:

```powershell
.\integrations\hermes\start-project.ps1
```

`.hermes.md` and the skill help discovery, but neither is a security/control boundary.

## Pilot controller

Preferred pilot:

```powershell
python integrations\hermes\pilot_controller.py .\brief.txt `
  --plan-id book1.ch05 `
  --chapter-key book1/ch05 `
  --at book1/ch05 `
  --branch main `
  --viewpoint Mara `
  --provider <provider> `
  --model <model>
```

The controller rebuilds canon/state, compiles an author-aware plan request, invokes Hermes in a fresh one-turn process, mechanically validates/repairs the plan, drafts all disclosure epochs in separate fresh processes, assembles them in software, and obeys the finite prose-repair router until `accept` or `human_review`.

To validate setup without consuming model calls:

```powershell
python integrations\hermes\pilot_controller.py .\brief.txt `
  --plan-id pilot.test --chapter-key book1/ch05 --at book1/ch05 `
  --branch retcon.bind_fixed_dc --viewpoint Mara `
  --prepare-only --skip-setup
```

## Strong fresh-call primitive

For custom orchestration, invoke `hermes_fresh_call.py`. It pins the project root, never resumes/continues an old Hermes session, uses one turn, can use Hermes safe mode, and verifies request prompt hashes when given a manifest.

## Temporal rule

Every pilot request carries `timeline_branch`. Never repair a child branch using an abandoned parent's future context. A time traveler arriving from a future must receive explicit branch-local carried state/knowledge; the runtime does not inherit the future automatically.
