# UStracker 2.3.0 - data layout for Windows (run by the installer, elevated).
#   Program: <App>  (C:\Program Files\UStracker, read-only for users)
#   Data:    <Data>\UserData  (C:\ProgramData\UStracker\UserData, users can write)
#   <App>\UserData is a junction to the data folder, so the program keeps using "UserData".
# Scan (2.3.0): every UStracker data found on this computer is checked.
#   - validated by the Adm Global (State\adm-global.ok with the x_pub of this version's Trust): kept/migrated;
#   - not validated (older system): COPIED to <Backup>\<origin> (Documentos\UStracker_backup_old\...), then removed.
#   Old program folders (C:\UStracker) are removed after their data is safe in the backup.
# Exit: 0 ok, 10 copy failed (nothing removed), 11 junction failed, 12 removal failed.
param([string]$App, [string]$Data, [string]$Old = '', [string]$Old2 = '', [string]$Log, [string]$Backup, [string]$Trust)

$ErrorActionPreference = 'Stop'
function L([string]$m) { try { Add-Content -LiteralPath $Log -Value ((Get-Date -Format 's') + ' ' + $m) } catch {} }
$xpub = ''
try { $xpub = [string]((Get-Content -LiteralPath $Trust -Raw | ConvertFrom-Json).x_pub) } catch { L ('trust not read: ' + $_.Exception.Message) }

function Has-System([string]$ud) {
    return (Test-Path -LiteralPath (Join-Path $ud 'Auth\auth.db')) -or (Test-Path -LiteralPath (Join-Path $ud 'Production\ustracker.db'))
}
function Is-Validated([string]$ud) {
    $marker = Join-Path $ud 'State\adm-global.ok'
    if (-not $xpub -or -not (Test-Path -LiteralPath $marker)) { return $false }
    try { return ([string]((Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json).x_pub) -eq $xpub) } catch { return $false }
}
function Is-Junction([string]$p) {
    if (-not (Test-Path -LiteralPath $p)) { return $false }
    return [bool]((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)
}
function Copy-Tree([string]$from, [string]$to) {
    L "copy $from -> $to"
    & robocopy.exe $from $to /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /XD (Join-Path $from 'State\WebView2') /XF backend.json /NFL /NDL /NJH /NJS /NP | Out-Null
    $code = $LASTEXITCODE
    L "robocopy exit $code"
    return ($code -lt 8)
}
function Remove-Tree([string]$p) {
    if (-not (Test-Path -LiteralPath $p)) { return }
    # junctions inside go first WITHOUT following them
    Get-ChildItem -LiteralPath $p -Recurse -Force -Attributes ReparsePoint -ErrorAction SilentlyContinue |
        Sort-Object { $_.FullName.Length } -Descending | ForEach-Object { & cmd.exe /c rmdir "$($_.FullName)" | Out-Null }
    Remove-Item -LiteralPath $p -Recurse -Force
}
# old system data -> backup, then removed
function Retire([string]$ud, [string]$label) {
    $dest = Join-Path $Backup $label
    if (-not (Copy-Tree $ud $dest)) { L "backup failed: $ud"; exit 10 }
    if (-not (Test-Path -LiteralPath (Join-Path $dest 'Auth')) -and (Test-Path -LiteralPath (Join-Path $ud 'Auth'))) { L "backup check failed: $ud"; exit 10 }
    try { Remove-Tree $ud; L "not validated by the Adm Global: $ud moved to $dest" } catch { L ('remove failed: ' + $_.Exception.Message); exit 12 }
}

New-Item -ItemType Directory -Force -Path $Data | Out-Null
$target = Join-Path $Data 'UserData'
$link = Join-Path $App 'UserData'
L "=== UStracker setup-data App=$App Data=$Data Old=$Old Old2=$Old2 Backup=$Backup"

# 1) data already in ProgramData
$hasData = $false
if ((Test-Path -LiteralPath $target) -and (Has-System $target)) {
    if (Is-Validated $target) { $hasData = $true; L 'ProgramData data validated by the Adm Global: kept' }
    else { Retire $target 'ProgramData_UserData' }
}

# 2) a real UserData folder inside the program folder (old portable layout installed here)
if ((Test-Path -LiteralPath $link) -and -not (Is-Junction $link)) {
    if ((Has-System $link) -and (Is-Validated $link) -and -not $hasData) {
        if (-not (Copy-Tree $link $target)) { L 'copy failed'; exit 10 }
        $hasData = $true
        try { Remove-Tree $link } catch { L ('remove failed: ' + $_.Exception.Message); exit 12 }
    } elseif (Has-System $link) { Retire $link 'Programa_UserData' }
    else { try { Remove-Tree $link } catch { L ('remove failed: ' + $_.Exception.Message); exit 12 } }
}

# 3) old installs somewhere else (registry location, C:\UStracker)
$olds = @($Old, $Old2) | Where-Object { $_ -and ($_.TrimEnd('\') -ne $App.TrimEnd('\')) } | Select-Object -Unique
foreach ($o in $olds) {
    if (-not (Test-Path -LiteralPath $o)) { continue }
    $oud = Join-Path $o 'UserData'
    if ((Test-Path -LiteralPath $oud) -and -not (Is-Junction $oud) -and (Has-System $oud)) {
        if ((Is-Validated $oud) -and -not $hasData) {
            if (-not (Copy-Tree $oud $target)) { L 'copy failed'; exit 10 }
            $hasData = $true
        } else {  # not validated (or a second copy): the backup keeps it
            $dest = Join-Path $Backup ((Split-Path $o -Leaf) + '_UserData')
            if (-not (Copy-Tree $oud $dest)) { L "backup failed: $oud"; exit 10 }
            L "old data $oud copied to $dest"
        }
    }
    try { Remove-Tree $o; L "old program folder removed: $o" }
    catch { L ('old folder not fully removed (in use?): ' + $_.Exception.Message) }
}

# 4) users may write their data (Builtin Users = S-1-5-32-545)
New-Item -ItemType Directory -Force -Path (Join-Path $target 'Logs') | Out-Null
& icacls.exe $Data /grant '*S-1-5-32-545:(OI)(CI)M' /T /C /Q | Out-Null
L "icacls exit $LASTEXITCODE"

# 5) junction <App>\UserData -> <Data>\UserData
if (-not (Test-Path -LiteralPath $link)) {
    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    L 'junction created'
}
if (-not (Test-Path -LiteralPath (Join-Path $link 'Logs'))) { L 'junction check failed'; exit 11 }
L 'setup-data ok'
exit 0
