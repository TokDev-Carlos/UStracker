# SDD ledger — plan: docs/handoff/2026-09-28-ustracker-reestruturacao-incremental.md

Preparation: canonical handoff materialized into Git; baseline tag created; engineering controls are being added in a separate commit.
Ruling: schema authority is 3, not the historical schema 2 text in CODEX_EXECUCAO.md — supported by VERSION.json, HANDOFF_METADATA.json, db.py and the incremental plan — cost if wrong: migration sequence would need to be re-derived before any database write.
Gate: functional Tasks 1-10 are not started. User confirmation is required after preparation verification.
