# UStracker 2.2.0 - data layout for Windows (run by the installer, elevated).
#   Program: <App>  (C:\Program Files\UStracker, read-only for users)
#   Data:    <Data>\UserData  (C:\ProgramData\UStracker\UserData, users can write)
#   <App>\UserData is a junction to the data folder, so the program keeps using "UserData".
# Migration: data of an old install (C:\UStracker) is COPIED (never moved/deleted); the old folder is renamed.
# Exit: 0 ok, 10 copy failed (nothing changed), 11 junction failed.
param([string]$App, [string]$Data, [string]$Old = '', [string]$Log)

$ErrorActionPreference = 'Stop'
function L([string]$m) { try { Add-Content -LiteralPath $Log -Value ((Get-Date -Format 's') + ' ' + $m) } catch {} }
function Copy-Data([string]$from, [string]$to) {
    L "copy $from -> $to"
    & robocopy.exe $from $to /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /XF backend.json /NFL /NDL /NJH /NJS /NP | Out-Null
    $code = $LASTEXITCODE
    L "robocopy exit $code"
    return ($code -lt 8)
}

New-Item -ItemType Directory -Force -Path $Data | Out-Null
$target = Join-Path $Data 'UserData'
$link = Join-Path $App 'UserData'
New-Item -ItemType Directory -Force -Path (Join-Path $target 'Logs') | Out-Null
L "=== UStracker setup-data App=$App Data=$Data Old=$Old"
$hasData = Test-Path -LiteralPath (Join-Path $target 'Auth\auth.db')

# 1) a real UserData folder inside the program folder (old portable layout installed here)
if (Test-Path -LiteralPath $link) {
    $item = Get-Item -LiteralPath $link -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        L 'junction already present'
    } else {
        if (-not $hasData) {
            if (-not (Copy-Data $link $target)) { L 'copy failed'; exit 10 }
            $hasData = $true
        }
        $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        Rename-Item -LiteralPath $link -NewName ('UserData.migrado-' + $stamp)
        L "old in-place UserData renamed (UserData.migrado-$stamp)"
    }
}

# 2) an old install somewhere else (C:\UStracker)
if ($Old -and ($Old -ne $App) -and (Test-Path -LiteralPath (Join-Path $Old 'UserData'))) {
    if (-not $hasData) {
        if (-not (Copy-Data (Join-Path $Old 'UserData') $target)) { L 'copy failed'; exit 10 }
        $hasData = $true
    } else {
        L 'data already in ProgramData: old UserData not copied'
    }
}

# 3) users may write their data (Builtin Users = S-1-5-32-545)
& icacls.exe $Data /grant '*S-1-5-32-545:(OI)(CI)M' /T /C /Q | Out-Null
L "icacls exit $LASTEXITCODE"

# 4) junction <App>\UserData -> <Data>\UserData
if (-not (Test-Path -LiteralPath $link)) {
    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    L 'junction created'
}
if (-not (Test-Path -LiteralPath (Join-Path $link 'Logs'))) { L 'junction check failed'; exit 11 }

# 5) retire the old folder (kept as a copy; the user deletes it later)
if ($Old -and ($Old -ne $App) -and (Test-Path -LiteralPath $Old)) {
    $leaf = (Split-Path $Old -Leaf) + '_antigo'
    if (Test-Path -LiteralPath (Join-Path (Split-Path $Old -Parent) $leaf)) { $leaf = $leaf + '_' + (Get-Date -Format 'yyyyMMdd_HHmmss') }
    try { Rename-Item -LiteralPath $Old -NewName $leaf; L "old folder renamed to $leaf" }
    catch { L ('old folder kept (in use): ' + $_.Exception.Message) }
}
L 'setup-data ok'
exit 0
