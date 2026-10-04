# installer — instalador único

`UStracker.nsi` (NSIS 3) gera **`UStracker_install_x64.exe`** com tudo dentro.

```bash
makensis -DSRC=<pasta do programa pronta> -DVERSION=2.0.0 \
  -DWV2=<MicrosoftEdgeWebView2RuntimeInstallerX64.exe> \
  -DPLACA=<placa-bootstrap.json> -DICON=<UStracker.ico> UStracker.nsi
```
- Sem `-DWV2` ou `-DPLACA` a compilação falha (de propósito).
- `placa-bootstrap.json` contém a chave da empresa: **nunca** versionar; ele vem de `C:\UStracker\Trust`.
- Atualiza por cima, mantém `UserData`, remove sobras `Redist\`/`Instalador\` de versões antigas.

`LEIA-ME.txt` é o texto curto que acompanha a instalação.
