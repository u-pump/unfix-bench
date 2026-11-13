# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
# Local runner for Codex CLI. Claude Code runs in GitHub Actions: see docs/run-claude-code.md.
param(
    [Parameter(Mandatory, Position = 0)]
    [ValidatePattern('^[a-z0-9][a-z0-9-]*$')][string]$CaseId,
    [ValidateSet('codex-cli')][string]$Agent = 'codex-cli'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$caseDir = Join-Path $root "cases/$CaseId"
$agentDir = Join-Path $caseDir "agents/$Agent"
$patchPath = Join-Path $agentDir 'agent-fix.patch'
$metaPath = Join-Path $agentDir 'agent.yaml'
$checkoutRoot = Join-Path (Split-Path -Parent $root) ".tmp/bench-agent/$Agent"
$checkout = Join-Path $checkoutRoot $CaseId
$logDir = Join-Path $root '.tmp/agent-runs/logs'
$runId = "$CaseId-$Agent-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
$logPath = Join-Path $logDir "$runId.log"
$candidate = Join-Path $logDir "$runId.patch"
$repo = "u-pump/bench-in-$CaseId"
if (-not (Test-Path -LiteralPath $caseDir -PathType Container)) { throw "Unknown case: $CaseId" }
if (-not (Test-Path -LiteralPath $patchPath -PathType Leaf)) { throw "Missing agent-fix.patch: $Agent" }
if ((Get-Item -LiteralPath $patchPath).Length -ne 0) { throw "First patch already recorded: $Agent/$CaseId" }
if (Test-Path -LiteralPath $checkout) { throw "Checkout already exists: $checkout" }
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) { throw 'Codex CLI не найден' }
$version = (& codex --version).Trim()
if ($LASTEXITCODE -ne 0 -or -not $version) { throw 'codex --version failed' }
$oldGhToken = $env:GH_TOKEN
$oldGithubToken = $env:GITHUB_TOKEN
try {
    $env:GH_TOKEN = (gh auth token --user u-pump).Trim()
    if (-not $env:GH_TOKEN) { throw 'u-pump GitHub token unavailable' }
    if ((gh repo view $repo --json isPrivate --jq '.isPrivate') -ne 'true') { throw "Input repository is not private: $repo" }
    New-Item -ItemType Directory -Force -Path $checkoutRoot, $logDir | Out-Null
    gh repo clone $repo $checkout -- --depth 1 --single-branch
    if ($LASTEXITCODE -ne 0) { throw "Clone failed: $repo" }
    $checkoutTop = (git -C $checkout rev-parse --show-toplevel).Trim()
    if ([IO.Path]::GetFullPath($checkoutTop).TrimEnd('\') -ne [IO.Path]::GetFullPath($checkout).TrimEnd('\')) {
        throw 'Unexpected checkout root'
    }
    if ((git -C $checkout rev-list --count HEAD) -ne '1' -or (git -C $checkout cat-file -p HEAD | Select-String '^parent ')) {
        throw 'Input repository does not have one root commit'
    }
    $taskPath = Join-Path $checkout 'TASK.md'
    if (-not (Test-Path -LiteralPath $taskPath -PathType Leaf)) { throw 'TASK.md missing' }
    $task = (Get-Content -LiteralPath $taskPath -Raw -Encoding UTF8).Trim()
    if ($task -ne 'Fix the bug described in ISSUE.md. Keep the change minimal. Run the existing tests.') { throw 'TASK.md differs from the benchmark protocol' }
    $env:GH_TOKEN = $null
    $env:GITHUB_TOKEN = $null
    Write-Host "$Agent $version; log: $logPath"
    Push-Location -LiteralPath $checkout
    try {
        & codex exec --sandbox workspace-write $task 2>&1 | Tee-Object -FilePath $logPath
        $agentExit = $LASTEXITCODE
    } finally { Pop-Location }
    $log = Get-Content -LiteralPath $logPath -Raw -Encoding UTF8
    if ($agentExit -ne 0) { throw "$Agent exited with code $agentExit; attempt not recorded. See $logPath" }
    $modelMatch = [regex]::Match($log, '(?m)^model:\s*(\S+)')
    $model = if ($modelMatch.Success) { $modelMatch.Groups[1].Value } else { '' }
    if (-not $model -or -not [regex]::IsMatch($log, '(?m)^exec\r?$') -or
        -not [regex]::IsMatch($log, '(?m)^ (?:succeeded|exited \d+) in ')) {
        throw "Codex CLI executed no completed commands; attempt not recorded. See $logPath"
    }
    git -C $checkout add -A -- . ':(exclude,glob)build*/**' ':(exclude,glob)**/build*/**'
    if ($LASTEXITCODE -ne 0) { throw 'Could not stage agent changes' }
    git -C $checkout diff --cached --binary --no-ext-diff --output=$candidate HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Could not save agent patch' }
    $hash = if ((Get-Item -LiteralPath $candidate).Length -eq 0) { $null } else {
        (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $metadata = [ordered]@{
        name = 'Codex CLI'; version = $version; model = $model; invocation = 'codex exec --sandbox workspace-write'
        date_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        environment = 'local Windows; Codex workspace-write sandbox; network restriction depends on CLI sandbox configuration'
        patch_sha256 = $hash
        attempt_note = 'First completed local attempt; build*/ output excluded from the patch.'
    }
    Copy-Item -LiteralPath $candidate -Destination $patchPath
    try { $metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $metaPath -Encoding utf8 }
    catch { [IO.File]::WriteAllBytes($patchPath, [byte[]]@()); throw }
    Write-Host "Patch: $patchPath; SHA-256: $hash"
} finally {
    $env:GH_TOKEN = $oldGhToken
    $env:GITHUB_TOKEN = $oldGithubToken
    $separator = [IO.Path]::DirectorySeparatorChar
    $rootFull = [IO.Path]::GetFullPath($checkoutRoot).TrimEnd($separator)
    $checkoutFull = [IO.Path]::GetFullPath($checkout)
    if (-not $checkoutFull.StartsWith("$rootFull$separator", [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe checkout cleanup path' }
    if (Test-Path -LiteralPath $checkoutFull) { Remove-Item -LiteralPath $checkoutFull -Recurse -Force }
}
