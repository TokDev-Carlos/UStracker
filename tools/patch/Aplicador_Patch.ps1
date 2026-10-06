# UStracker - Aplicador de Patch (janela). Abre pelo Aplicar_Patch.cmd (pede permissao de administrador).
# 1 - Atualizar Sistema da Maquina: backup dos dados, aplica o pacote, confere; volta sozinho se a versao nova nao abrir.
# 2 - Atualizar Todos os Sistemas: faz o 1 e, se deu certo, lanca no canal de atualizacao (os outros computadores recebem).
#     O token do GitHub e pedido na hora (arquivo da pasta Tokens) e nao fica salvo.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

# --- administrador (Arquivos de Programas e protegido)
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', "`"$PSCommandPath`"")
    exit
}

$Here = Split-Path -Parent $PSCommandPath
$Tool = Join-Path $Here 'patch_tool.py'
$Docs = [Environment]::GetFolderPath('MyDocuments')
$BackupDir = Join-Path $Docs 'UStracker_Backups'
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$LogFile = Join-Path $BackupDir 'Aplicador_Patch.log'
function Log([string]$m) { try { Add-Content -LiteralPath $LogFile -Value ((Get-Date -Format 's') + ' ' + $m) -Encoding UTF8 } catch {} }

function Find-Install {
    foreach ($view in @('Registry64', 'Registry32')) {
        try {
            $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine, [Microsoft.Win32.RegistryView]::$view)
            $k = $base.OpenSubKey('SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\UStracker')
            if ($k) { $p = $k.GetValue('InstallLocation'); if ($p -and (Test-Path (Join-Path $p 'version.md'))) { return $p } }
        } catch {}
    }
    foreach ($p in @("$env:ProgramFiles\UStracker", 'C:\UStracker')) { if (Test-Path (Join-Path $p 'version.md')) { return $p } }
    return ''
}

