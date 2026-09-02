$ErrorActionPreference = 'Stop'
$Source = Join-Path $PSScriptRoot 'skill\deterministic-writing-runtime'
$HermesHome = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { Join-Path $env:LOCALAPPDATA 'hermes' }
$Dest = Join-Path $HermesHome 'skills\writing\deterministic-writing-runtime'
New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
Copy-Item -Recurse -Force $Source $Dest
Write-Host "Installed Hermes skill: $Dest"
Write-Host "Launch this project with: $PSScriptRoot\start-project.ps1"
