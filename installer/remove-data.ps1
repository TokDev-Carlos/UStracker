# UStracker 2.2.0 - "Remover tudo" on uninstall (run elevated by the uninstaller).
# 1) copies UserData to <Backup>\UserData (the WebView2 cache is skipped); 2) only if the copy worked, deletes <Data>.
# Exit: 0 ok, 10 copy failed (nothing deleted), 12 delete incomplete.
param([string]$Data, [string]$Backup, [string]$Log)

$ErrorActionPreference = 'Stop'
function L([string]$m) { try { Add-Content -LiteralPath $Log -Value ((Get-Date -Format 's') + ' ' + $m) } catch {} }
$source = Join-Path $Data 'UserData'
New-Item -ItemType Directory -Force -Path $Backup | Out-Null
L "=== UStracker remove-data Data=$Data Backup=$Backup"
if (Test-Path -LiteralPath $source) {
    & robocopy.exe $source (Join-Path $Backup 'UserData') /E /COPY:DAT /R:1 /W:1 /XD (Join-Path $source 'State\WebView2') /XF backend.json /NFL /NDL /NJH /NJS /NP | Out-Null
    $code = $LASTEXITCODE
    L "robocopy exit $code"
    if ($code -ge 8) { exit 10 }
    if (-not (Test-Path -LiteralPath (Join-Path $Backup 'UserData'))) { exit 10 }
}
try { Remove-Item -LiteralPath $Data -Recurse -Force; L 'data removed' } catch { L ('delete incomplete: ' + $_.Exception.Message); exit 12 }
exit 0
