# cloud — nuvem da empresa (Google Apps Script + Drive)

- `Code.gs`: script publicado como App da Web (*Qualquer pessoa*). Guarda snapshots cifrados, fotos, acessos e a **vez de gravar** (`lease`). Guia: [`docs/NUVEM_GOOGLE_DRIVE.md`](../docs/NUVEM_GOOGLE_DRIVE.md).
- `harness/`: simulador em Node dos serviços Google usado pelos testes (`gas_server.mjs`).

Ao mudar o `Code.gs`, publique uma **nova versão** da implantação no Apps Script.
