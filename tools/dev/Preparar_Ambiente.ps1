# UStracker - prepara o ambiente de desenvolvimento local (rodar no PowerShell, sem administrador).
# Cria D:\PROGRAMAS\UStracker_Project, clona o repositorio (Dev), instala Node.js e NSIS (winget) se faltarem,
# cria o ambiente Python (.venv) e roda um teste rapido. Nada e apagado. Relatorio em Logs\.
param([string]$Base = 'D:\PROGRAMAS\UStracker_Project', [switch]$SemInstalar)

$ErrorActionPreference = 'Continue'
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$folders = @('Codigo', 'Entregas', 'Ferramentas', 'Logs',
             'Conhecimento\Problemas_Solucoes', 'Conhecimento\Decisoes', 'Conhecimento\Ideias', 'Conhecimento\Validacoes')
foreach ($f in $folders) { New-Item -ItemType Directory -Force -Path (Join-Path $Base $f) | Out-Null }
$report = Join-Path $Base "Logs\preparar_ambiente_$stamp.txt"
function Write-Log([string]$m) { Add-Content -LiteralPath $report -Value $m -Encoding UTF8; Write-Host $m }
function Ver([string]$exe, [string]$arg = '--version') {
    $c = Get-Command $exe -ErrorAction SilentlyContinue
    if (-not $c) { return 'nao instalado' }
    try { return ((& $c.Source $arg 2>&1 | Select-Object -First 1) -as [string]).Trim() } catch { return 'erro ao consultar' }
}
function Refresh-Path { $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User') }

Write-Log "=== UStracker - preparar ambiente ($stamp) em $env:COMPUTERNAME ==="
Write-Log "Pastas: $($folders -join ', ')"

# 1) Node.js e NSIS (winget)
if (-not $SemInstalar) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { Write-Log 'winget nao encontrado: instale Node.js 22+ e NSIS manualmente.' }
    else {
        if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
            Write-Log 'Instalando Node.js LTS...'
            winget install --id OpenJS.NodeJS.LTS -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
            Write-Log "winget Node.js: codigo $LASTEXITCODE"
        }
        if (-not (Get-Command makensis -ErrorAction SilentlyContinue) -and -not (Test-Path "${env:ProgramFiles(x86)}\NSIS\makensis.exe")) {
            Write-Log 'Instalando NSIS...'
            winget install --id NSIS.NSIS -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
            Write-Log "winget NSIS: codigo $LASTEXITCODE"
        }
        Refresh-Path
    }
}
$nsis = (Get-Command makensis -ErrorAction SilentlyContinue).Source
if (-not $nsis -and (Test-Path "${env:ProgramFiles(x86)}\NSIS\makensis.exe")) { $nsis = "${env:ProgramFiles(x86)}\NSIS\makensis.exe" }

# 2) codigo (Dev)
$code = Join-Path $Base 'Codigo'
if (-not (Test-Path (Join-Path $code '.git'))) {
    if ((Get-ChildItem -LiteralPath $code -Force | Measure-Object).Count -eq 0) {
        Write-Log 'Clonando UStracker (Dev)...'
        git clone --branch Dev https://github.com/TokDev-Carlos/UStracker.git $code 2>&1 | Out-Null
        Write-Log "git clone: codigo $LASTEXITCODE"
    } else { Write-Log 'Codigo\ nao esta vazia e nao e um repositorio: nada clonado (confira a pasta).' }
} else {
    Write-Log 'Atualizando Codigo (git pull --ff-only)...'
    git -C $code pull --ff-only 2>&1 | Out-Null
    Write-Log "git pull: codigo $LASTEXITCODE"
}

# 3) Python (.venv) + dependencias + teste rapido
$tests = 'nao rodou'
if (Test-Path (Join-Path $code 'requirements-package.txt')) {
    $venvPy = Join-Path $code '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPy)) { if (Get-Command py -ErrorAction SilentlyContinue) { py -3.13 -m venv (Join-Path $code '.venv') 2>&1 | Out-Null }; if (-not (Test-Path $venvPy)) { python -m venv (Join-Path $code '.venv') 2>&1 | Out-Null } }
    if (Test-Path $venvPy) {
        & $venvPy -m pip install --disable-pip-version-check -q -r (Join-Path $code 'requirements-package.txt') 2>&1 | Out-Null
        Write-Log "pip install: codigo $LASTEXITCODE"
        Push-Location $code
        $env:PYTHONPATH = 'src;.'; $env:USTRACKER_DEV_PLAINTEXT = '1'
        $out = & $venvPy -m unittest tests.test_h03_patch_tool tests.test_g01_release2 2>&1 | Out-String
        $tests = (($out -split "`n") | Where-Object { $_ -match '^(Ran|OK|FAILED)' }) -join ' | '
        Pop-Location
    } else { Write-Log 'Nao foi possivel criar o .venv (Python 3.13 instalado?)' }
}

# 4) relatorio
Write-Log ''
Write-Log '--- Versoes ---'
Write-Log "claude:   $(Ver claude)"
Write-Log "git:      $(Ver git)"
Write-Log "python:   $(Ver python)"
Write-Log "node:     $(Ver node)"
Write-Log "npm:      $(Ver npm)"
Write-Log "makensis: $(if ($nsis) { (& $nsis /VERSION 2>&1 | Select-Object -First 1) } else { 'nao instalado' })"
Write-Log ''
Write-Log '--- Repositorio ---'
if (Test-Path (Join-Path $code '.git')) {
    Write-Log "branch: $(git -C $code rev-parse --abbrev-ref HEAD)"
    Write-Log "commit: $(git -C $code log --oneline -1)"
    Write-Log "versao: $(Get-Content (Join-Path $code 'version.md') -ErrorAction SilentlyContinue)"
}
Write-Log "teste rapido: $tests"
Write-Log ''
Write-Log '--- UStracker instalado ---'
Write-Log "version.md: $(Get-Content "$env:ProgramFiles\UStracker\version.md" -ErrorAction SilentlyContinue)"
Write-Log "=== fim: $report ==="
