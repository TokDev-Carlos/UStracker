# UStracker - Etapa B: coloca cada coisa no lugar certo (copia, confere SHA-256, so entao remove a origem).
#   Documentos\UStracker_Backups\Release_<v>   -> D:\PROGRAMAS\UStracker_Project\Entregas\<v>
#   Documentos\UStracker_Backups\Aplicador_Patch -> ja copiado para Ferramentas\Aplicador_Patch (confere e remove a copia antiga)
#   github_token.txt, token_leitura_acesso.txt  -> Drive: Dev_Sistemas\Tokens\GitHub (pelo H:\Meu Drive)
#   teste_claude_local.txt                      -> Logs
# Se qualquer conferencia falhar, a origem NAO e removida. Relatorio em Logs\organizar_<data>.txt
param([string]$Base = 'D:\PROGRAMAS\UStracker_Project', [string]$Drive = 'H:\Meu Drive')

$ErrorActionPreference = 'Continue'
$docs = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'UStracker_Backups'
$log = Join-Path $Base ('Logs\organizar_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.txt')
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
function R([string]$m) { Add-Content -LiteralPath $log -Value $m -Encoding UTF8; Write-Host $m }
function Hashes([string]$dir) {
    $h = @{}
    Get-ChildItem -LiteralPath $dir -Recurse -File -Force | ForEach-Object { $h[$_.FullName.Substring($dir.Length).TrimStart('\')] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
    return $h
}
function Same([string]$a, [string]$b) {
    $ha = Hashes $a; $hb = Hashes $b
    foreach ($k in $ha.Keys) { if ($hb[$k] -ne $ha[$k]) { return $false } }
    return $ha.Count -gt 0
}
function Move-Checked([string]$src, [string]$dst) {
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    & robocopy.exe $src $dst /E /COPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { R "ERRO copiando $src (robocopy $LASTEXITCODE): origem mantida"; return }
    if (Same $src $dst) { Remove-Item -LiteralPath $src -Recurse -Force; R "OK  $src -> $dst (SHA-256 conferido, origem removida)" }
    else { R "ERRO conferencia ${src} -> ${dst}: origem mantida" }
}

R "=== Organizar pastas $(Get-Date -Format s) ==="
# 1) instaladores
Get-ChildItem -LiteralPath $docs -Directory -Filter 'Release_*' | ForEach-Object {
    Move-Checked $_.FullName (Join-Path $Base ('Entregas\' + $_.Name.Substring(8)))
}
# 2) Aplicador de Patch (a copia nova ja esta em Ferramentas)
$old = Join-Path $docs 'Aplicador_Patch'; $new = Join-Path $Base 'Ferramentas\Aplicador_Patch'
if (Test-Path $old) {
    if ((Test-Path $new) -and (Same $old $new)) { Remove-Item -LiteralPath $old -Recurse -Force; R "OK  $old removido (igual a $new)" }
    else { R "AVISO $old mantido (diferente de $new ou destino ausente)" }
}
# 3) tokens -> Drive (Dev_Sistemas\Tokens\GitHub)
$tok = Join-Path $Drive 'Dev_Sistemas\Tokens'
if (Test-Path $tok) {
    $dst = Join-Path $tok 'GitHub'; New-Item -ItemType Directory -Force -Path $dst | Out-Null
    foreach ($n in 'github_token.txt', 'token_leitura_acesso.txt') {
        $s = Join-Path $docs $n
        if (-not (Test-Path $s)) { continue }
        Copy-Item -LiteralPath $s -Destination (Join-Path $dst $n) -Force
        if ((Get-FileHash $s).Hash -eq (Get-FileHash (Join-Path $dst $n)).Hash) { Remove-Item -LiteralPath $s -Force; R "OK  $n -> Drive\Dev_Sistemas\Tokens\GitHub (conferido, origem removida)" }
        else { R "ERRO ${n}: conferencia falhou, origem mantida" }
    }
} else { R "AVISO Drive nao encontrado em $tok (Google Drive para computador ligado?). Tokens mantidos em Documentos." }
# 4) relatorio de teste
$t = Join-Path $docs 'teste_claude_local.txt'
if (Test-Path $t) { Move-Item -LiteralPath $t -Destination (Join-Path $Base 'Logs\teste_claude_local.txt') -Force; R 'OK  teste_claude_local.txt -> Logs' }
R ''
R '--- Documentos\UStracker_Backups agora ---'
Get-ChildItem -LiteralPath $docs -Force | ForEach-Object { R ('  ' + $_.Name) }
R "=== fim ==="
