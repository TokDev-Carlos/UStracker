# SDD ledger — plan: docs/handoff/2026-09-28-ustracker-reestruturacao-incremental.md

Preparation: canonical handoff materialized into Git; baseline tag created; engineering controls are being added in a separate commit.
Ruling: schema authority is 3, not the historical schema 2 text in CODEX_EXECUCAO.md — supported by VERSION.json, HANDOFF_METADATA.json, db.py and the incremental plan — cost if wrong: migration sequence would need to be re-derived before any database write.
Gate: functional Tasks 1-10 are not started. User confirmation is required after preparation verification.

Task 1: started in feature/R01-foundation-visual from aff64d0ac32225b588119fe76a81aac1442156da using changeset R01-foundation-visual.
Task 1: Ruling: the initial shortcut test expected a new RootPaths.BootstrapExecutable member outside the R01 allowed paths; keep host/Shared untouched and resolve the launcher as Path.Combine(RootPaths.ProductRoot, "UStracker.exe") inside Bootstrap — preserves scope — cost if wrong: one localized path helper adjustment.
Task 1: Ruling: r2_ui.test.mjs encoded Intl's non-breaking-space output; R01 defines canonical textual BRL as "R$ 0,00", so update the expectation to ordinary space — required by the accepted format contract — cost if wrong: visual whitespace only, not cents or stored values.
Task 1: Final review finding fixed: R01 shell rules overrode the legacy <=800px responsive layout; added a regression test that failed first, then restored explicit narrow-screen grid/sidebar behavior — RED→GREEN 11/11 focused R01 tests.
Task 1: source-ready at 1599676beccd4d4b11b97f513f903aa99bd12ec8. Available verification: Node 19/19 PASS; focused Python 3/3 PASS; compileall PASS; path policy PASS; clean preflight PASS. Full Python suite is 13 PASS / 1 environmental ERROR because sqlcipher3 is unavailable. .NET builds, Windows shortcut/icon smoke and visual Test homologation are NOT RUN here. Changeset remains IN_PROGRESS; candidate gate correctly blocks promotion.
Task 1: PONTO-DE-PARADA-1-SOURCE-READY recorded. R02 must not start until Windows gates and visual Test homologation are approved.
