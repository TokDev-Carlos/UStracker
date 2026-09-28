# UStracker — Handoff técnico para outra IA

Este pacote é a base de desenvolvimento autocontida do UStracker `1.00.01.000` (schema `3`). Ele foi montado a partir da fonte canônica arquivada e conferida contra a instalação ativa em `C:\UStracker` em 28/09/2026.

O pacote serve para entender, editar, testar e reempacotar o sistema. Ele não contém dados reais, credenciais, bancos, backups, caches, executáveis publicados nem o runtime portátil.

## Leia nesta ordem

1. `AI_HANDOFF.md` — contrato deste pacote.
2. `docs/handoff/2026-09-28-ustracker-reestruturacao-incremental.md` — plano de execução revisado e adaptado ao sistema real.
3. `CODEX_EXECUCAO.md` — histórico técnico e decisões da preparação R2.
4. `README.md` e `CHECKPOINT_R2_FINAL.md` — visão da versão atual.
5. `src/ustracker/db.py`, `server.py`, `services.py` e `extensions.py` — banco, API e regras.
6. `frontend/app.js`, `frontend/styles.css` e `frontend/ui/` — interface atual.
7. `host/Shared/`, `host/Bootstrap/`, `host/Shell/` e `host/Updater/` — inicialização, WebView2 e encerramento Windows.
8. `tests/` — regressões e comportamento comprovado.
9. `tools/package.ps1` — empacotamento oficial.
10. `docs/handoff/AUDITORIA_BASELINE.md` e `MANIFEST_SHA256.csv` — rastreabilidade do pacote.

## Contrato de trabalho

- Crie uma cópia isolada deste diretório e inicialize Git antes de editar; esta base não inclui `.git`.
- Não edite diretamente `C:\UStracker`, a instalação em uso, nem `C:\UStracker\Runtime`.
- Não copie `UserData` para o projeto. Bancos reais, backups `.usbk`, perfil WebView2 e credenciais ficam fora do trabalho de desenvolvimento.
- Preserve a versão atual como baseline. As mudanças do plano devem ser incrementais, com checkpoint e teste a cada tarefa.
- O schema atual é `3`. As migrações planejadas até o schema `8` devem ser sequenciais, transacionais, idempotentes e testadas a partir de uma cópia sintética ou sanitizada.
- Não publique Release, não assine binários e não substitua a instalação ativa sem autorização explícita.
- Antes de declarar conclusão, execute toda a suíte, gere o pacote e faça smoke test do executável em uma pasta limpa.

## Baseline comprovado em 28/09/2026

- Backend: 11 testes aprovados (`test_r2_*.py`).
- Frontend: 8 testes aprovados (`r2_ui.test.mjs`).
- Sintaxe JavaScript: aprovada.
- Compilação Python: aprovada.
- Hosts .NET: Bootstrap, Shell e Updater compilam com sucesso. O único aviso observado foi `NU1900`, porque o índice remoto de vulnerabilidades do NuGet estava indisponível.
- Os 18 arquivos do backend, os 51 arquivos do frontend e os três executáveis publicados da fonte arquivada correspondem byte a byte à instalação ativa.

## Comandos de validação

Execute na raiz extraída deste handoff. Em PowerShell:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
$env:USTRACKER_DEV_PLAINTEXT = '1'
python -m unittest discover -s tests -p 'test_r2_*.py' -v
node --test tests\r2_ui.test.mjs
node --check frontend\app.js
python -m compileall -q src\ustracker tests
dotnet build host\Bootstrap\Bootstrap.csproj
dotnet build host\Shell\Shell.csproj
dotnet build host\Updater\Updater.csproj
```

Na máquina auditada, o Python portátil também pode ser usado:

```powershell
C:\UStracker\Runtime\python.exe -m unittest discover -s tests -p 'test_r2_*.py' -v
```

## Dependências e empacotamento

- Python de desenvolvimento auditado: `3.13.15`.
- Node auditado: `24.19.0`.
- .NET SDK auditado: `10.0.400`.
- Dependências Python estão fixadas em `requirements-runtime.txt` e `requirements-package.txt`.
- O projeto usa `Microsoft.Web.WebView2` `1.0.4191.47`.
- `tools/package.ps1` é a referência de empacotamento e contém URLs e hashes dos redistribuíveis.
- Este handoff não inclui o cache offline de aproximadamente 272 MB. Portanto, o primeiro empacotamento em outra máquina precisa de rede ou de um cache separado com os artefatos cujos hashes são verificados pelo script.
- O fluxo existente gera a instalação portátil; ele não implementa MSI nem assinatura de código.

## O que deliberadamente ficou de fora

`UserData`, bancos `.db`, backups `.usbk`, logs, dumps, segredos, chaves privadas, perfil WebView2, `Runtime`, `Redist`, `Dist`, `.git`, ambientes virtuais, caches Python, `bin`, `obj`, PDBs e ZIPs anteriores.

O ZIP antigo de instalação também não está aninhado aqui: além de ser redundante, contém um snapshot desatualizado de dados reais. Seu hash de referência está registrado na auditoria.
