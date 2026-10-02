# R12 Bounded Entity Search Implementation Plan

> Execute with TDD and fresh verification evidence for each task.

**Goal:** Provide one bounded, accent/case-insensitive client autocomplete for every active client selector without changing mutation payloads or visual conventions.

**Architecture:** Register a folded-text SQL function, expose a bounded authenticated client-entity endpoint, build a headless/testable autocomplete controller plus renderer/binder, then replace unbounded form selectors by context.

---

### Task 1: Add the bounded client search service

**Files:** `src/ustracker/db.py`, `src/ustracker/services.py`, `tests/test_r12_client_search.py`

- [ ] Write RED tests with 1005 clients covering name, accent/case, document, company, phone, empty query, ordering, default/capped limits.
- [ ] Register deterministic `fold_text` per connection and implement `search_client_entities` with backend bounding.
- [ ] Run focused and backend regression tests.
- [ ] Commit: `feat: add bounded folded client search`

### Task 2: Expose the authenticated API contract

**Files:** `src/ustracker/server.py`, `tests/test_r12_routes.py`

- [ ] Write RED route tests for authentication, empty query, result shape, limit cap, and accent/case queries.
- [ ] Add `GET /api/v1/entities/clients` without changing legacy routes.
- [ ] Run focused route tests.
- [ ] Commit: `feat: expose client entity search API`

### Task 3: Build the reusable autocomplete component

**Files:** `frontend/ui/entity-autocomplete.js`, `tests/r12_entity_autocomplete.test.mjs`

- [ ] Write RED tests for 1000+ source records without 1000 DOM options, 200 ms debounce, incremental narrowing, keyboard selection/escape, clear, stale response protection, and API error state.
- [ ] Implement pure state/controller functions plus existing-token markup and DOM binding.
- [ ] Run focused Node tests and JavaScript syntax checks.
- [ ] Commit: `feat: add reusable entity autocomplete`

### Task 4: Integrate Commercial, subscription, and Finance workflows

**Files:** `frontend/ui/subscription-workflow.js`, `frontend/pages/commercial.js`, `frontend/pages/finance.js`, `frontend/app.js`, relevant Node tests

- [ ] Write RED integration/static tests proving forms no longer materialize client option lists.
- [ ] Bind autocomplete to subscription, direct purchase, and payment forms; keep `client_id` payloads and dependent vehicle/charge filtering.
- [ ] Run focused and all Node tests.
- [ ] Commit: `feat: use client autocomplete in commercial and finance`

### Task 5: Integrate Mobility and remaining active selectors

**Files:** `frontend/pages/mobility.js`, `frontend/app.js`, relevant Node tests

- [ ] Write RED tests for vehicle/fleet creation, mobility filter, and transfer client selection.
- [ ] Replace remaining editable unbounded client selectors and preserve company/fleet dependent loading.
- [ ] Static-scan active frontend workflows for unbounded `client_id` selects.
- [ ] Commit: `feat: use client autocomplete across mobility`

### Task 6: R12 gate and version promotion

**Files:** `version.md`, generated metadata, execution ledger, acceptance matrix, `engineering/reports/R12-bounded-entity-search/README.md`

- [ ] Run compile/static checks, focused suites, full Python and Node regression.
- [ ] Review scope, secrets, paths, payload compatibility, and bounded result behavior.
- [ ] Promote `version.md` from `1.002` to `1.003` and synchronize metadata.
- [ ] Record exact evidence and environment limitations; do not install/promote.
- [ ] Commit: `chore: checkpoint verified R12 search`
