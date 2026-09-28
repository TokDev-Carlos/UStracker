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

$approvalPath = Join-Path $RepoRoot 'engineering\APPROVAL.json'
$approval = Get-Content $approvalPath -Raw | ConvertFrom-Json
if (-not [bool]$approval.user_approved_execution) {
    throw 'BLOQUEADO: o usuario ainda nao autorizou a execucao funcional do plano.'
}

& (Join-Path $RepoRoot 'engineering\tools\Invoke-Preflight.ps1') -RepoRoot $RepoRoot -PythonPath $PythonPath

$changesetFile = Join-Path $RepoRoot ("engineering\changesets\{0}.json" -f $ChangesetId)
if (-not (Test-Path -LiteralPath $changesetFile)) { throw "Changeset inexistente: $ChangesetId" }
$changeset = Get-Content $changesetFile -Raw | ConvertFrom-Json
if ($changeset.status -ne 'PREPARED') { throw "Changeset deve estar PREPARED, atual: $($changeset.status)" }

$worktreesRoot = Join-Path $RepoRoot '.worktrees'
New-Item -ItemType Directory -Force -Path $worktreesRoot | Out-Null
$worktree = Join-Path $worktreesRoot $ChangesetId
$branch = "feature/$ChangesetId"
if (Test-Path -LiteralPath $worktree) { throw "Worktree ja existe: $worktree" }
& git -C $RepoRoot show-ref --verify --quiet "refs/heads/$branch"
if ($LASTEXITCODE -eq 0) { throw "Branch ja existe: $branch" }

$baseCommit = (& git -C $RepoRoot rev-parse main).Trim()
& git -C $RepoRoot worktree add $worktree -b $branch $baseCommit
if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar worktree.' }

$workChangesetFile = Join-Path $worktree ("engineering\changesets\{0}.json" -f $ChangesetId)
$workChangeset = Get-Content $workChangesetFile -Raw | ConvertFrom-Json
$workChangeset.base_commit = $baseCommit
$workChangeset.status = 'IN_PROGRESS'
$workChangeset.user_approved_execution = $true
$workChangeset | ConvertTo-Json -Depth 20 | Set-Content $workChangesetFile -Encoding UTF8

$ledger = Join-Path $worktree 'engineering\ledgers\progress.md'
Add-Content $ledger "`nTask $($workChangeset.task_number): started in $branch from $baseCommit using changeset $ChangesetId."

Write-Host "WORKTREE=$worktree"
Write-Host "BRANCH=$branch"
Write-Host "BASE_COMMIT=$baseCommit"
Write-Host "CHANGESET=$workChangesetFile"
