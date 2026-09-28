[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ChangesetId,
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

$changesetRel = "engineering/changesets/$ChangesetId.json"
$changesetPath = Join-Path $RepoRoot ($changesetRel -replace '/', '\')
if (-not (Test-Path $changesetPath)) { throw "Changeset ausente: $changesetPath" }
$changeset = Get-Content $changesetPath -Raw | ConvertFrom-Json
if (-not [bool]$changeset.user_approved_execution) { throw 'Changeset nao autorizado para execucao.' }

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$reportDir = Join-Path $RepoRoot "engineering\reports\runtime\$ChangesetId-$timestamp"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

$policyRel = "engineering/reports/runtime/$ChangesetId-$timestamp/policy.json"
& $PythonPath (Join-Path $RepoRoot 'engineering\tools\guard.py') --repo $RepoRoot policy --changeset $changesetRel --output $policyRel
$policyExit = $LASTEXITCODE
$policy = Get-Content (Join-Path $RepoRoot ($policyRel -replace '/', '\')) -Raw | ConvertFrom-Json

$env:PYTHONPATH = Join-Path $RepoRoot 'src'
$env:USTRACKER_DEV_PLAINTEXT = '1'
$checks = @()

function Invoke-Check([string]$Name, [string]$Exe, [string[]]$Arguments) {
    $safeName = $Name -replace '[^A-Za-z0-9_.-]', '_'
    $log = Join-Path $reportDir ($safeName + '.log')
    $started = (Get-Date).ToUniversalTime().ToString('o')
    & $Exe @Arguments 2>&1 | Tee-Object -FilePath $log | Write-Host
    $exit = $LASTEXITCODE
    $finished = (Get-Date).ToUniversalTime().ToString('o')
    $script:checks += [pscustomobject]@{ name=$Name; exit_code=$exit; started_at=$started; finished_at=$finished; log=$log }
    return $exit
}

$nodeTestFiles = @('tests/r2_ui.test.mjs')
if ($null -ne $changeset.PSObject.Properties['node_test_files']) {
    $configuredNodeTests = @($changeset.node_test_files | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($configuredNodeTests.Count -gt 0) { $nodeTestFiles = $configuredNodeTests }
}
$manualGates = @()
if ($null -ne $changeset.PSObject.Properties['manual_gates']) {
    $manualGates = @($changeset.manual_gates | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
}

$failed = $false
if ((Invoke-Check 'python-unittest' $PythonPath @('-m','unittest','discover','-s','tests','-p','test_*.py','-v')) -ne 0) { $failed = $true }
$nodeArgs = @('--test') + $nodeTestFiles
if ((Invoke-Check 'node-tests' 'node' $nodeArgs) -ne 0) { $failed = $true }
if ((Invoke-Check 'node-check' 'node' @('--check','frontend/app.js')) -ne 0) { $failed = $true }
if ((Invoke-Check 'python-compileall' $PythonPath @('-m','compileall','-q','src/ustracker','tests')) -ne 0) { $failed = $true }
if ((Invoke-Check 'dotnet-bootstrap' 'dotnet' @('build','host/Bootstrap/Bootstrap.csproj','-c','Release','-p:Platform=x64','--no-restore','--nologo')) -ne 0) { $failed = $true }
if ((Invoke-Check 'dotnet-shell' 'dotnet' @('build','host/Shell/Shell.csproj','-c','Release','-p:Platform=x64','--no-restore','--nologo')) -ne 0) { $failed = $true }
if ((Invoke-Check 'dotnet-updater' 'dotnet' @('build','host/Updater/Updater.csproj','-c','Release','-p:Platform=x64','--no-restore','--nologo')) -ne 0) { $failed = $true }
if ($policyExit -ne 0 -or $policy.status -ne 'PASS') { $failed = $true }

$manualPending = (-not $failed -and $manualGates.Count -gt 0)
$status = 'PASS'
if ($failed) { $status = 'FAIL' }
elseif ($manualPending) { $status = 'PASS_AUTOMATED_AWAITING_MANUAL' }

$head = (& git -C $RepoRoot rev-parse HEAD).Trim()
$report = [ordered]@{
    changeset_id = $ChangesetId
    status = $status
    git_head = $head
    base_commit = $changeset.base_commit
    checked_at = (Get-Date).ToUniversalTime().ToString('o')
    policy = $policy
    checks = $checks
    manual_gates = $manualGates
}
$reportPath = Join-Path $reportDir 'verification.json'
$report | ConvertTo-Json -Depth 20 | Set-Content $reportPath -Encoding UTF8

if ($failed) {
    Write-Host "VERIFICATION=FAIL"
    Write-Host "REPORT=$reportPath"
    exit 2
}
if ($manualPending) {
    Write-Host "VERIFICATION=PASS_AUTOMATED_AWAITING_MANUAL"
    Write-Host "MANUAL_GATES=$($manualGates.Count)"
    Write-Host "REPORT=$reportPath"
    exit 3
}

$changeset.status = 'VERIFIED'
$changeset | ConvertTo-Json -Depth 20 | Set-Content $changesetPath -Encoding UTF8
Write-Host "VERIFICATION=PASS"
Write-Host "REPORT=$reportPath"
exit 0
