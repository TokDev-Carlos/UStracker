# Contexto do projeto — UStracker

- **O que é:** sistema Windows (desktop) de clientes, frotas/veículos, planos, assinaturas, pagamentos, despesas e fiscal administrativo, com nuvem própria no Google Drive.
- **Stack:** Python 3.13 + FastAPI (backend local, `src/ustracker/`), JS em módulos ES sem framework (`frontend/`), host .NET com WebView2 (`host/`), Apps Script (`cloud/Code.gs`), instalador NSIS (`release/installer/`).
- **Dados no PC:** `C:\ProgramData\UStracker\UserData\` (Auth, Production, Test, Media, State, Logs); programa em `C:\Program Files\UStracker\` (junção para UserData).
- **Banco:** SQLite cifrado (SQLCipher), uma base por ambiente (Produção/Teste); chave dos dados (VRK) protegida por senha (scrypt + AES-GCM).
- **Acesso:** Adm Global (Token Mestre no repositório privado `acesso-UStracker` + PIN) acima de todos; Administrador; usuários por pacote de permissões (Gerente, Operador…).
- **Nuvem:** Apps Script assinado (HMAC) guarda snapshots cifrados e anexos numa pasta do Drive achada por ID; placa (`placa.json`) aponta os bancos da empresa.
- **Atualizações:** pacotes `.usup` assinados (Ed25519); canal `updates/` na branch `main` do GitHub `TokDev-Carlos/UStracker`; `.uspatch` pelo Aplicador de Patch.
- **Entrega:** código na branch `Dev`; versão lançada na `main` + tag + Release.
