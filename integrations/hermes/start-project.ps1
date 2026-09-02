$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$env:WRITING_RUNTIME_ROOT = $Root
Push-Location $Root
try {
    & hermes -s deterministic-writing-runtime @args
} finally {
    Pop-Location
}
