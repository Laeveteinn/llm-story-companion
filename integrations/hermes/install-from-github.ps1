param(
    [string]$Repository = 'https://github.com/Laeveteinn/llm-story-companion.git',
    [string]$Ref = 'main',
    [string]$Destination = "$HOME\WritingHarness-Deterministic",
    [string]$ExpectedCommit = '',
    [switch]$LaunchHermes,
    [switch]$SkipSetup
)
$ErrorActionPreference = 'Stop'

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

Require-Command git
$Destination = [System.IO.Path]::GetFullPath($Destination)
$parent = Split-Path -Parent $Destination
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }

if (Test-Path (Join-Path $Destination '.git')) {
    $origin = (& git -C $Destination remote get-url origin).Trim()
    if ($origin -ne $Repository) {
        throw "Existing destination has unexpected origin: $origin"
    }
} elseif (Test-Path $Destination) {
    throw "Destination exists but is not a Git repository: $Destination"
} else {
    & git clone --no-checkout $Repository $Destination
    if ($LASTEXITCODE -ne 0) { throw 'git clone failed' }
}

# Resolve exactly one remote ref, then detach. No implicit merge/pull and no dependency on GitHub Actions.
& git -C $Destination fetch --force --depth 1 origin $Ref
if ($LASTEXITCODE -ne 0) { throw "git fetch failed for ref $Ref" }
& git -C $Destination checkout --detach --force FETCH_HEAD
if ($LASTEXITCODE -ne 0) { throw 'git checkout failed' }
$commit = (& git -C $Destination rev-parse HEAD).Trim().ToLowerInvariant()

if ($ExpectedCommit) {
    $expected = $ExpectedCommit.Trim().ToLowerInvariant()
    if ($commit -ne $expected) { throw "Resolved commit $commit does not match expected $expected" }
}

$required = @('write_runtime.py', 'pyproject.toml', 'integrations\hermes\bootstrap.ps1', '.hermes.md')
foreach ($rel in $required) {
    if (-not (Test-Path (Join-Path $Destination $rel))) {
        throw "Repository checkout is not a complete deterministic-writing runtime; missing $rel"
    }
}

$runtimeState = Join-Path $Destination 'runtime_state'
New-Item -ItemType Directory -Force -Path $runtimeState | Out-Null
$record = [ordered]@{
    repository = $Repository
    requested_ref = $Ref
    resolved_commit = $commit
    installed_at_utc = [DateTime]::UtcNow.ToString('o')
    destination = $Destination
}
$record | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $runtimeState 'install-source.json')

if (-not $SkipSetup) {
    & (Join-Path $Destination 'integrations\hermes\bootstrap.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Harness bootstrap failed' }
}

Write-Host "Installed deterministic writing runtime at $Destination"
Write-Host "Resolved Git commit: $commit"
if ($LaunchHermes) {
    & (Join-Path $Destination 'integrations\hermes\start-project.ps1')
}
