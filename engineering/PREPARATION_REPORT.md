# UStracker — Relatório de preparação do ambiente de engenharia

Data de referência: 2026-09-28.

## Estado

**PREPARED_AWAITING_USER_CONFIRMATION**. O plano funcional R01–R10 não foi iniciado.

## Integridade e isolamento

- Handoff recebido: SHA-256 `677097E1C002CF7C2C6FAB8AB18C7B6CCF2420AAC305D2365F193C84E4E4A1C3`.
- Baseline Git: tag `baseline/1.00.01.000-schema3`, commit `f6fafde4f4abc8a8484239fa86fc3c031497d422`.
- Head de engenharia verificado: `d1b902a532ec94ba3bd24ffa43bb339b5de63d40` antes da inclusão deste relatório.
- Arquivos funcionais do produto alterados em relação à baseline: **0**.
- `APPROVAL.json:user_approved_execution`: **false**.
- `EXECUTION_STATE.functional_plan_started`: **false**.
- Candidate gate de R01 foi executado propositalmente sem aprovação e retornou FAIL, como esperado, por `execution-not-approved-by-user`, `changeset-not-verified:PREPARED` e ausência de `base_commit`.

## Verificação executada neste ambiente

| Check | Resultado |
|---|---|
| Guard preflight | PASS |
| Testes da infraestrutura | 14/14 PASS |
| `git diff --check` | PASS |
| `git fsck --full` | PASS |
| Node UI baseline | 8/8 PASS |
| `node --check frontend/app.js` | PASS |
| `python -m compileall -q src/ustracker tests` | PASS |
| Python baseline | 10 PASS / 1 ERROR ambiental |
| .NET builds | NÃO EXECUTADOS — `dotnet` indisponível neste ambiente |
| PowerShell runtime/parse | NÃO EXECUTADO — PowerShell indisponível neste ambiente |

### Limitação do teste Python

O teste `test_schema3_alters_actual_legacy_table_without_billing_cycle` exige `sqlcipher3`. O módulo não está instalado neste ambiente de análise, portanto o erro observado foi `ModuleNotFoundError: No module named 'sqlcipher3'`. Os outros 10 testes passaram. Também foram observados `ResourceWarning` de conexões SQLite já conhecidos na baseline; não foram corrigidos porque esta etapa não altera comportamento do produto.

## Supabase

O ambiente conectado já contém estruturas de outro sistema. Nenhuma migração, tabela ou branch do UStracker foi criada remotamente. Foi preparado somente `engineering/supabase/migrations/0001_engineering_registry.sql`, usando schema privado `ustracker_eng`, sem `public`, sem acesso `anon/authenticated` e sem dados pessoais.

## Gates preparados

- baseline tag + snapshot SHA-256 por arquivo;
- bloqueio de arquivos sensíveis e chaves privadas;
- worktree por changeset;
- escopo de paths permitido/sensível por R01–R10;
- limite de uma versão de schema por incremento;
- TDD e regressão obrigatórios;
- checkpoint reproduzível;
- candidate gate;
- empacotamento sem instalação automática;
- contrato de rollback/recovery preservando o updater existente.

## Próximo gate

Antes de R01, executar no Windows alvo `engineering/tools/Invoke-Preflight.ps1` e `engineering/tools/Verify-Baseline.ps1`. A criação do primeiro worktree continua bloqueada até confirmação explícita do usuário.
