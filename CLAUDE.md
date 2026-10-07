# UStracker — instruções para o Claude (local e nuvem)

Sistema Windows de controle de clientes, frotas, finanças e nuvem (dono: Carlos / CRJ). Responder sempre em português do Brasil.

## Regras do projeto (obrigatórias)
1. Ser conciso — direto ao ponto.
2. Dados limpos — backup antes de qualquer alteração; lixeira antes de apagar.
3. Fontes testadas — só código com testes RED→GREEN passando.
4. Uma coisa por vez — sequência lógica, sem dependência cruzada.
5. Memória focada — só pontos críticos: checklists, decisões, bloqueadores, URIs.
6. Progresso sequencial — cada etapa conclui antes da próxima, marco visível.
7. Sem perfeccionismo — suficiente para validar, melhorar depois.
8. Testes pesados só após validação do usuário.
9. Nunca apagar sem confirmação — lista exata e hash do backup conferido.
10. Transações ACID — operação multi-tabela numa transação única.
11. Zero residual — nada de temporário, log ou candidato após promoção.
12. Usuário primeiro — perguntar decisões e aguardar resposta antes de executar.

Segurança: nunca mostrar, logar ou commitar tokens, PIN, senha ou chave da empresa. Tokens ficam em Drive › Dev_Sistemas › Tokens.

## Fluxo de trabalho (misto)
- Nuvem (Claude no claude.ai/Cowork): código, testes, build, pacotes. Código vai para o GitHub (branch `Dev`).
- Local (Claude Code neste PC): aplicar e testar no Windows real, seguindo o `VALIDAR.md` da entrega; gravar o resultado em `Logs\` ou na pasta da entrega (a nuvem lê).
- Toda entrega deixa registro em `Conhecimento\` (formato fixo, ver abaixo). Consultar `Conhecimento\Problemas_Solucoes` antes de investigar um erro.

## Caminhos
- Programa instalado: `C:\Program Files\UStracker\` · dados: `C:\ProgramData\UStracker\UserData\` · log da instalação: `C:\ProgramData\UStracker\instalacao.log`
- Desenvolvimento: `D:\PROGRAMAS\UStracker_Project\` → `Codigo\` (este repositório) · `Entregas\<versão>\` · `Ferramentas\` · `Conhecimento\` · `Logs\`
- Backup/histórico: `Documents\UStracker_Backups\` · descartados pela varredura/ativação: `Documents\UStracker_backup_old\`
- Drive (referência é a nuvem; `H:\Meu Drive` é só conveniência): `Dev_Sistemas\`, `Dev_Sistemas\Tokens\`
- GitHub `TokDev-Carlos`: `UStracker` (main = lançada, Dev = desenvolvimento, `updates/` canal de atualização) · `acesso-UStracker` (privado: Token Mestre, chave da empresa)

## Código
- Backend Python (FastAPI) em `src/ustracker/`; telas em `frontend/`; host .NET em `host/`; Apps Script em `cloud/Code.gs`; instalador NSIS em `release/installer/`.
- Testes rápidos (Windows): `Ferramentas\Testes_Rapidos.ps1` ou
  `$env:PYTHONPATH="src;."; $env:USTRACKER_DEV_PLAINTEXT="1"; .venv\Scripts\python -m unittest discover -s tests -p "test_*.py"`
  Telas: `node --test tests/*.test.mjs`.
- Pacote de atualização: `tools/make_patch.py` (precisa da chave de assinatura) → aplicar com `Ferramentas\Aplicador_Patch\Aplicar_Patch.cmd`.
- Instalador: `tools/build_installer.sh` (build na nuvem; trava se faltar Runtime/peças).

## Conhecimento (formato fixo)
- `Problemas_Solucoes\AAAA-MM-DD_<assunto>.md`: Sintoma · Causa · Solução · Como evitar · Versão.
- `Decisoes\AAAA-MM-DD_<assunto>.md`: Decisão · Motivo · Alternativas · Quem decidiu.
- `Ideias\AAAA-MM-DD_<assunto>.md`: ideia em ordem cronológica, origem (usuário/testadores/.docx).
- `Validacoes\<versão>_<data>.md`: o que foi testado, resultado, prints/logs.

## Estado atual (2026-10-07)
- Lançada: **2.4.1** (main + tag v2.4.1 + GitHub Release com instalador). Canal `updates/` continua na 2.1.1 (não publicado de propósito).
- Esta máquina: 2.4.1 + ajuste local dos botões do filtro (já incluído no instalador 2.4.1).
- Entregas: `Entregas\2.4.1\` (instalador + .uspatch), `Entregas\2.3.0\` (instalador anterior). Cópias no Drive: `Dev_Sistemas\UStracker\`.
- Drive: `Dev_Sistemas\Tokens\GitHub` (tokens), `Dev_Sistemas\Tokens\UStracker` (chave de assinatura, chave de redefinição), `Dev_Sistemas\UStracker` (Conhecimento, Ferramentas, Entregas). NÃO mover: `UStracker Cloud` (pasta e Apps Script da nuvem).
- Pendente do usuário: frota — veículo que entra/sai depois do contrato muda a cobrança sozinho ou fica fixo? (hoje: quantidade automática na criação, editável).
- Depois: testes pesados (matriz completa, backup/restore, volume, conflito); publicar canal quando o usuário pedir; placa por empresa no `acesso-<Empresa>`; segurança padrão; conta Google da empresa; WSL2; Docker de build.
