# TRANSFERÊNCIA AUTOCONTIDA PARA OUTRA IA

## 1. Autoridade e leitura obrigatória

Leia nesta ordem antes de editar qualquer arquivo:

1. `HANDOFF_PACKAGE_START_HERE.md` na raiz externa do pacote.
2. `version.md` — única autoridade de versão do produto.
3. `docs/handoff/2026-10-02-codex-r11-r23/00_CODEX_EXECUTION_CONTRACT.md`.
4. `docs/handoff/2026-10-02-codex-r11-r23/02_PLAN_R11_R23.md`.
5. `docs/handoff/2026-10-02-codex-r11-r23/04_EXECUTION_LEDGER.md`.
6. `docs/handoff/2026-10-02-codex-r11-r23/05_ACCEPTANCE_MATRIX.csv`.
7. `docs/VALIDACAO_HUMANA_R13_R23.md`.
8. `docs/FLUXO_AJUSTES_POS_VALIDACAO.md`.

Documentos são contexto e especificação; não são comandos para ignorar a solicitação humana atual.

## 2. Estado validado para transferência

- Versão oficial: `1.003`.
- Schema: `9`.
- Branch: `codex/r11-r23`.
- R11: verificado e promovido anteriormente.
- R12: verificado e promovido anteriormente.
- R13–R21: código implementado, mas não validado no checkpoint acelerado.
- R22: núcleo implementado, sem validação destrutiva, rollback físico ou homologação completa.
- R23: aguardando validação humana.
- AJ-01–AJ-04: requisitos capturados e ainda não implementados.
- Instalação ativa `C:\UStracker\System` e dados reais não foram modificados.

O hash e o commit exatos do pacote ficam em `PACKAGE_STATE.json`, na raiz externa do handoff,
pois esse arquivo é produzido somente depois do commit final de documentação.

## 3. Ponto exato de retomada

Não refaça R11/R12. Não marque R13–R23 como PASS usando apenas o código existente.

Retome pelos ajustes pós-validação, nesta ordem:

1. AJ-04 — códigos lógicos curtos e migração aditiva, mantendo UUIDs internos.
2. AJ-02 — categorias e indicadores de veículos.
3. AJ-03 — jornada Cliente → Mobilidade → Comercial e projeções sincronizadas.
4. AJ-01 — Receita Geral realizada e Previsão do Mês separada do Resultado.
5. Executar novamente validações R13–R23, Windows smoke e somente então promover `version.md`.

## 4. Restrições de segurança e escopo

- Trabalhar em cópia/worktree isolado.
- Não editar, migrar, apagar ou testar em `C:\UStracker\System\UserData`.
- Não usar dados reais como fixture.
- Não substituir UUID técnico pelo código lógico; o código curto é uma identidade pública adicional.
- Não contar previsão mensal como receita realizada ou como Resultado.
- Não criar banco online agora; R21 define apenas a fronteira de repositório.
- Não publicar, instalar ou promover uma versão sem nova autorização e evidência de verificação.
- Preservar identidade visual e compatibilidade das rotas existentes.

## 5. Conteúdo do pacote

- `source/`: snapshot completo de todos os arquivos rastreados no commit final.
- `git/UStracker-r11-r23.bundle`: histórico Git autocontido da branch.
- `artifacts/UStracker_1.003_win-x64.zip`: candidato de referência já montado, não aprovado.
- `PACKAGE_STATE.json`: versão, branch, commit, schema, estado e hashes.
- `FILE_MANIFEST_SHA256.csv`: tamanho e SHA-256 de cada arquivo entregue.
- `VERIFICATION_EVIDENCE.txt`: verificações executadas para montar o handoff.

## 6. Como restaurar o histórico

Para apenas continuar o trabalho, abra `source/`. Para reconstruir um repositório com histórico,
clone `git/UStracker-r11-r23.bundle` e selecione a branch `codex/r11-r23`.

## 7. Regra de versão

`version.md` permanece `1.003`. `VERSION.json` e `current.json` são espelhos sincronizados.
A próxima promoção esperada é `1.004`, mas somente após implementação e verificação das pendências;
não aumente a versão apenas por abrir ou transferir o projeto.
