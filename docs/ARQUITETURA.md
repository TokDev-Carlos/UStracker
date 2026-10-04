# Arquitetura — UStracker 2.0.0

## Camadas
1. **Host Windows (`host/`)**: `UStracker.exe` (Bootstrap) inicia o backend e abre o **Shell** (.NET + WebView2). `Updater` aplica pacotes assinados.
2. **Tela (`frontend/`)**: HTML + módulos ES sem framework. `app.js` (roteamento e telas), `pages/` (Clientes, Nuvem, Usuários…), `ui/` (componentes, diálogos, permissões).
3. **API local (`src/ustracker/server.py`)**: FastAPI em `127.0.0.1`, CSRF em toda escrita, sessão por cookie, middleware de permissões (`access.py`).
4. **Domínio**: `services.py`, `clients.py`, `mobility*.py`, `catalog.py`, `commercial.py`, `billing.py`, `finance.py`, `expenses.py`, `trash.py`…
5. **Dados (`db.py`)**: SQLCipher, schema 14, um banco por ambiente (`UserData/Production`, `UserData/Test`). Toda operação multi-tabela numa transação; auditoria encadeada.

## Segurança e acesso (`auth.py`, `access.py`, `crypto.py`)
- VRK (chave raiz) cifrada por senha em envelopes: Administradores (posições 1..3) e usuários (1000+id).
- Pacotes de permissão `modulo.acao`: Operador, Gerente e personalizados. Rota sem regra = só Administrador.
- Fotos/anexos cifrados com AES-GCM (`media.py`, `attachments.py`).

## Nuvem e Servidores (`cloud.py`, `station.py`, `placa.py`, `cloud/Code.gs`)
- Cada computador é um **Servidor N**. Antes de gravar pede a **vez** (lease 120 s); envia 4 s após a mudança; busca novidades a cada 25 s; acessos são mesclados, nunca substituídos.
- **Placa de direção** (`placa.json`, assinada Ed25519): Banco 1 principal, Banco 2+ espelhos. Chaves de conexão cifradas com a chave da empresa, que viaja só dentro do instalador (`Trust/placa-bootstrap.json`).
- Computador novo: `/cloud/bootstrap` → `/auth/join` baixa tudo e entra.

## Instalador (`installer/UStracker.nsi`)
NSIS 3, um arquivo: programa + WebView2 offline + placa. Atualiza por cima sem tocar `UserData`.

## Testes
`tests/test_*.py` (unittest, inclusive nuvem real contra simulador do Apps Script) e `tests/*.test.mjs` (telas).
