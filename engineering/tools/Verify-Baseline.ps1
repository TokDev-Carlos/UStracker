[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$InstallRoot = 'C:\UStracker'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
if ([string]::IsNullOrWhiteSpace($RepoRoot)) { $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path }
else { $RepoRoot = (Resolve-Path $RepoRoot).Path }
if (-not (Test-Path -LiteralPath $InstallRoot)) { throw "Instalacao de referencia ausente: $InstallRoot" }

function Compare-Tree([string]$Source, [string]$Target) {
    $rows = @()
    Get-ChildItem $Source -Recurse -File | ForEach-Object {
        $relative = $_.FullName.Substring($Source.Length).TrimStart('\')
        $peer = Join-Path $Target $relative
        if (-not (Test-Path -LiteralPath $peer)) {
            $rows += [pscustomobject]@{ path=$relative; status='MISSING_TARGET' }
        } else {
            $a = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
            $b = (Get-FileHash $peer -Algorithm SHA256).Hash
            if ($a -ne $b) { $rows += [pscustomobject]@{ path=$relative; status='HASH_MISMATCH' } }
        }
    }
    return $rows
}

$frontendIssues = @(Compare-Tree (Join-Path $RepoRoot 'frontend') (Join-Path $InstallRoot 'frontend'))
$backendIssues = @(Compare-Tree (Join-Path $RepoRoot 'src\ustracker') (Join-Path $InstallRoot 'Runtime\Lib\site-packages\ustracker'))
$report = [ordered]@{
    checked_at = (Get-Date).ToUniversalTime().ToString('o')
    install_root = $InstallRoot
    frontend_issues = $frontendIssues
    backend_issues = $backendIssues
    status = $(if ($frontendIssues.Count -eq 0 -and $backendIssues.Count -eq 0) { 'PASS' } else { 'FAIL' })
}
$out = Join-Path $RepoRoot 'engineering\reports\runtime\baseline-compare.json'
New-Item -ItemType Directory -Force -Path (Split-Path $out -Parent) | Out-Null
$report | ConvertTo-Json -Depth 20 | Set-Content $out -Encoding UTF8
Write-Host "BASELINE_COMPARE=$($report.status)"
Write-Host "REPORT=$out"
if ($report.status -ne 'PASS') { exit 2 }
