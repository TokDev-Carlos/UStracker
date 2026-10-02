# EXECUTION CONTRACT — UStracker R11..R23

MODE: IMPLEMENTATION
STYLE: MACHINE/ENGINEERING
BASELINE: `source/`, branch `handoff/schema8-r10v2`, schema target/current = 8.

## 0. Preconditions

- Create isolated branch/worktree from baseline HEAD.
- Inspect `git status`, current schema constants, migrations, server routes, frontend router, icon registry, updater, RootPaths, backup/recovery.
- Run available baseline tests before production edits.
- Record all pre-existing failures. Never silently classify a failure as unrelated.
- Do not modify `artifacts/`.

## 1. Invariants

INV-001 Portability: application root is dynamic. Product must run from arbitrary writable folder/drive.
INV-002 No business logic duplication in frontend. Backend/domain owns calculations and state transitions.
INV-003 Money stored as integer cents; UI pt-BR.
INV-004 Existing authentication/audit/CSRF/idempotency/writer-station rules remain intact.
INV-005 Migrations are additive/reentrant. No destructive DROP without explicit approved migration/recovery plan.
INV-006 User-visible mutation updates UI without manual browser/application refresh.
INV-007 No selector loads unbounded client list. Use server/filter/autocomplete pattern.
INV-008 One user action = one operation. File/photo upload must not require a separate “select” then “send” button sequence.
INV-009 Icons are consistent, non-emoji, mapped through registry/assets.
INV-010 Approved visual identity is baseline. Refinement only; no broad redesign.
INV-011 Updater is versioned, integrity-checked, transactional, rollback-capable. No uncontrolled folder clones.
INV-012 Online data evolution uses repository/API abstraction. Never use a synchronised cloud-drive SQLite file as concurrent multi-client database.
INV-013 Preserve legacy routes/aliases until migration compatibility is proven.
INV-014 Every menu must support its declared job end-to-end.
INV-015 Every stage has RED→GREEN evidence and broad regression before checkpoint.

## 2. Engineering loop per stage

1. CHARACTERIZE current behavior.
2. TRACE source-of-truth and callers.
3. WRITE failing acceptance/regression tests.
4. RUN tests and confirm failure reason.
5. IMPLEMENT smallest coherent vertical slice.
6. RUN focused tests until GREEN.
7. RUN affected integration/API/frontend tests.
8. RUN broad regression.
9. REVIEW diff for scope/security/data/portability.
10. COMMIT one behavior/migration per commit.
11. UPDATE execution ledger and acceptance matrix.
12. DO NOT advance on Critical/Important unresolved failure.

## 3. Prohibited shortcuts

- No hardcoded machine/user path.
- No “temporary” duplicate business service.
- No frontend-only fix when backend contract is wrong.
- No tests changed merely to make a failing implementation green.
- No dummy real customer data injection.
- No production-data mutation for testing.
- No disabling audit/security checks to simplify development.
- No full framework rewrite.
- No uncontrolled polling/background writers.
- No claim of PASS without current command output.

## 4. Completion report format

For every Rxx stage report exactly:

- BASE_HEAD
- FINAL_HEAD
- CHANGED_FILES
- MIGRATION
- RED_TESTS
- GREEN_TESTS
- FULL_REGRESSION
- USER_VISIBLE_BEHAVIOR
- COMPATIBILITY
- PORTABILITY_IMPACT
- DATA_RISK
- UNVERIFIED_ITEMS
- NEXT_STAGE_GATE