# --- chama o patch_tool.py com o Python do UStracker instalado; devolve o objeto JSON
function Invoke-Tool([string]$root, [string[]]$toolArgs, [string]$stdin = '') {
    $py = Join-Path $root 'Runtime\python.exe'
    if (-not (Test-Path $py)) { return @{ error = "Python do UStracker nao encontrado em $root" } }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $py
    $quoted = @('-I', "`"$Tool`"") + ($toolArgs | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } })
    $psi.Arguments = ($quoted -join ' ')
    $psi.WorkingDirectory = $root
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.RedirectStandardInput = $true
    $psi.StandardOutputEncoding = [Text.Encoding]::UTF8
    $psi.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
    $p = [Diagnostics.Process]::Start($psi)
    if ($stdin) { $p.StandardInput.Write($stdin) }
    $p.StandardInput.Close()
    $outTask = $p.StandardOutput.ReadToEndAsync(); $errTask = $p.StandardError.ReadToEndAsync()
    while (-not $p.HasExited) { [System.Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 150 }
    $out = $outTask.Result; $err = $errTask.Result
    $line = ($out -split "`n" | Where-Object { $_.Trim().StartsWith('{') } | Select-Object -Last 1)
    if (-not $line) { Log "sem resposta: $err"; return @{ error = 'o aplicador nao respondeu (veja Aplicador_Patch.log)' } }
    return ($line | ConvertFrom-Json)
}

function Close-UStracker([string]$root) {
    $procs = Get-Process | Where-Object { $_.Path -and $_.Path -like "$root\*" }
    if (-not $procs) { return $true }
    $r = [System.Windows.Forms.MessageBox]::Show("O UStracker esta aberto neste computador.`r`n`r`nO ideal e fechar pelo botao Encerrar (envia as ultimas alteracoes para a nuvem).`r`nClique em OK para fecha-lo agora e continuar.", 'Aplicador de Patch', 'OKCancel', 'Warning')
    if ($r -ne 'OK') { return $false }
    $procs | Stop-Process -Force
    Start-Sleep -Seconds 3
    return $true
}

# --- janela
$form = New-Object System.Windows.Forms.Form
$form.Text = 'UStracker - Aplicador de Patch'
$form.Size = New-Object System.Drawing.Size(640, 470)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$ico = Join-Path $Here 'UStracker.ico'
if (Test-Path $ico) { $form.Icon = New-Object System.Drawing.Icon($ico) }

function Add-Label($text, $x, $y, $w = 580, $h = 24) { $l = New-Object System.Windows.Forms.Label; $l.Text = $text; $l.Location = New-Object System.Drawing.Point($x, $y); $l.Size = New-Object System.Drawing.Size($w, $h); $form.Controls.Add($l); return $l }

Add-Label 'Pasta do UStracker neste computador:' 20 15 | Out-Null
$txtRoot = New-Object System.Windows.Forms.TextBox; $txtRoot.Location = New-Object System.Drawing.Point(20, 40); $txtRoot.Size = New-Object System.Drawing.Size(470, 26); $txtRoot.Text = (Find-Install); $form.Controls.Add($txtRoot)
$btnRoot = New-Object System.Windows.Forms.Button; $btnRoot.Text = 'Outra...'; $btnRoot.Location = New-Object System.Drawing.Point(500, 38); $btnRoot.Size = New-Object System.Drawing.Size(100, 30); $form.Controls.Add($btnRoot)

Add-Label 'Pacote de patch (.uspatch):' 20 80 | Out-Null
$txtPatch = New-Object System.Windows.Forms.TextBox; $txtPatch.Location = New-Object System.Drawing.Point(20, 105); $txtPatch.Size = New-Object System.Drawing.Size(470, 26); $txtPatch.ReadOnly = $true; $form.Controls.Add($txtPatch)
$btnPatch = New-Object System.Windows.Forms.Button; $btnPatch.Text = 'Escolher...'; $btnPatch.Location = New-Object System.Drawing.Point(500, 103); $btnPatch.Size = New-Object System.Drawing.Size(100, 30); $form.Controls.Add($btnPatch)

$lblInfo = Add-Label 'Escolha o pacote.' 20 145 580 90
$lblInfo.Font = New-Object System.Drawing.Font('Segoe UI', 10)

$btnLocal = New-Object System.Windows.Forms.Button; $btnLocal.Text = '1 - Atualizar Sistema da Maquina'; $btnLocal.Location = New-Object System.Drawing.Point(20, 250); $btnLocal.Size = New-Object System.Drawing.Size(580, 44); $btnLocal.Enabled = $false; $form.Controls.Add($btnLocal)
$btnAll = New-Object System.Windows.Forms.Button; $btnAll.Text = '2 - Atualizar Todos os Sistemas (esta maquina + lancamento na nuvem)'; $btnAll.Location = New-Object System.Drawing.Point(20, 302); $btnAll.Size = New-Object System.Drawing.Size(580, 44); $btnAll.Enabled = $false; $form.Controls.Add($btnAll)
$lblStatus = Add-Label '' 20 360 580 60
$lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(30, 64, 175)

$script:info = $null
function Refresh-Info {
    $script:info = $null; $btnLocal.Enabled = $false; $btnAll.Enabled = $false
    if (-not $txtPatch.Text) { return }
    $lblInfo.Text = 'Conferindo o pacote...'; $form.Refresh()
    $r = Invoke-Tool $txtRoot.Text @('info', '--root', $txtRoot.Text, '--patch', $txtPatch.Text)
    if ($r.error) { $lblInfo.Text = "Pacote recusado: $($r.error)"; $lblInfo.ForeColor = 'Firebrick'; return }
    $script:info = $r; $lblInfo.ForeColor = 'Black'
    $lvl = if ($r.level -eq 'critical') { 'OBRIGATORIA' } else { 'normal' }
    $lblInfo.Text = "Assinatura conferida.`r`nInstalado nesta maquina: $($r.from)   ->   Pacote: $($r.to)  ($lvl)`r`n$($r.notes)"
    $btnLocal.Enabled = [bool]$r.newer
    $btnAll.Enabled = $true
    if (-not $r.newer) { $lblStatus.Text = "Esta maquina ja esta na $($r.from). A opcao 2 ainda pode lancar a $($r.to) na nuvem." }
}

function Apply-Here {
    if (-not (Close-UStracker $txtRoot.Text)) { return $false }
    $lblStatus.Text = 'Fazendo backup dos dados e aplicando... (nao feche esta janela)'; $form.Refresh()
    $form.Cursor = 'WaitCursor'
    $r = Invoke-Tool $txtRoot.Text @('apply', '--root', $txtRoot.Text, '--patch', $txtPatch.Text, '--backup-dir', $BackupDir)
    $form.Cursor = 'Default'
    if ($r.error) { Log "apply ERRO: $($r.error)"; $lblStatus.Text = ''; [System.Windows.Forms.MessageBox]::Show("Nao aplicado: $($r.error)", 'Aplicador de Patch', 'OK', 'Error') | Out-Null; return $false }
    Log "apply OK $($r.from) -> $($r.to) backup=$($r.backup)"
    $lblStatus.Text = "Esta maquina foi atualizada: $($r.from) -> $($r.to). Backup dos dados: $($r.backup)"
    return $true
}

$btnRoot.Add_Click({ $d = New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description = 'Pasta do UStracker (onde fica o version.md)'; if ($d.ShowDialog() -eq 'OK') { $txtRoot.Text = $d.SelectedPath; Refresh-Info } })
$btnPatch.Add_Click({ $d = New-Object System.Windows.Forms.OpenFileDialog; $d.Filter = 'Patch do UStracker (*.uspatch)|*.uspatch'; $d.InitialDirectory = $BackupDir; if ($d.ShowDialog() -eq 'OK') { $txtPatch.Text = $d.FileName; Refresh-Info } })

$btnLocal.Add_Click({
    if (-not $script:info) { return }
    if ([System.Windows.Forms.MessageBox]::Show("Atualizar ESTA maquina de $($script:info.from) para $($script:info.to)?`r`nOs dados sao copiados antes para Documentos\UStracker_Backups.", 'Aplicador de Patch', 'YesNo', 'Question') -ne 'Yes') { return }
    if (Apply-Here) { Refresh-Info; [System.Windows.Forms.MessageBox]::Show('Pronto. Abra o UStracker e confira.', 'Aplicador de Patch', 'OK', 'Information') | Out-Null }
})

$btnAll.Add_Click({
    if (-not $script:info) { return }
    $v = $script:info.to
    if ([System.Windows.Forms.MessageBox]::Show("Atualizar TODOS os sistemas para a $v?`r`n`r`n1) esta maquina e atualizada e conferida;`r`n2) a $v e lancada na nuvem: os outros computadores recebem pela atualizacao automatica.", 'Aplicador de Patch', 'YesNo', 'Warning') -ne 'Yes') { return }
    if ($script:info.newer) { if (-not (Apply-Here)) { return } }
    if ([System.Windows.Forms.MessageBox]::Show("Esta maquina esta na $v.`r`nAbra o UStracker e confira se esta tudo certo ANTES de lancar.`r`n`r`nLancar a $v para todos agora?", 'Aplicador de Patch', 'YesNo', 'Question') -ne 'Yes') { $lblStatus.Text = 'Lancamento na nuvem adiado. Use a opcao 2 de novo quando quiser.'; return }
    $d = New-Object System.Windows.Forms.OpenFileDialog; $d.Title = 'Arquivo com o token do GitHub (pasta Tokens do Drive)'; $d.Filter = 'Texto (*.txt)|*.txt|Todos (*.*)|*.*'
    if ($d.ShowDialog() -ne 'OK') { return }
    $token = [IO.File]::ReadAllText($d.FileName)
    $lblStatus.Text = 'Lancando na nuvem...'; $form.Refresh(); $form.Cursor = 'WaitCursor'
    $r = Invoke-Tool $txtRoot.Text @('publish', '--root', $txtRoot.Text, '--patch', $txtPatch.Text) $token
    $token = $null; [GC]::Collect()
    $form.Cursor = 'Default'
    if ($r.error) { Log "publish ERRO: $($r.error)"; $lblStatus.Text = ''; [System.Windows.Forms.MessageBox]::Show("Nao lancado: $($r.error)", 'Aplicador de Patch', 'OK', 'Error') | Out-Null; return }
    Log "publish OK $($r.published) (antes: $($r.previous))"
    $lblStatus.Text = "Lancado: $($r.published). Os outros computadores recebem em ate 3 horas (ou ao abrir o sistema)."
    [System.Windows.Forms.MessageBox]::Show("Versao $($r.published) lancada na nuvem.", 'Aplicador de Patch', 'OK', 'Information') | Out-Null
})

[void]$form.ShowDialog()
