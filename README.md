# UStracker

Sistema Windows de controle de clientes, frotas, finanças e nuvem (CRJ).

| Pasta | Conteúdo |
|---|---|
| `src/ustracker/` | Backend Python (FastAPI) |
| `frontend/` | Telas (JS/CSS) |
| `host/` | Host .NET (WebView2) |
| `cloud/` | Apps Script da nuvem (Google Drive) |
| `release/` | Instalador NSIS, LEIA-ME e documentos do usuário |
| `tools/` | Build do instalador, pacotes de patch (`make_patch.py`, `patch/`), scripts locais (`dev/`) |
| `tests/` | Testes Python (`test_*.py`) e de tela (`*.test.mjs`) |
| `Trust/` | Chaves públicas (atualização / Adm Global) |

Branches: `main` = versão lançada · `Dev` = desenvolvimento. Canal de atualização: `updates/` (na `main`).
Regras e caminhos de trabalho: `CLAUDE.md`. Novidades por versão: `release/Docs/NOVIDADES.md`.
