; UStracker — instalador para Windows 10/11 x64 (NSIS 3, script UTF-8: makensis -INPUTCHARSET UTF8)
; Compilar: makensis -INPUTCHARSET UTF8 -DSRC=<pasta do programa> -DVERSION=2.2.0
;           -DWV2=<MicrosoftEdgeWebView2RuntimeInstallerX64.exe> -DPLACA=<placa-bootstrap.json> -DICON=<host/Bootstrap/Assets/UStracker.ico> [-DOUT=...] UStracker.nsi
;
; 2.2.0 — estrutura Windows:
;   Programa  C:\Program Files\UStracker          (protegido: só administradores do Windows alteram)
;   Dados     C:\ProgramData\UStracker\UserData   (usuários do Windows podem gravar)
;   O programa enxerga os dados em "UserData" por uma junção (Program Files\UStracker\UserData → ProgramData).
; 2.3.0 — varredura: dados validados pelo Adm Global ficam; um sistema antigo NÃO validado é descartado (os dados vão
; antes para Documentos\UStracker_backup_old\<data>). Desinstalar: "Manter dados" (padrão) ou "Remover tudo" (com cópia antes).
; Silencioso: /S (instala/atualiza).  Desinstalação silenciosa: Desinstalar_UStracker.exe /S [/REMOVERTUDO]

Unicode true
SetCompressor lzma
SetCompressorDictSize 64
RequestExecutionLevel admin
ManifestDPIAware true

!ifndef VERSION
  !define VERSION "2.3.0"
!endif
!ifndef SRC
  !error "Defina -DSRC=<pasta do programa>"
!endif
!ifndef WV2
  !error "Defina -DWV2=<MicrosoftEdgeWebView2RuntimeInstallerX64.exe> (o WebView2 vai dentro do instalador)"
!endif
!ifndef PLACA
  !error "Defina -DPLACA=<placa-bootstrap.json> (endereço da nuvem da empresa, vai dentro do instalador)"
!endif
!ifndef OUT
  !define OUT "UStracker_install_x64.exe"
!endif
; 2.3.0 — guard: never build an installer without the program pieces (build 1 of 2.3.0 shipped without Runtime)
!macro REQUIRE path
  !if /FileExists "${SRC}/${path}"
  !else
    !error "Programa incompleto: falta ${SRC}/${path}"
  !endif
!macroend
!insertmacro REQUIRE "Runtime/python.exe"
!insertmacro REQUIRE "Runtime/Lib/site-packages/fastapi/__init__.py"
!insertmacro REQUIRE "Runtime/Lib/site-packages/uvicorn/__init__.py"
!insertmacro REQUIRE "Runtime/Lib/site-packages/ustracker/server.py"
!insertmacro REQUIRE "frontend/index.html"
!insertmacro REQUIRE "UStracker.exe"
!insertmacro REQUIRE "UStracker.Shell.exe"
!insertmacro REQUIRE "UStracker.Updater.exe"
!insertmacro REQUIRE "WebView2Loader.dll"
!insertmacro REQUIRE "Trust/adm-global.json"
!insertmacro REQUIRE "Trust/update_public_key.pem"
!ifndef ICON
  !error "Defina -DICON=<UStracker.ico> (ícone do instalador: host/Bootstrap/Assets/UStracker.ico)"
!endif

!define APP "UStracker"
!define PUBLISHER "CRJ"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\UStracker"
!define WV2_GUID "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
!define OLD_DEFAULT "C:\UStracker"

Name "${APP} ${VERSION}"
OutFile "${OUT}"
InstallDir "$PROGRAMFILES64\${APP}"
BrandingText "${APP} ${VERSION} — ${PUBLISHER}"
VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=1046 "ProductName" "${APP}"
VIAddVersionKey /LANG=1046 "CompanyName" "${PUBLISHER}"
VIAddVersionKey /LANG=1046 "FileDescription" "Instalador do ${APP}"
VIAddVersionKey /LANG=1046 "ProductVersion" "${VERSION}"
VIAddVersionKey /LANG=1046 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=1046 "LegalCopyright" "© ${PUBLISHER}"

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "x64.nsh"
!include "nsDialogs.nsh"

