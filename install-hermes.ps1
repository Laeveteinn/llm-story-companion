param(
    [string]$Repository = 'Laeveteinn/llm-story-companion',
    [string]$Ref = 'main',
    [string]$Destination = "$HOME\WritingHarness-Deterministic",
    [string]$ExpectedCommit = '',
    [switch]$SkipHermesInstall,
    [switch]$SkipSetup,
    [switch]$LaunchHermes
)
$ErrorActionPreference = 'Stop'
$Headers = @{ 'User-Agent' = 'deterministic-writing-runtime-installer' }

function Refresh-HermesPath {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'hermes\hermes-agent\bin'),
        (Join-Path $env:LOCALAPPDATA 'hermes\hermes-agent\venv\Scripts')
    )
    foreach ($candidate in $candidates) {
        if ((Test-Path $candidate) -and (($env:Path -split ';') -notcontains $candidate)) {
            $env:Path = "$candidate;$env:Path"
        }
    }
}

if (-not (Get-Command hermes -ErrorAction SilentlyContinue) -and -not $SkipHermesInstall) {
    Write-Host 'Hermes CLI not found; installing with the official Nous Research Windows installer...'
    Invoke-Expression (Invoke-RestMethod 'https://hermes-agent.nousresearch.com/install.ps1')
    Refresh-HermesPath
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host 'Git not found; installing Git for Windows with WinGet...'
        winget install --id Git.Git --exact --source winget --accept-source-agreements --accept-package-agreements --silent
        $gitCmd = Get-Command git.exe -ErrorAction SilentlyContinue
        if (-not $gitCmd) {
            $candidate = Join-Path $env:ProgramFiles 'Git\cmd'
            if (Test-Path $candidate) { $env:Path = "$candidate;$env:Path" }
        }
    }
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Git is required for the deterministic public-source install.'
}

$apiRef = [uri]::EscapeDataString($Ref)
$commitInfo = Invoke-RestMethod -Headers $Headers "https://api.github.com/repos/$Repository/commits/$apiRef"
$commit = ([string]$commitInfo.sha).Trim().ToLowerInvariant()
if ($commit -notmatch '^[0-9a-f]{40}$') { throw "GitHub returned an invalid commit SHA: $commit" }
if ($ExpectedCommit -and $commit -ne $ExpectedCommit.Trim().ToLowerInvariant()) {
    throw "Resolved commit $commit does not match ExpectedCommit $ExpectedCommit"
}

$temp = Join-Path ([System.IO.Path]::GetTempPath()) ("writing-harness-installer-" + [guid]::NewGuid().ToString('N') + '.ps1')
try {
    $raw = "https://raw.githubusercontent.com/$Repository/$commit/integrations/hermes/install-from-github.ps1"
    Invoke-WebRequest -UseBasicParsing -Headers $Headers $raw -OutFile $temp
    $repoUrl = "https://github.com/$Repository.git"
    & $temp -Repository $repoUrl -Ref $commit -Destination $Destination -ExpectedCommit $commit -SkipSetup:$SkipSetup -LaunchHermes:$LaunchHermes
    if ($LASTEXITCODE -ne 0) { throw 'Deterministic source installation failed' }
} finally {
    Remove-Item -Force $temp -ErrorAction SilentlyContinue
}
