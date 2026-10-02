# R13 Runtime Action State Implementation Plan

## Task 1: Headless action runner and mutation coalescing

**Files:** `frontend/ui/action-state.js`, `frontend/ui/api.js`, Node tests

- Write RED tests for state order, double-submit deduplication, errors, and stale responses.
- Implement keyed action runner and identical concurrent mutation coalescing.
- Run focused and full Node regression.
- Commit: `feat: add deterministic action state runner`

## Task 2: Bind Clients and Mobility

**Files:** `frontend/app.js`, Node integration tests

- Write RED static/integration coverage for create/edit/archive/upload/transfer flows.
- Replace active handlers with shared form/button actions and explicit refresh callbacks.
- Verify failure leaves the current surface intact.
- Commit: `feat: synchronize client and mobility actions`

## Task 3: Bind remaining active menus and protect navigation

**Files:** `frontend/app.js`, `frontend/ui/action-state.js`, Node tests

- Integrate Catalog, Commercial, Finance, Files, and System mutations.
- Add latest-only navigation protection.
- Static-scan active mutation handlers and run menu-by-menu contract tests.
- Commit: `feat: synchronize remaining runtime actions`

## Task 4: R13 gate and version promotion

**Files:** `version.md`, generated metadata, execution ledger, acceptance matrix, `engineering/reports/R13-runtime-action-state/README.md`

- Run focused suites, full regressions, syntax/compile checks, and scope/security review.
- Promote `version.md` from `1.003` to `1.004` and synchronize metadata.
- Record exact evidence and environment limitations; do not package, install, or promote.
- Commit: `chore: checkpoint verified R13 actions`