Var DataDir
Var OldDir
Var BackupDir
Var OldVersion
Var LogFile
Var UnMode
Var UnText
Var UnRadioKeep
Var UnRadioAll

!ifdef ICON
  !define MUI_ICON "${ICON}"
  !define MUI_UNICON "${ICON}"
!endif
!define MUI_ABORTWARNING
!define MUI_ABORTWARNING_TEXT "Cancelar a instalação do ${APP}? Nada foi alterado ainda se você ainda não clicou em Instalar."
!define MUI_WELCOMEPAGE_TITLE "Instalar o ${APP} ${VERSION}"
!define MUI_WELCOMEPAGE_TEXT "Este assistente instala ou atualiza o ${APP} neste computador.$\r$\n$\r$\n• Programa: Arquivos de Programas\${APP} (protegido)$\r$\n• Dados: ProgramData\${APP} (clientes, finanças, fotos e backups)$\r$\n$\r$\nSe houver uma versão antiga aberta, ela será fechada. Um sistema antigo que não foi validado pelo Adm Global é descartado: os dados dele vão antes para Documentos\UStracker_backup_old."
!define MUI_LICENSEPAGE_TEXT_TOP "Leia os termos de uso do ${APP}."
!define MUI_FINISHPAGE_TITLE "${APP} ${VERSION} instalado"
!define MUI_FINISHPAGE_TEXT "Pronto.$\r$\n$\r$\nNa primeira abertura, o ${APP} pede a ATIVAÇÃO pelo Adm Global e já entra no sistema. Em Sistema, o Adm Global cria o Administrador local deste computador."
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Abrir o ${APP} agora"
!define MUI_FINISHPAGE_RUN_FUNCTION OpenAppAsUser

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${SRC}/LICENSE.txt"
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
UninstPage custom un.ModePage un.ModeLeave
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "PortugueseBR"

; ----------------------------------------------------------------------------------------------- comuns
!macro LOG text
  FileOpen $9 "$LogFile" a
  ${If} $9 != ""
    FileSeek $9 0 END
    FileWrite $9 "${text}$\r$\n"
    FileClose $9
  ${EndIf}
  DetailPrint "${text}"
!macroend

; Close every UStracker process (program folder new or old). Asks first, unless silent.
!macro CLOSE_APP un
Function ${un}CloseApp
  StrCpy $1 "$$p=Get-Process | Where-Object { $$_.Path -and ($$_.Path -like '$INSTDIR\*' -or $$_.Path -like '${OLD_DEFAULT}\*'"
  ${If} $OldDir != ""
    StrCpy $1 "$1 -or $$_.Path -like '$OldDir\*'"
  ${EndIf}
  StrCpy $1 "$1) };"
  nsExec::ExecToStack 'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$1 if($$p){exit 1}else{exit 0}"'
  Pop $0
  Pop $2
  ${If} $0 == "1"
    MessageBox MB_ICONEXCLAMATION|MB_OKCANCEL "O ${APP} está aberto neste computador.$\r$\n$\r$\nClique em OK para fechá-lo e continuar (as alterações já gravadas não se perdem)." /SD IDOK IDOK close
    Abort
    close:
    nsExec::ExecToStack 'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$1 $$p | Stop-Process -Force; Start-Sleep -Seconds 2"'
    Pop $0
    Pop $2
  ${EndIf}
