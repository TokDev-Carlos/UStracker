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
$gateRel = "engineering/reports/runtime/$ChangesetId-candidate-gate.json"
& $PythonPath (Join-Path $RepoRoot 'engineering\tools\guard.py') --repo $RepoRoot candidate-gate --changeset $changesetRel --output $gateRel
if ($LASTEXITCODE -ne 0) { throw "Candidate gate falhou. Consulte $gateRel" }

$outDir = Join-Path $RepoRoot "candidate\$ChangesetId"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
& (Join-Path $RepoRoot 'tools\package.ps1') -RepoRoot $RepoRoot -OutDir $outDir

$zip = Get-ChildItem $outDir -Filter 'UStracker_*_win-x64.zip' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($null -eq $zip) { throw 'ZIP candidate nao localizado.' }
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip.FullName).Hash
$metadata = [ordered]@{
    changeset_id = $ChangesetId
    git_head = (& git -C $RepoRoot rev-parse HEAD).Trim()
    package = $zip.Name
    sha256 = $hash
    built_at = (Get-Date).ToUniversalTime().ToString('o')
    installed = $false
    promoted = $false
}
$metadata | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $outDir 'CANDIDATE.json') -Encoding UTF8
Write-Host "CANDIDATE=$($zip.FullName)"
Write-Host "SHA256=$hash"
Write-Host 'INSTALLATION=NOT_PERFORMED'
