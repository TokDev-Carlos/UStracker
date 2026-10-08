---
paths:
  - "cloud/**/*"
---
# Apps Script (nuvem no Google Drive)
- Pastas e arquivos do Drive sempre por **ID** (`FOLDER_ID` nas propriedades); nome só como recriação.
- Toda escrita concorrente dentro de `LockService`; requisições assinadas (HMAC + nonce).
- Testar com o harness `cloud/harness/gas_server.mjs` (`tests/c01_apps_script.test.mjs`).
- Mudou o `Code.gs`? O Carlos precisa colar no editor e publicar nova versão da implantação — avisar no `VALIDAR.md`.
