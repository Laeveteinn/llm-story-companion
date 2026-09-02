$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$env:WRITING_RUNTIME_ROOT = $Root
Push-Location $Root
try {
    # Keep the installed Hermes skill synchronized with this checkout on every launch.
    & (Join-Path $PSScriptRoot 'install-skill.ps1')
    & hermes -s deterministic-writing-runtime @args
} finally {
    Pop-Location
}
