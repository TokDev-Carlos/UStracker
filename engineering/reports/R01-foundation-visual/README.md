# R01 — Verificação source-ready

Estado: **SOURCE_READY_AWAITING_WINDOWS**. Este registro não marca o changeset como VERIFIED e não autoriza promoção para candidate.

## Identidade

- Base: `aff64d0ac32225b588119fe76a81aac1442156da`
- Commit de implementação: `1599676beccd4d4b11b97f513f903aa99bd12ec8`
- Schema: `3 → 3` (sem migração)
- Checkpoint: `engineering/checkpoints/R01-source-ready.json`

## Evidência disponível

- Node R01 + regressão R2: **19/19 PASS**.
- `node --check frontend/app.js`: **PASS**.
- Testes Python focados R01: **3/3 PASS**.
- `compileall`: **PASS**.
- Guard de caminhos: **PASS**, sem superfície sensível alterada.
- Preflight pós-commit: **PASS**, árvore limpa.
- Candidate gate: **BLOQUEADO COMO ESPERADO** por `changeset-not-verified:IN_PROGRESS`.
- Suite Python completa: **13 PASS / 1 ERROR ambiental**, exclusivamente `ModuleNotFoundError: sqlcipher3` no teste legado de migração.

## Revisão

A revisão do diff encontrou uma regressão de responsividade causada pela ordem das novas regras CSS. Foi criado teste de regressão, observado RED e corrigido até GREEN; a suíte focada R01 passou 11/11 após a correção.

## Gates ainda obrigatórios no Windows

1. Build Bootstrap .NET Framework 4.8 x64.
2. Build Shell .NET Framework 4.8 x64.
3. Smoke de primeira e segunda inicialização: exatamente um `UStracker.lnk`, target correto e ícones visíveis.
4. Homologação visual no ambiente **Teste**.
5. Suite Python completa com `sqlcipher3` disponível.

Até esses gates passarem, R01 permanece `IN_PROGRESS`; R02 não deve iniciar.

## Efeitos externos

Nenhuma modificação no Supabase remoto, nenhuma instalação ativa alterada, nenhum push, deploy ou release executado.
