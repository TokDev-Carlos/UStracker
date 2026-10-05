# installer — instalador único

`UStracker.nsi` (NSIS 3) gera **`UStracker_install_x64.exe`** com tudo dentro.

```bash
makensis -INPUTCHARSET UTF8 -DSRC=<pasta do programa pronta> -DVERSION=2.2.0 \
  -DWV2=<MicrosoftEdgeWebView2RuntimeInstallerX64.exe> \
  -DPLACA=<placa-bootstrap.json> -DICON=host/Bootstrap/Assets/UStracker.ico UStracker.nsi
```
- Sem `-DWV2` ou `-DPLACA` a compilação falha (de propósito).
- `placa-bootstrap.json`: endereço da placa + chave pública, **sem** a chave da empresa (2.2.0). A chave da empresa chega na ativação pelo Adm Global (`acesso-UStracker/company-key.json`).
- `Trust/adm-global.json` (com o token só de leitura) vem da pasta do programa; nunca versionar.

Estrutura instalada (2.2.0):
- Programa: `C:\Program Files\UStracker` (só administradores alteram).
- Dados: `C:\ProgramData\UStracker\UserData` (usuários do Windows gravam), ligado ao programa pela junção `UserData`.
- `setup-data.ps1`: cria a pasta de dados, permissões, junção e migra `C:\UStracker` (copia; a pasta antiga vira `C:\UStracker_antigo`).
- `remove-data.ps1`: "Remover tudo" na desinstalação — copia para `Documentos\UStracker_Backups\Desinstalacao_<data>` e só então apaga.

Fecha o sistema aberto antes de instalar; `/S` instala em silêncio; `Desinstalar_UStracker.exe /S [/REMOVERTUDO]`. Log: `UserData\Logs\instalacao.log`.

`LEIA-ME.txt` é o texto curto que acompanha a instalação.
