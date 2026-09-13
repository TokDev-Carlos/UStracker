[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$OutDir = ""
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
if ([string]::IsNullOrWhiteSpace($RepoRoot)) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
if ([string]::IsNullOrWhiteSpace($RepoRoot)) { throw 'RepoRoot nao pode ser determinado' }
$RepoRoot = (Resolve-Path $RepoRoot).Path
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $RepoRoot 'Dist' }
$version = (Get-Content (Join-Path $RepoRoot 'VERSION.json') -Raw | ConvertFrom-Json).version
$candidate = Join-Path $OutDir ("UStracker_{0}_win-x64" -f $version)
$zipPath = $candidate + '.zip'
Remove-Item $candidate -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $candidate | Out-Null

function Copy-Tree([string]$Source,[string]$Destination) {
    if (!(Test-Path $Source)) { throw "Fonte ausente: $Source" }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item (Join-Path $Source '*') $Destination -Recurse -Force
}

$cache = Join-Path $OutDir '_cache'
New-Item -ItemType Directory -Force -Path $cache | Out-Null
$pythonZip = Join-Path $cache 'python-3.13.15-embed-amd64.zip'
$pythonUrl = 'https://www.python.org/ftp/python/3.13.15/python-3.13.15-embed-amd64.zip'
$pythonExpected = 'D1F04D990AEE1253D8569E8E5104E30FA9F5FA830899F14843448872D936A2CF'
if (!(Test-Path $pythonZip)) { Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonZip -UseBasicParsing }
$pythonActual = (Get-FileHash $pythonZip -Algorithm SHA256).Hash
if ($pythonActual -ne $pythonExpected) { throw "Hash CPython invalido: $pythonActual" }
$runtime = Join-Path $candidate 'Runtime'
Expand-Archive -Path $pythonZip -DestinationPath $runtime -Force
$site = Join-Path $runtime 'Lib\site-packages'
New-Item -ItemType Directory -Force -Path $site | Out-Null

$wheelDir = Join-Path $cache 'wheels'
New-Item -ItemType Directory -Force -Path $wheelDir | Out-Null
python -m pip download --only-binary=:all: --no-deps 'sqlcipher3==0.6.2' -d $wheelDir
if ($LASTEXITCODE -ne 0) { throw 'Falha ao baixar sqlcipher3' }
$wheel = Get-ChildItem $wheelDir -Filter 'sqlcipher3-0.6.2-*-win_amd64.whl' | Select-Object -First 1
if ($null -eq $wheel) { throw 'Wheel sqlcipher3 cp313 win_amd64 nao localizado' }
$sqlExpected = '9DC959FF792228C6DF836CFD3667C713AE13E6E18DC2905C9D5666558606E832'
$sqlActual = (Get-FileHash $wheel.FullName -Algorithm SHA256).Hash
if ($sqlActual -ne $sqlExpected) { throw "Hash sqlcipher3 invalido: $sqlActual" }
python -m pip install --disable-pip-version-check --no-compile --target $site -r (Join-Path $RepoRoot 'requirements-package.txt') $wheel.FullName
if ($LASTEXITCODE -ne 0) { throw 'Falha ao montar dependencias Python' }
Copy-Tree (Join-Path $RepoRoot 'src\ustracker') (Join-Path $site 'ustracker')
Get-ChildItem (Join-Path $site 'ustracker') -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

$pth = Get-ChildItem $runtime -Filter 'python*._pth' | Select-Object -First 1
if ($null -eq $pth) { throw 'python._pth nao localizado' }
@('python313.zip','.', 'Lib\site-packages','import site') | Set-Content $pth.FullName -Encoding ASCII

Copy-Tree (Join-Path $RepoRoot 'frontend') (Join-Path $candidate 'frontend')
Copy-Tree (Join-Path $RepoRoot 'Trust') (Join-Path $candidate 'Trust')
Copy-Tree (Join-Path $RepoRoot 'docs') (Join-Path $candidate 'Docs')
Copy-Item (Join-Path $RepoRoot 'VERSION.json') $candidate -Force
Copy-Item (Join-Path $RepoRoot 'current.json') $candidate -Force
Copy-Item (Join-Path $RepoRoot 'LICENSE.txt') $candidate -Force
Copy-Item (Join-Path $RepoRoot 'NOTICE.txt') $candidate -Force