FunctionEnd
!macroend
!insertmacro CLOSE_APP ""
!insertmacro CLOSE_APP "un."

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "O ${APP} precisa do Windows 64 bits." /SD IDOK
    Abort
  ${EndIf}
  SetRegView 64
  SetShellVarContext all
  ReadEnvStr $0 PROGRAMDATA
  ${If} $0 == ""
    StrCpy $0 "C:\ProgramData"
  ${EndIf}
  StrCpy $DataDir "$0\${APP}"
  ; old install: registry first, then the old default folder
  ReadRegStr $OldDir HKLM "${UNINST_KEY}" "InstallLocation"
  ReadRegStr $OldVersion HKLM "${UNINST_KEY}" "DisplayVersion"
  ${If} $OldDir == ""
  ${AndIf} ${FileExists} "${OLD_DEFAULT}\UStracker.exe"
    StrCpy $OldDir "${OLD_DEFAULT}"
  ${EndIf}
  ${If} $OldDir == "$INSTDIR"
    StrCpy $OldDir ""
  ${EndIf}
  ${If} $OldDir != ""
  ${AndIfNot} ${FileExists} "$OldDir\*.*"
    StrCpy $OldDir ""
  ${EndIf}
FunctionEnd

; offline WebView2 runtime embedded at build time (installed only when missing)
Function EnsureWebView2
  ReadRegStr $0 HKLM "SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\${WV2_GUID}" "pv"
  ${If} $0 == ""
  ${OrIf} $0 == "0.0.0.0"
    ReadRegStr $0 HKCU "Software\Microsoft\EdgeUpdate\Clients\${WV2_GUID}" "pv"
  ${EndIf}
  ${If} $0 == ""
  ${OrIf} $0 == "0.0.0.0"
    !insertmacro LOG "Instalando o Microsoft WebView2 (componente da tela do sistema)..."
    InitPluginsDir
    SetOutPath "$PLUGINSDIR"
    SetCompress off
    File /oname=MicrosoftEdgeWebView2RuntimeInstallerX64.exe "${WV2}"
    SetCompress auto
    ExecWait '"$PLUGINSDIR\MicrosoftEdgeWebView2RuntimeInstallerX64.exe" /silent /install' $0
    !insertmacro LOG "WebView2: código $0"
    SetOutPath "$INSTDIR"
  ${Else}
    !insertmacro LOG "Microsoft WebView2 encontrado ($0)."
  ${EndIf}
FunctionEnd

; The finish page runs elevated: open the app as the signed-in user instead (never as administrator).
Function OpenAppAsUser
  Exec '"$WINDIR\explorer.exe" "$INSTDIR\UStracker.exe"'
FunctionEnd

