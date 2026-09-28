# DEC-001 — Autoridade de versão de schema

**Decisão:** a baseline válida é schema 3.

**Evidência canônica:** `VERSION.json`, `HANDOFF_METADATA.json` e `src/ustracker/db.py` registram schema 3. O plano incremental também parte de schema 3 e prevê evolução até schema 8.

**Conflito conhecido:** `CODEX_EXECUCAO.md` contém instruções históricas que tratam schema 2 → 3. Esse documento é referência histórica para R2 e não deve controlar a nova reestruturação.

**Regra:** nenhuma migração futura pode reduzir schema, repetir 2 → 3 ou marcar uma versão como concluída fora da transação da migração.
