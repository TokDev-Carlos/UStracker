param(
    [Parameter(Mandatory = $true)]
    [string]$Candidate
)

$ErrorActionPreference = 'Stop'
$Candidate = (Resolve-Path $Candidate).Path
$stage = Join-Path $env:RUNNER_TEMP ("ustracker-portable-smoke-" + [Guid]::NewGuid().ToString('N'))
$launcher = $null
$backendPid = $null

function Get-Csrf([string]$BaseUrl, [Microsoft.PowerShell.Commands.WebRequestSession]$Session) {
    $result = Invoke-RestMethod -Uri "$BaseUrl/api/v1/auth/csrf" -Method Get -WebSession $Session
    return [string]$result.csrf
}

function Post-Json([string]$Uri, [hashtable]$Payload, [string]$Csrf, [Microsoft.PowerShell.Commands.WebRequestSession]$Session) {
    $headers = @{ 'X-CSRF-Token' = $Csrf }
    $body = $Payload | ConvertTo-Json -Compress -Depth 8
    return Invoke-RestMethod -Uri $Uri -Method Post -WebSession $Session -Headers $headers -ContentType 'application/json' -Body $body
}

try {
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    Expand-Archive -Path $Candidate -DestinationPath $stage -Force

    $exe = Join-Path $stage 'UStracker.exe'
    if (-not (Test-Path $exe)) { throw "UStracker.exe ausente no candidato: $Candidate" }

    $launcher = Start-Process -FilePath $exe -WorkingDirectory $stage -PassThru
    $stateFile = Join-Path $stage 'UserData\State\backend.json'
    $deadline = (Get-Date).AddSeconds(45)
    $baseUrl = $null

    while ((Get-Date) -lt $deadline) {
        if (Test-Path $stateFile) {
            try {
                $state = Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
                $backendPid = [int]$state.pid
                $candidateBase = "http://127.0.0.1:$([int]$state.port)"
                $health = Invoke-RestMethod -Uri "$candidateBase/api/v1/health" -Method Get -TimeoutSec 2
                if ($health.status -eq 'ok') {
                    $baseUrl = $candidateBase
                    break
                }
            } catch { }
        }
        Start-Sleep -Milliseconds 250
    }

    if (-not $baseUrl) {
        if ($launcher -and $launcher.HasExited) { throw "UStracker.exe encerrou prematuramente com codigo $($launcher.ExitCode)" }
        throw 'UStracker.exe nao publicou um backend saudavel em ate 45 segundos.'
    }

    $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $setup = Invoke-RestMethod -Uri "$baseUrl/api/v1/auth/setup-status" -Method Get -WebSession $session
    if ([int]$setup.enrolled -ne 0) { throw "Pacote novo deveria iniciar sem administradores; enrolled=$($setup.enrolled)" }

    $csrf = Get-Csrf $baseUrl $session
    $bootstrap = Post-Json "$baseUrl/api/v1/auth/bootstrap" @{ name='Smoke Admin 1'; password='StrongPass!123' } $csrf $session
    if ($bootstrap.tickets.Count -ne 2) { throw 'Bootstrap nao retornou os dois tickets de enrollment.' }

    $slot = 2
    foreach ($ticket in $bootstrap.tickets) {
        $csrf = Get-Csrf $baseUrl $session
        Post-Json "$baseUrl/api/v1/auth/enroll" @{ ticket=[string]$ticket; name="Smoke Admin $slot"; password="StrongPass!${slot}xx" } $csrf $session | Out-Null
        $slot++
    }

    $setup = Invoke-RestMethod -Uri "$baseUrl/api/v1/auth/setup-status" -Method Get -WebSession $session
    if (-not [bool]$setup.complete -or [int]$setup.enrolled -ne 3) { throw 'Enrollment dos tres administradores nao persistiu no backend empacotado.' }

    $csrf = Get-Csrf $baseUrl $session
    Post-Json "$baseUrl/api/v1/auth/login" @{ name='Smoke Admin 1'; password='StrongPass!123' } $csrf $session | Out-Null
    $me = Invoke-RestMethod -Uri "$baseUrl/api/v1/auth/me" -Method Get -WebSession $session
    if ($me.name -ne 'Smoke Admin 1') { throw 'Login autenticado nao retornou o administrador esperado.' }

    $dashboard = Invoke-RestMethod -Uri "$baseUrl/api/v1/dashboard" -Method Get -WebSession $session
    if ($null -eq $dashboard) { throw 'Dashboard nao respondeu apos login.' }

    Write-Host "PORTABLE_SMOKE_PASS base=$baseUrl admin=$($me.name)"
}
finally {
    if ($backendPid) { Stop-Process -Id $backendPid -Force -ErrorAction SilentlyContinue }
    Get-Process -Name 'UStracker.Shell' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    if ($launcher -and -not $launcher.HasExited) { Stop-Process -Id $launcher.Id -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Milliseconds 300
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
}