; ----------------------------------------------------------------------------------------------- instalar
Section "Programa" SecMain
  SectionIn RO
  CreateDirectory "$DataDir"
  StrCpy $LogFile "$DataDir\instalacao.log"
  !insertmacro LOG "=== ${APP} ${VERSION}: instalação iniciada (anterior: $OldVersion $OldDir)"
  Call CloseApp

  ; 1) program files (old program code removed first so no stale file survives)
  SetOutPath "$INSTDIR"
  RMDir /r "$INSTDIR\Runtime\Lib\site-packages\ustracker"
  RMDir /r "$INSTDIR\frontend"
  RMDir /r "$INSTDIR\Instalador"
  RMDir /r "$INSTDIR\Redist"
  File /r /x "UserData" /x "Trust" /x "Instalador" /x "Redist" /x "*.pdb" /x "__pycache__" "${SRC}/*.*"
  ; Trust: always the keys of THIS version (update key, Adm Global, cloud address without the company key)
  SetOutPath "$INSTDIR\Trust"
  Delete "$INSTDIR\Trust\*.*"
  File "${SRC}/Trust/update_public_key.pem"
  File "${SRC}/Trust/adm-global.json"
  File "${SRC}/Trust/README.txt"
  File /oname=placa-bootstrap.json "${PLACA}"
  SetOutPath "$INSTDIR"
  !insertmacro LOG "Programa copiado para $INSTDIR"

  ; 2) data folder in ProgramData + junction + scan: data not validated by the Adm Global -> Documentos\UStracker_backup_old
  SetShellVarContext current
  ${GetTime} "" "L" $0 $1 $2 $3 $4 $5 $6
  StrCpy $BackupDir "$DOCUMENTS\UStracker_backup_old\$2$1$0_$4$5$6"
  SetShellVarContext all
  InitPluginsDir
  File /oname=$PLUGINSDIR\setup-data.ps1 "setup-data.ps1"
  nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PLUGINSDIR\setup-data.ps1" -App "$INSTDIR" -Data "$DataDir" -Old "$OldDir" -Old2 "${OLD_DEFAULT}" -Log "$LogFile" -Backup "$BackupDir" -Trust "$INSTDIR\Trust\adm-global.json"'
  Pop $0
  ${If} $0 != "0"
    !insertmacro LOG "ERRO na pasta de dados (código $0)"
    MessageBox MB_ICONSTOP "Não foi possível preparar a pasta de dados (código $0).$\r$\nDetalhes em:$\r$\n$LogFile$\r$\nCópia dos dados antigos (se houver):$\r$\n$BackupDir" /SD IDOK
    Abort
  ${EndIf}
  !insertmacro LOG "Dados em $DataDir\UserData"

  ; 3) faster first start: compile the program once (users cannot write in Program Files)
  nsExec::ExecToLog '"$INSTDIR\Runtime\python.exe" -m compileall -q "$INSTDIR\Runtime\Lib\site-packages"'
  Pop $0

  Call EnsureWebView2

  ; 4) shortcuts (all users) — the old ones are replaced
  Delete "$DESKTOP\${APP}.lnk"
  RMDir /r "$SMPROGRAMS\${APP}"
  CreateDirectory "$SMPROGRAMS\${APP}"
  CreateShortCut "$SMPROGRAMS\${APP}\${APP}.lnk" "$INSTDIR\UStracker.exe" "" "$INSTDIR\UStracker.exe" 0
  CreateShortCut "$SMPROGRAMS\${APP}\Manual do ${APP}.lnk" "$INSTDIR\Docs\MANUAL_USUARIO.md"
  CreateShortCut "$SMPROGRAMS\${APP}\Desinstalar ${APP}.lnk" "$INSTDIR\Desinstalar_UStracker.exe"
  CreateShortCut "$DESKTOP\${APP}.lnk" "$INSTDIR\UStracker.exe" "" "$INSTDIR\UStracker.exe" 0

  ; 5) Programs and Features
  WriteUninstaller "$INSTDIR\Desinstalar_UStracker.exe"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "${APP}"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "${PUBLISHER}"
  WriteRegStr HKLM "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINST_KEY}" "DataLocation" "$DataDir"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\UStracker.exe"
  WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Desinstalar_UStracker.exe"'
  WriteRegStr HKLM "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\Desinstalar_UStracker.exe" /S'
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K /G=0" $0 $1 $2
  WriteRegDWORD HKLM "${UNINST_KEY}" "EstimatedSize" $0
  !insertmacro LOG "=== ${APP} ${VERSION} instalado"
SectionEnd

; ----------------------------------------------------------------------------------------------- desinstalar
Function un.onInit
  SetRegView 64
  SetShellVarContext all
  ReadRegStr $DataDir HKLM "${UNINST_KEY}" "DataLocation"
  ${If} $DataDir == ""
    ReadEnvStr $0 PROGRAMDATA
    StrCpy $DataDir "$0\${APP}"
  ${EndIf}
  StrCpy $UnMode "keep"
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/REMOVERTUDO" $1
  ${IfNot} ${Errors}
    StrCpy $UnMode "all"
  ${EndIf}
  StrCpy $OldDir ""
FunctionEnd

