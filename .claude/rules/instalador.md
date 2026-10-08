---
paths:
  - "release/**/*"
  - "tools/build_installer.sh"
---
# Instalador (NSIS)
- `tools/build_installer.sh <instalador_anterior.exe> <pasta>`: mescla o código novo sobre o Runtime anterior; trava se faltar arquivo.
- Ícone obrigatório (`-DICON`); placa sem chave da empresa; varredura de dados antigos em `setup-data.ps1`.
- Arquivos `.ps1` em ASCII; nunca nomear função PowerShell com 1 letra (alias, ex.: `R`).
