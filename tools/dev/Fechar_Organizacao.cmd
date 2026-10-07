@echo off
rem UStracker - organiza pastas e prepara o ambiente. Tela completa gravada em Logs\fechar_tela_*.txt
set F=%~dp0
set L=D:\PROGRAMAS\UStracker_Project\Logs
if not exist "%L%" mkdir "%L%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$t=Join-Path '%L%' ('fechar_tela_'+(Get-Date -Format yyyyMMdd_HHmmss)+'.txt'); Start-Transcript -Path $t | Out-Null; & '%F%Organizar_Pastas.ps1'; & '%F%Preparar_Ambiente.ps1'; Stop-Transcript | Out-Null"
echo.
echo Pronto. Relatorios em %L%
pause
