# UStracker - testes rapidos locais (Python + telas). Resultado em ..\Logs\testes_<data>.txt
param([string]$Base = 'D:\PROGRAMAS\UStracker_Project')
$code = Join-Path $Base 'Codigo'
$log = Join-Path $Base ("Logs\testes_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.txt')
Push-Location $code
$env:PYTHONPATH = 'src;.'; $env:USTRACKER_DEV_PLAINTEXT = '1'
$py = Join-Path $code '.venv\Scripts\python.exe'
"=== Python ===" | Out-File $log -Encoding UTF8
& $py -m unittest discover -s tests -p 'test_*.py' 2>&1 | Select-String -Pattern '^(ERROR|FAIL):|^Ran |^OK|^FAILED' | ForEach-Object { $_.Line } | Out-File $log -Append -Encoding UTF8
"=== Telas ===" | Out-File $log -Append -Encoding UTF8
if (Get-Command node -ErrorAction SilentlyContinue) {
    $files = Get-ChildItem tests -Filter '*.test.mjs' | ForEach-Object { $_.FullName }
    node --test @files 2>&1 | Select-String -Pattern '^not ok|^# (pass|fail)' | ForEach-Object { $_.Line } | Out-File $log -Append -Encoding UTF8
} else { 'node nao instalado' | Out-File $log -Append -Encoding UTF8 }
Pop-Location
Get-Content $log
