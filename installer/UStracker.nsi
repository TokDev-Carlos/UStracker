; UStracker — instalador para Windows 10/11 x64 (NSIS 3)
; Compilar: makensis -DSRC=<pasta do programa> -DVERSION=2.0.0 -DWV2=<MicrosoftEdgeWebView2RuntimeInstallerX64.exe>
;           -DPLACA=<placa-bootstrap.json> [-DOUT=UStracker_install_x64.exe] UStracker.nsi
; Release 2: um único arquivo leva tudo (programa + WebView2 + endereço da nuvem). Nada ao lado do instalador.
; Regras: instala ou atualiza por cima; NUNCA apaga ou substitui UserData; a chave de atualização (Trust) só entra se faltar.

Unicode true
SetCompressor lzma
SetCompressorDictSize 64
RequestExecutionLevel admin
ManifestDPIAware true

!ifndef VERSION
  !define VERSION "2.0.0"
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

!define APP "UStracker"
!define PUBLISHER "CRJ"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\UStracker"
!define WV2_GUID "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

Name "${APP} ${VERSION}"
OutFile "${OUT}"
InstallDir "C:\UStracker"
InstallDirRegKey HKLM "${UNINST_KEY}" "InstallLocation"
BrandingText "${APP} ${VERSION}"
VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=1046 "ProductName" "${APP}"
VIAddVersionKey /LANG=1046 "FileDescription" "Instalador do ${APP}"
VIAddVersionKey /LANG=1046 "ProductVersion" "${VERSION}"
VIAddVersionKey /LANG=1046 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=1046 "LegalCopyright" "${PUBLISHER}"

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

!ifdef ICON
  !define MUI_ICON "${ICON}"
  !define MUI_UNICON "${ICON}"
!endif
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Instalar o ${APP} ${VERSION}"
!define MUI_WELCOMEPAGE_TEXT "Este assistente instala ou atualiza o ${APP} neste computador.$\r$\n$\r$\nSe o ${APP} já estiver instalado, só o programa é atualizado: seus dados (pasta UserData) continuam intactos.$\r$\n$\r$\nAntes de continuar, feche o ${APP} pelo botão Encerrar."
!define MUI_DIRECTORYPAGE_TEXT_TOP "Pasta do ${APP}. Use uma pasta local (não use pasta de rede nem pasta sincronizada). Para atualizar, escolha a pasta onde ele já está."
!define MUI_FINISHPAGE_TITLE "${APP} pronto"
!define MUI_FINISHPAGE_TEXT "Instalação concluída.$\r$\n$\r$\nAbra o ${APP}. Se a empresa já usa o ${APP}, entre com seu usuário e senha: os dados chegam sozinhos da nuvem. Se for o primeiro computador, cadastre o Administrador."
!define MUI_FINISHPAGE_RUN "$INSTDIR\UStracker.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Abrir o ${APP} agora"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "PortugueseBR"

Function .onInit
  ${IfNot} ${FileExists} "$WINDIR\SysWOW64\*.*"
    MessageBox MB_ICONSTOP "O ${APP} precisa do Windows 64 bits."
    Abort
  ${EndIf}
FunctionEnd

; The app writes UserData\State\backend.json while it is running.
Function WaitAppClosed
  loop:
  ${If} ${FileExists} "$INSTDIR\UserData\State\backend.json"
    MessageBox MB_ICONEXCLAMATION|MB_ABORTRETRYIGNORE "O ${APP} parece estar aberto.$\r$\n$\r$\nFeche pelo botão Encerrar e clique em Repetir.$\r$\n(Ignorar: continuar mesmo assim, se ele já estiver fechado.)" IDRETRY loop IDIGNORE done
    Abort
  ${EndIf}
  done:
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
    DetailPrint "Instalando o Microsoft WebView2 (componente da tela do sistema)..."
    InitPluginsDir
    SetOutPath "$PLUGINSDIR"
    SetCompress off
    File /oname=MicrosoftEdgeWebView2RuntimeInstallerX64.exe "${WV2}"
    SetCompress auto
    ExecWait '"$PLUGINSDIR\MicrosoftEdgeWebView2RuntimeInstallerX64.exe" /silent /install'
    SetOutPath "$INSTDIR"
  ${Else}
    DetailPrint "Microsoft WebView2 encontrado ($0)."
  ${EndIf}
FunctionEnd

