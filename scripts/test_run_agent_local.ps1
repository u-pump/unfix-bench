# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$scriptPath = Join-Path $PSScriptRoot 'run-agent-local.ps1'
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -ne 0) { throw "PowerShell syntax errors: $($errors | Out-String)" }

# The local runner is Codex-only; Claude Code runs in GitHub Actions.
try { & $scriptPath -Agent claude-code fmt-4800; throw 'Claude Code was accepted by the local runner' }
catch { if ($_.Exception.Message -notmatch 'claude-code|ValidateSet') { throw } }

$caseId = 'cpp-peglib-121'
$codexPatch = Join-Path $root "cases/$caseId/agents/codex-cli/agent-fix.patch"
$codexHash = (Get-FileHash -LiteralPath $codexPatch -Algorithm SHA256).Hash
try { & $scriptPath -Agent codex-cli $caseId; throw 'Recorded Codex patch was accepted for overwrite' }
catch { if ($_.Exception.Message -notmatch 'First patch already recorded') { throw } }
if ((Get-FileHash -LiteralPath $codexPatch -Algorithm SHA256).Hash -ne $codexHash) { throw 'Recorded patch changed' }
Write-Host 'run-agent-local.ps1 tests passed; no agent launched'
