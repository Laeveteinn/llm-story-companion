$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $Root
try {
    & (Join-Path $Root 'setup.ps1')
    & (Join-Path $PSScriptRoot 'install-skill.ps1')
    Write-Host "Bootstrap complete. Use $PSScriptRoot\start-project.ps1"
} finally {
    Pop-Location
}