Section "Programa" SecMain
  SectionIn RO
  Call WaitAppClosed
  SetOutPath "$INSTDIR"
  ${If} ${FileExists} "$INSTDIR\UserData\*.*"
    DetailPrint "Atualizando: seus dados em UserData são mantidos."
  ${EndIf}
  ; remove only replaceable program code so no stale file survives an update
  RMDir /r "$INSTDIR\Runtime\Lib\site-packages\ustracker"
  RMDir /r "$INSTDIR\frontend"
  ; Release 2: leftovers of the old kit-based installer
  RMDir /r "$INSTDIR\Redist"
  RMDir /r "$INSTDIR\Instalador"
  ; program files
  File /r /x "UserData" /x "Trust" /x "Instalador" /x "Redist" /x "*.pdb" /x "__pycache__" "${SRC}/*.*"
  ; Trust (update public key) is installed only when missing
  SetOverwrite off
  SetOutPath "$INSTDIR\Trust"
  File /nonfatal /r "${SRC}/Trust/*.*"
  SetOverwrite on
  ; S-08: company cloud address (placa), embedded at build time — new computers download the data by themselves
  File /oname=placa-bootstrap.json "${PLACA}"
  SetOutPath "$INSTDIR"
  CreateDirectory "$INSTDIR\UserData"
  ; normal (non-admin) Windows users must be able to write their data
  nsExec::ExecToLog 'icacls "$INSTDIR" /grant *S-1-5-32-545:(OI)(CI)M /T /C /Q'
  Pop $0

  Call EnsureWebView2

  SetShellVarContext all
  CreateDirectory "$SMPROGRAMS\${APP}"
  CreateShortCut "$SMPROGRAMS\${APP}\${APP}.lnk" "$INSTDIR\UStracker.exe" "" "$INSTDIR\UStracker.exe" 0
  CreateShortCut "$SMPROGRAMS\${APP}\Manual do ${APP}.lnk" "$INSTDIR\Docs\MANUAL_USUARIO.md"
  CreateShortCut "$SMPROGRAMS\${APP}\Desinstalar ${APP}.lnk" "$INSTDIR\Desinstalar_UStracker.exe"
  CreateShortCut "$DESKTOP\${APP}.lnk" "$INSTDIR\UStracker.exe" "" "$INSTDIR\UStracker.exe" 0

  WriteUninstaller "$INSTDIR\Desinstalar_UStracker.exe"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "${APP}"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "${PUBLISHER}"
  WriteRegStr HKLM "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\UStracker.exe"
  WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Desinstalar_UStracker.exe"'
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K /G=0" $0 $1 $2
  WriteRegDWORD HKLM "${UNINST_KEY}" "EstimatedSize" $0
SectionEnd

; Uninstall removes the program only. UserData (clients, finance, photos, backups) stays.
Section "Uninstall"
  ${If} ${FileExists} "$INSTDIR\UserData\State\backend.json"
    MessageBox MB_ICONEXCLAMATION "Feche o ${APP} pelo botão Encerrar e rode a desinstalação de novo."
    Abort
  ${EndIf}
  RMDir /r "$INSTDIR\Runtime"
  RMDir /r "$INSTDIR\runtimes"
  RMDir /r "$INSTDIR\frontend"
  RMDir /r "$INSTDIR\Docs"
  RMDir /r "$INSTDIR\Redist"
  Delete "$INSTDIR\UStracker.exe"
  Delete "$INSTDIR\UStracker.exe.config"
  Delete "$INSTDIR\UStracker.Shell.exe"
  Delete "$INSTDIR\UStracker.Shell.exe.config"
  Delete "$INSTDIR\UStracker.Updater.exe"
  Delete "$INSTDIR\UStracker.Updater.exe.config"
  Delete "$INSTDIR\Microsoft.Web.WebView2.*.dll"
  Delete "$INSTDIR\WebView2Loader.dll"
  Delete "$INSTDIR\VERSION.json"
  Delete "$INSTDIR\current.json"
  Delete "$INSTDIR\version.md"
  Delete "$INSTDIR\SBOM.json"
  Delete "$INSTDIR\LEIA-ME.txt"
  Delete "$INSTDIR\LICENSE.txt"
  Delete "$INSTDIR\NOTICE.txt"
  Delete "$INSTDIR\UStracker.ico"
  Delete "$INSTDIR\Desinstalar_UStracker.exe"
  SetShellVarContext all
  Delete "$DESKTOP\${APP}.lnk"
  RMDir /r "$SMPROGRAMS\${APP}"
  DeleteRegKey HKLM "${UNINST_KEY}"
  MessageBox MB_ICONINFORMATION "Programa removido.$\r$\n$\r$\nSeus dados continuam em:$\r$\n$INSTDIR\UserData$\r$\n$\r$\nPara apagá-los de vez, exclua essa pasta manualmente."
SectionEnd
