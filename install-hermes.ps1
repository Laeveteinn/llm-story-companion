param(
    [string]$Repository = 'Laeveteinn/llm-story-companion',
    [string]$Ref = 'main',
    [string]$Destination = "$HOME\WritingHarness-Deterministic",
    [string]$ExpectedCommit = '',
    [string]$ExpectedArchiveSha256 = '',
    [switch]$Force,
    [switch]$SkipHermesInstall,
    [switch]$SkipSetup,
    [switch]$LaunchHermes
)
$ErrorActionPreference = 'Stop'
$Headers = @{ 'User-Agent' = 'deterministic-writing-runtime-installer' }

function Resolve-PythonInvocation {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) { return @($python.Source) }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) { return @($py.Source, '-3') }
    $candidate = Join-Path $env:LOCALAPPDATA 'hermes\hermes-agent\venv\Scripts\python.exe'
    if (Test-Path $candidate) { return @($candidate) }
    throw 'Python 3 is required to extract the deterministic distribution. Install Hermes first or provide python/py on PATH.'
}

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

# Resolve a mutable ref once. Every distribution byte below is fetched from this immutable commit.
$apiRef = [uri]::EscapeDataString($Ref)
$commitInfo = Invoke-RestMethod -Headers $Headers "https://api.github.com/repos/$Repository/commits/$apiRef"
$commit = ([string]$commitInfo.sha).Trim().ToLowerInvariant()
if ($commit -notmatch '^[0-9a-f]{40}$') { throw "GitHub returned an invalid commit SHA: $commit" }
if ($ExpectedCommit -and $commit -ne $ExpectedCommit.Trim().ToLowerInvariant()) {
    throw "Resolved commit $commit does not match ExpectedCommit $ExpectedCommit"
}
$rawBase = "https://raw.githubusercontent.com/$Repository/$commit"
$dist = Invoke-RestMethod -Headers $Headers "$rawBase/dist/current.json"
if ($dist.encoding -ne 'base64-parts') { throw "Unsupported distribution encoding: $($dist.encoding)" }
if ($dist.format -ne 'tar.xz') { throw "Unsupported distribution format: $($dist.format)" }
if (-not $dist.parts -or -not $dist.sha256) { throw 'Distribution manifest is incomplete' }

$Destination = [System.IO.Path]::GetFullPath($Destination)
if (Test-Path $Destination) {
    if (-not $Force) { throw "Destination already exists: $Destination (back it up or pass -Force)" }
    Remove-Item -Recurse -Force $Destination
}
$parent = Split-Path -Parent $Destination
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }

$temp = Join-Path ([System.IO.Path]::GetTempPath()) ("writing-harness-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $temp | Out-Null
try {
    $encoded = New-Object System.Text.StringBuilder
    foreach ($part in $dist.parts) {
        $piece = (Invoke-WebRequest -UseBasicParsing -Headers $Headers "$rawBase/$($dist.part_dir)/$part").Content.Trim()
        [void]$encoded.Append($piece)
    }
    $archive = Join-Path $temp $dist.archive
    [IO.File]::WriteAllBytes($archive, [Convert]::FromBase64String($encoded.ToString()))
    $actual = (Get-FileHash -Algorithm SHA256 $archive).Hash.ToLowerInvariant()
    $published = ([string]$dist.sha256).Trim().ToLowerInvariant()
    if ($actual -ne $published) { throw "Reconstructed archive hash mismatch: $actual != $published" }
    if ($ExpectedArchiveSha256 -and $actual -ne $ExpectedArchiveSha256.Trim().ToLowerInvariant()) {
        throw "Archive $actual does not match ExpectedArchiveSha256 $ExpectedArchiveSha256"
    }

    $unpacked = Join-Path $temp 'unpacked'
    New-Item -ItemType Directory -Force -Path $unpacked | Out-Null
    $pythonInvocation = Resolve-PythonInvocation
    $pythonExe = $pythonInvocation[0]
    $pythonPrefix = @($pythonInvocation | Select-Object -Skip 1)
    $extractCode = @'
import pathlib, sys, tarfile
archive, out = sys.argv[1:]
root = pathlib.Path(out).resolve()
with tarfile.open(archive, 'r:xz') as tf:
    members = tf.getmembers()
    for member in members:
        if member.issym() or member.islnk():
            raise SystemExit(f'refusing archive link: {member.name}')
        target = (root / member.name).resolve()
        if target != root and root not in target.parents:
            raise SystemExit(f'unsafe archive path: {member.name}')
    tf.extractall(root)
'@
    & $pythonExe @pythonPrefix -c $extractCode $archive $unpacked
    if ($LASTEXITCODE -ne 0) { throw 'Archive extraction failed' }
    $expanded = Get-ChildItem -Path $unpacked -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'write_runtime.py') } | Select-Object -First 1
    if (-not $expanded) { throw 'Archive layout/runtime validation failed' }
    $required = @(
        'write_runtime.py', 'pyproject.toml', '.hermes.md', 'SNAPSHOT_MANIFEST.json',
        'writing_runtime\temporal.py', 'writing_runtime\semantic.py',
        'integrations\hermes\pilot_controller.py', 'integrations\hermes\bootstrap.ps1',
        'tests\test_temporal.py'
    )
    foreach ($rel in $required) {
        if (-not (Test-Path (Join-Path $expanded.FullName $rel))) { throw "Incomplete archive; missing $rel" }
    }
    Move-Item -Path $expanded.FullName -Destination $Destination

    $runtimeState = Join-Path $Destination 'runtime_state'
    New-Item -ItemType Directory -Force -Path $runtimeState | Out-Null
    [ordered]@{
        repository = "https://github.com/$Repository"
        requested_ref = $Ref
        resolved_commit = $commit
        distribution_version = $dist.version
        archive = $dist.archive
        archive_sha256 = $actual
        installed_at_utc = [DateTime]::UtcNow.ToString('o')
        destination = $Destination
    } | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $runtimeState 'install-source.json')

    if (-not $SkipSetup) {
        & (Join-Path $Destination 'integrations\hermes\bootstrap.ps1')
        if ($LASTEXITCODE -ne 0) { throw 'Harness bootstrap failed' }
    }
    Refresh-HermesPath
    Write-Host "Installed deterministic writing runtime $($dist.version) at $Destination"
    Write-Host "Pinned GitHub commit: $commit"
    Write-Host "Archive SHA-256: $actual"
    if ($LaunchHermes) {
        if (-not (Get-Command hermes -ErrorAction SilentlyContinue)) {
            throw 'Hermes is not visible in this process. Open a new PowerShell window and run integrations\hermes\start-project.ps1.'
        }
        & (Join-Path $Destination 'integrations\hermes\start-project.ps1')
    }
} finally {
    Remove-Item -Recurse -Force $temp -ErrorAction SilentlyContinue
}
