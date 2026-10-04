[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$OutputRoot,
    [Parameter(Mandatory = $true)][string]$CandidateZip
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
$candidate = (Resolve-Path -LiteralPath $CandidateZip).Path
$output = [System.IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Path $output -Force | Out-Null

Push-Location $repo
try {
    $status = (& git status --porcelain) -join ''
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao consultar git status' }
    if ($status) { throw 'Worktree deve estar limpo antes do handoff' }

    $branch = (& git branch --show-current).Trim()
    $head = (& git rev-parse HEAD).Trim()
    $shortHead = (& git rev-parse --short HEAD).Trim()
    $version = (Get-Content -LiteralPath (Join-Path $repo 'version.md') -Raw).Trim()
    $versionJson = Get-Content -LiteralPath (Join-Path $repo 'VERSION.json') -Raw | ConvertFrom-Json
    $currentJson = Get-Content -LiteralPath (Join-Path $repo 'current.json') -Raw | ConvertFrom-Json
    if ($version -ne $versionJson.version -or $version -ne $currentJson.version) {
        throw 'version.md, VERSION.json e current.json divergem'
    }

    $tracked = & git ls-files
    $forbidden = $tracked | Where-Object {
        $_ -match '(^|/)UserData/' -or $_ -match '(^|/)\.env' -or
        $_ -match '\.(pfx|p12|key)$' -or ($_ -match 'private.*\.pem$')
    }
    if ($forbidden) { throw "Arquivo sensivel rastreado: $($forbidden -join ', ')" }

    $packageName = "UStracker_AI_HANDOFF_v${version}_${shortHead}_20261002"
    $staging = Join-Path $output $packageName
    $finalZip = "$staging.zip"
    if (Test-Path -LiteralPath $staging) { throw "Destino ja existe: $staging" }
    if (Test-Path -LiteralPath $finalZip) { throw "Destino ja existe: $finalZip" }

    $source = Join-Path $staging 'source'
    $gitDir = Join-Path $staging 'git'
    $artifacts = Join-Path $staging 'artifacts'
    New-Item -ItemType Directory -Path $source, $gitDir, $artifacts | Out-Null

    $sourceArchive = Join-Path $staging '_source_snapshot.zip'
    & git archive --format=zip --output=$sourceArchive HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao exportar snapshot Git' }
    Expand-Archive -LiteralPath $sourceArchive -DestinationPath $source
    Remove-Item -LiteralPath $sourceArchive -Force

    $bundle = Join-Path $gitDir 'UStracker-r11-r23.bundle'
    & git bundle create $bundle $branch
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar bundle Git' }
    & git bundle verify $bundle | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Bundle Git invalido' }

    $candidateTarget = Join-Path $artifacts (Split-Path -Leaf $candidate)
    Copy-Item -LiteralPath $candidate -Destination $candidateTarget
    $candidateHash = (Get-FileHash -LiteralPath $candidateTarget -Algorithm SHA256).Hash

    $state = [ordered]@{
        product = 'UStracker'
        handoff_format = 'AI_TRANSFER_V1'
        created_date = '2026-10-02'
        product_version = $version
        schema_version = [int]$versionJson.schema_version
        branch = $branch
        commit = $head
        worktree_clean = $true
        r11 = 'VERIFIED_SOURCE'
        r12 = 'VERIFIED_SOURCE'
        r13_r21 = 'IMPLEMENTED_UNVERIFIED'
        r22 = 'CORE_IMPLEMENTED_UNVERIFIED'
        r23 = 'AWAITING_HUMAN'
        adjustments = [ordered]@{
            AJ_01 = 'REQUIREMENT_CAPTURED_NOT_IMPLEMENTED'
            AJ_02 = 'REQUIREMENT_CAPTURED_NOT_IMPLEMENTED'
            AJ_03 = 'REQUIREMENT_CAPTURED_NOT_IMPLEMENTED'
            AJ_04 = 'REQUIREMENT_CAPTURED_NOT_IMPLEMENTED'
            execution_order = @('AJ-04', 'AJ-02', 'AJ-03', 'AJ-01')
        }
        candidate = [ordered]@{
            file = "artifacts/$(Split-Path -Leaf $candidateTarget)"
            sha256 = $candidateHash
            status = 'REFERENCE_ONLY_NOT_APPROVED'
        }
        excluded = @('.git working directory', 'Dist cache', 'bin/obj', 'UserData', 'active System installation', 'real data', 'secrets/private keys')
    }
    $state | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $staging 'PACKAGE_STATE.json') -Encoding UTF8

    @"
# UStracker — início do handoff para outra IA

Versão: $version  
Schema: $($versionJson.schema_version)  
Branch: $branch  
Commit: $head

Comece por `source/docs/handoff/2026-10-02-codex-r11-r23/11_TRANSFER_TO_OTHER_AI.md`.

O código R13–R22 NÃO está validado. AJ-01–AJ-04 ainda NÃO foram implementados.
Não toque em instalação ativa ou dados reais. `version.md` é a autoridade de versão.
`PACKAGE_STATE.json` contém o estado legível por máquina e os hashes principais.
"@ | Set-Content -LiteralPath (Join-Path $staging 'HANDOFF_PACKAGE_START_HERE.md') -Encoding UTF8

    @"
Verification target: AI transfer package
Repository: $repo
Branch: $branch
Commit: $head
Version authority: version.md = $version
VERSION.json = $($versionJson.version)
current.json = $($currentJson.version)
Schema = $($versionJson.schema_version)
Version metadata consistent: PASS
Worktree clean before export: PASS
Tracked secret/UserData policy scan: PASS
Git snapshot export: PASS
Git bundle verify: PASS
Reference candidate SHA-256: $candidateHash
Functional verdict: PARTIAL / NOT RE-RUN FOR THIS HANDOFF
Known stop: R13-R22 implemented but unverified; R23 awaits human validation; AJ-01..AJ-04 captured, not implemented.
"@ | Set-Content -LiteralPath (Join-Path $staging 'VERIFICATION_EVIDENCE.txt') -Encoding UTF8

    $manifestPath = Join-Path $staging 'FILE_MANIFEST_SHA256.csv'
    $manifestRows = Get-ChildItem -LiteralPath $staging -Recurse -File |
        Where-Object { $_.FullName -ne $manifestPath } |
        Sort-Object FullName |
        ForEach-Object {
            [pscustomobject]@{
                path = $_.FullName.Substring($staging.Length + 1).Replace('\', '/')
                size_bytes = $_.Length
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
            }
        }
    $manifestRows | Export-Csv -LiteralPath $manifestPath -NoTypeInformation -Encoding UTF8

    Compress-Archive -LiteralPath $staging -DestinationPath $finalZip -CompressionLevel Optimal
    $finalHash = (Get-FileHash -LiteralPath $finalZip -Algorithm SHA256).Hash
    "$finalHash  $(Split-Path -Leaf $finalZip)" | Set-Content -LiteralPath "$finalZip.sha256" -Encoding ASCII
    [pscustomobject]@{
        Package = $finalZip
        Sha256 = $finalHash
        Commit = $head
        Version = $version
        Files = @($manifestRows).Count + 1
    } | ConvertTo-Json -Depth 3
}
finally {
    Pop-Location
}
