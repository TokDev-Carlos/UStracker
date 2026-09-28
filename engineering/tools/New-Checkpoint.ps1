[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Label,
    [string]$ChangesetId = "",
    [string]$RepoRoot = "",
    [string]$PythonPath = ""
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
if ([string]::IsNullOrWhiteSpace($RepoRoot)) { $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path }
else { $RepoRoot = (Resolve-Path $RepoRoot).Path }
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $runtimePython = 'C:\UStracker\Runtime\python.exe'
    $PythonPath = if (Test-Path -LiteralPath $runtimePython) { $runtimePython } else { 'python' }
}
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$safe = ($Label -replace '[^A-Za-z0-9_.-]', '-')
$outputRel = "engineering/checkpoints/$stamp-$safe.json"
$args = @('--repo',$RepoRoot,'checkpoint','--label',$Label,'--output',$outputRel)
if (-not [string]::IsNullOrWhiteSpace($ChangesetId)) {
    $args += @('--changeset',"engineering/changesets/$ChangesetId.json")
}
& $PythonPath (Join-Path $RepoRoot 'engineering\tools\guard.py') @args
if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar checkpoint.' }
Write-Host "CHECKPOINT=$(Join-Path $RepoRoot ($outputRel -replace '/', '\'))"
