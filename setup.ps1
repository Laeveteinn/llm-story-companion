param(
  [switch]$CoreOnly,
  [switch]$SkipVale,
  [switch]$RefreshVale
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-Checked([string]$Label, [scriptblock]$Command) {
  & $Command
  if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
}

Write-Host "[1/6] Installing Python runtime..."
Invoke-Checked "pip upgrade" { python -m pip install -U pip }
Invoke-Checked "core runtime install" { python -m pip install -e . }
if (-not $CoreOnly) {
  Write-Host "[2/6] Installing pinned deterministic NLP libraries..."
  Invoke-Checked "NLP runtime install" { python -m pip install -e ".[nlp]" }
  python -m spacy download en_core_web_sm
  if ($LASTEXITCODE -ne 0) { Write-Warning "spaCy model install failed; deterministic core still works without it." }
} else { Write-Host "[2/6] Skipping optional NLP stack (-CoreOnly)." }

Write-Host "[3/6] Installing pinned Node analyzers..."
if (-not $CoreOnly) {
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
      Write-Host "Node/npm not found; attempting WinGet install of Node.js LTS."
      winget install --id OpenJS.NodeJS.LTS --exact --source winget --accept-source-agreements --accept-package-agreements --silent
      Write-Warning "If Node was just installed, restart this PowerShell session and rerun setup.ps1 so PATH is refreshed."
    }
  }
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "npm is required for the full analyzer stack." }
  $nodeVersion = (& node -p "process.versions.node").Trim()
  $parts = $nodeVersion.Split('.')
  if ([int]$parts[0] -lt 22 -or ([int]$parts[0] -eq 22 -and [int]$parts[1] -lt 18)) {
    throw "Node >=22.18.0 is required by pinned CSpell 10.x. Installed: $nodeVersion. Upgrade Node, then rerun setup.ps1."
  }
  if (Test-Path "package-lock.json") {
    Invoke-Checked "npm ci" { npm ci --ignore-scripts=false }
  } else {
    Write-Warning "No package-lock.json exists yet. This first full install will resolve dependencies and create one; preserve/commit that lock for reproducible future installs."
    Invoke-Checked "npm install" { npm install --ignore-scripts=false }
  }
} else { Write-Host "Skipping Node analyzers (-CoreOnly)." }

Write-Host "[4/6] Installing/configuring Vale 3.17.0..."
if (-not $SkipVale -and -not $CoreOnly) {
  if (-not (Get-Command vale -ErrorAction SilentlyContinue)) {
    $installed = $false
    if (Get-Command winget -ErrorAction SilentlyContinue) {
      winget install --name Vale --exact --version 3.17.0 --source winget --accept-source-agreements --accept-package-agreements --silent
      if ($LASTEXITCODE -eq 0) { $installed = $true } else { Write-Warning "WinGet Vale install failed; trying fallbacks." }
    }
    if (-not $installed -and (Get-Command choco -ErrorAction SilentlyContinue)) {
      choco install vale --version=3.17.0 -y
      if ($LASTEXITCODE -eq 0) { $installed = $true }
    }
    if (-not $installed -and (Get-Command scoop -ErrorAction SilentlyContinue)) {
      scoop install vale
      if ($LASTEXITCODE -eq 0) { $installed = $true }
    }
  }
  if (Get-Command vale -ErrorAction SilentlyContinue) {
    $haveFrozenStyles = Test-Path ".vale/styles"
    if ($RefreshVale -or -not $haveFrozenStyles) {
      vale sync
      if ($LASTEXITCODE -ne 0) { Write-Warning "Vale sync failed. Vale will be reported unavailable/failing until styles are synced." }
    } else {
      Write-Host "Using existing frozen .vale/styles. Pass -RefreshVale to intentionally update them."
    }
  } else {
    Write-Warning "Vale was not found after package-manager attempts. Install its CLI manually, then run: vale sync"
  }
} else { Write-Host "Vale skipped (-SkipVale or -CoreOnly)." }

Write-Host "[5/6] Building deterministic canon/state libraries..."
Invoke-Checked "canon build" { python write_runtime.py canon-build canon_source --out canon/canon.sqlite3 }
Invoke-Checked "canon dictionary" { python write_runtime.py canon-spell-dict --library canon/canon.sqlite3 --out config/canon-terms.txt }
Invoke-Checked "story state build" { python write_runtime.py state-build state_source --library canon/canon.sqlite3 --out state/story_state.sqlite3 }
Write-Host "[6/6] Verifying example plan and freezing toolchain..."
Invoke-Checked "example plan gate" { python write_runtime.py plan-check plans/example.json --library canon/canon.sqlite3 --state-library state/story_state.sqlite3 }
Invoke-Checked "tool lock" { python write_runtime.py tool-lock --out config/toolchain.lock.json }
python write_runtime.py doctor
python write_runtime.py tool-expected
if ($LASTEXITCODE -ne 0) { Write-Warning "One or more installed tool versions differ from the target manifest; see output above. The lock still records the exact runtime." }
Write-Host "Setup complete. Future runs can use: python write_runtime.py tool-verify"