Function un.ModePage
  !insertmacro MUI_HEADER_TEXT "O que fazer com os dados?" "Clientes, finanças, fotos e backups deste computador."
  nsDialogs::Create 1018
  Pop $0
  ${NSD_CreateRadioButton} 0 0 100% 14u "Manter dados (recomendado) — remove só o programa; os dados ficam para reinstalar."
  Pop $UnRadioKeep
  ${NSD_CreateRadioButton} 0 22u 100% 14u "Remover tudo — apaga os dados deste computador (antes, uma cópia vai para Documentos)."
  Pop $UnRadioAll
  ${NSD_CreateLabel} 12u 42u 100% 22u "Para remover tudo, digite REMOVER abaixo. A nuvem da empresa NÃO é apagada; os outros computadores continuam funcionando."
  Pop $0
  ${NSD_CreateText} 12u 66u 120u 13u ""
  Pop $UnText
  ${If} $UnMode == "all"
    ${NSD_Check} $UnRadioAll
  ${Else}
    ${NSD_Check} $UnRadioKeep
  ${EndIf}
  nsDialogs::Show
FunctionEnd

Function un.ModeLeave
  ${NSD_GetState} $UnRadioAll $0
  ${If} $0 == ${BST_CHECKED}
    ${NSD_GetText} $UnText $1
    ${If} $1 != "REMOVER"
      MessageBox MB_ICONEXCLAMATION "Para remover todos os dados, digite REMOVER (em maiúsculas)."
      Abort
    ${EndIf}
    StrCpy $UnMode "all"
  ${Else}
    StrCpy $UnMode "keep"
  ${EndIf}
FunctionEnd

Section "Uninstall"
  StrCpy $LogFile "$DataDir\UserData\Logs\instalacao.log"
  !insertmacro LOG "=== desinstalação ($UnMode)"
  Call un.CloseApp

  ; the junction goes first, WITHOUT following it (the data stays untouched here)
  nsExec::ExecToLog 'cmd.exe /c rmdir "$INSTDIR\UserData"'
  Pop $0
  ${If} ${FileExists} "$INSTDIR\UserData\*.*"
    !insertmacro LOG "a pasta UserData do programa não é uma junção: mantida"
  ${EndIf}
  RMDir /r "$INSTDIR\Runtime"
  RMDir /r "$INSTDIR\runtimes"
  RMDir /r "$INSTDIR\frontend"
  RMDir /r "$INSTDIR\Docs"
  RMDir /r "$INSTDIR\Trust"
  RMDir /r "$INSTDIR\Redist"
  RMDir /r "$INSTDIR\.update-work"
  Delete "$INSTDIR\*.exe"
  Delete "$INSTDIR\*.config"
  Delete "$INSTDIR\*.dll"
  Delete "$INSTDIR\*.json"
  Delete "$INSTDIR\*.md"
  Delete "$INSTDIR\*.txt"
  Delete "$INSTDIR\*.ico"
  RMDir "$INSTDIR"

  Delete "$DESKTOP\${APP}.lnk"
  RMDir /r "$SMPROGRAMS\${APP}"
  DeleteRegKey HKLM "${UNINST_KEY}"

  ${If} $UnMode == "all"
    SetShellVarContext current
    ${GetTime} "" "L" $0 $1 $2 $3 $4 $5 $6
    StrCpy $7 "$DOCUMENTS\UStracker_Backups\Desinstalacao_$2$1$0_$4$5"
    SetShellVarContext all
    InitPluginsDir
    File /oname=$PLUGINSDIR\remove-data.ps1 "remove-data.ps1"
    nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PLUGINSDIR\remove-data.ps1" -Data "$DataDir" -Backup "$7" -Log "$7\desinstalacao.log"'
    Pop $0
    ${If} $0 == "0"
      MessageBox MB_ICONINFORMATION "${APP} removido, com os dados deste computador.$\r$\n$\r$\nCópia de segurança dos dados:$\r$\n$7" /SD IDOK
    ${Else}
      MessageBox MB_ICONEXCLAMATION "O programa foi removido, mas os dados NÃO foram apagados (código $0).$\r$\nEles continuam em:$\r$\n$DataDir" /SD IDOK
    ${EndIf}
  ${Else}
    MessageBox MB_ICONINFORMATION "Programa removido.$\r$\n$\r$\nSeus dados continuam em:$\r$\n$DataDir$\r$\n$\r$\nAo reinstalar, tudo volta como estava." /SD IDOK
  ${EndIf}
SectionEnd
