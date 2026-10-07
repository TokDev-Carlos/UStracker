@echo off
rem UStracker - Aplicador de Patch (pede permissao de administrador do Windows)
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Aplicador_Patch.ps1"
