[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$PythonPath = ""
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
} else {
    $RepoRoot = (Resolve-Path $RepoRoot).Path
}
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $runtimePython = 'C:\UStracker\Runtime\python.exe'
    $PythonPath = if (Test-Path -LiteralPath $runtimePython) { $runtimePython } else { 'python' }
}

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Ferramenta obrigatoria ausente no PATH: $Name"
    }
}

Require-Command 'git'
Require-Command 'node'
Require-Command 'dotnet'
if ($PythonPath -eq 'python') { Require-Command 'python' }
elseif (-not (Test-Path -LiteralPath $PythonPath)) { throw "Python ausente: $PythonPath" }

$config = Get-Content (Join-Path $RepoRoot 'engineering\config\project.json') -Raw | ConvertFrom-Json
if ($RepoRoot.TrimEnd('\') -ieq ([string]$config.active_install_root).TrimEnd('\')) {
    throw 'ABORTADO: o workspace nao pode ser a instalacao ativa C:\UStracker.'
}

# Nenhum processo de produto/python pode apontar para esta arvore de trabalho.
$processHits = @()
if ($env:OS -eq 'Windows_NT') {
    try {
        $processHits = @(Get-CimInstance Win32_Process | Where-Object {
            $_.CommandLine -and $_.CommandLine.IndexOf($RepoRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
            $_.Name -match '^(UStracker(\.Shell|\.Updater)?\.exe|pythonw?\.exe)$'
        } | Select-Object Name, ProcessId, CommandLine)
    } catch {
        Write-Warning "Nao foi possivel consultar Win32_Process: $($_.Exception.Message)"
    }
}
if ($processHits.Count -gt 0) {
    $processHits | Format-Table -AutoSize | Out-String | Write-Host
    throw 'ABORTADO: ha processo executando a partir da arvore de trabalho.'
}

$reportDir = Join-Path $RepoRoot 'engineering\reports\runtime'
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$reportRel = 'engineering/reports/runtime/preflight.json'
& $PythonPath (Join-Path $RepoRoot 'engineering\tools\guard.py') --repo $RepoRoot preflight --output $reportRel
$guardExit = $LASTEXITCODE
$report = Get-Content (Join-Path $RepoRoot $reportRel) -Raw | ConvertFrom-Json
if ($guardExit -ne 0 -or $report.status -ne 'PASS') {
    throw "Preflight falhou. Consulte $reportRel"
}

Write-Host "PREFLIGHT=PASS"
Write-Host "REPO=$RepoRoot"
Write-Host "HEAD=$($report.head)"
Write-Host "BRANCH=$($report.branch)"
if ($report.warnings.Count -gt 0) {
    Write-Host ('WARNINGS=' + ($report.warnings -join '; '))
}