function Find-BuildFile([string]$Root,[string]$Name) {
    $item = Get-ChildItem $Root -Recurse -File -Filter $Name | Where-Object { $_.FullName -match '\\Release\\' } | Select-Object -First 1
    if ($null -eq $item) { throw "Build ausente: $Name" }
    return $item.FullName
}
$shellExe = Find-BuildFile (Join-Path $RepoRoot 'host\Shell\bin') 'UStracker.Shell.exe'
$shellDir = Split-Path -Parent $shellExe
Copy-Tree $shellDir $candidate
$bootstrapExe = Find-BuildFile (Join-Path $RepoRoot 'host\Bootstrap\bin') 'UStracker.exe'
Copy-Item $bootstrapExe $candidate -Force
$bootstrapConfig = $bootstrapExe + '.config'; if (Test-Path $bootstrapConfig) { Copy-Item $bootstrapConfig $candidate -Force }
$updaterExe = Find-BuildFile (Join-Path $RepoRoot 'host\Updater\bin') 'UStracker.Updater.exe'
Copy-Item $updaterExe $candidate -Force
$updaterConfig = $updaterExe + '.config'; if (Test-Path $updaterConfig) { Copy-Item $updaterConfig $candidate -Force }

# Offline WebView2 runtime installer, pinned to the Microsoft/winget manifest for 152.0.4191.53.
$redist = Join-Path $candidate 'Redist'; New-Item -ItemType Directory -Force -Path $redist | Out-Null
$wv2Cache = Join-Path $cache 'MicrosoftEdgeWebView2RuntimeInstallerX64-152.0.4191.53.exe'
$wv2Url = 'https://msedge.sf.dl.delivery.mp.microsoft.com/filestreamingservice/files/b7e683e6-e94c-4576-bfe5-34852785a4d6/MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
$wv2Expected = '987A9D8B3107E84F9B53B4A077D28AE4814FC3D964D5A55C559E7334BBF24D61'
if (!(Test-Path $wv2Cache)) { Invoke-WebRequest -Uri $wv2Url -OutFile $wv2Cache -UseBasicParsing }
$wv2Actual = (Get-FileHash $wv2Cache -Algorithm SHA256).Hash
if ($wv2Actual -ne $wv2Expected) { throw "Hash WebView2 invalido: $wv2Actual" }
$sig = Get-AuthenticodeSignature $wv2Cache
if ($sig.Status -ne 'Valid') { throw "Assinatura Authenticode WebView2 invalida: $($sig.Status)" }
if ($null -eq $sig.SignerCertificate -or $sig.SignerCertificate.Subject -notmatch 'Microsoft') { throw 'Certificado Authenticode WebView2 nao pertence a Microsoft' }
Copy-Item $wv2Cache (Join-Path $redist 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe') -Force

$runtimePython = Join-Path $runtime 'python.exe'
& $runtimePython -c "import fastapi,uvicorn,cryptography,PIL,openpyxl,sqlcipher3; c=sqlcipher3.connect(':memory:'); print('SQLCipher',c.execute('pragma cipher_version').fetchone()[0]); import ustracker; print('UStracker',ustracker.__version__)"
if ($LASTEXITCODE -ne 0) { throw 'Smoke test do Runtime falhou' }

& $runtimePython (Join-Path $RepoRoot 'tools\generate_sbom.py') (Join-Path $candidate 'SBOM.json')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar SBOM' }

New-Item -ItemType Directory -Force -Path (Join-Path $candidate 'UserData') | Out-Null
@"
UStracker $version
1. Extraia a pasta inteira para um disco local NTFS.
2. Execute UStracker.exe.
3. No primeiro uso, cadastre o Administrador 1 e conclua os Administradores 2 e 3 com os tickets exibidos.
4. Production e Test sao isolados; nao mova UserData enquanto o sistema estiver em uso.
5. Se o WebView2 nao existir, o instalador offline x64 incluido sera executado pelo Shell.
"@ | Set-Content (Join-Path $candidate 'LEIA-ME.txt') -Encoding UTF8

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $candidate '*') -DestinationPath $zipPath -CompressionLevel Optimal
$hash = (Get-FileHash $zipPath -Algorithm SHA256).Hash
"$hash  $(Split-Path $zipPath -Leaf)" | Set-Content ($zipPath + '.sha256') -Encoding ASCII
Write-Host "PACKAGE=$zipPath"
Write-Host "SHA256=$hash"
