# R11 Core Operational Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the complete Client → Company → Vehicle/Fleet → Monthly Plan → Subscription → Payment → Finance → Overview chain through one authoritative domain operation.

**Architecture:** Preserve the FastAPI/SQLite and JavaScript-module architecture. Add an additive schema-9 target relation, centralize subscription validation/hydration in the backend, and expose one reusable frontend workflow from Client Profile and Commercial.

**Tech Stack:** Python 3.13, FastAPI, SQLite/SQLCipher, JavaScript ES modules, Node test runner, unittest, .NET/WebView2 host unchanged.

**Spec:** `docs/superpowers/specs/2026-10-02-r11-core-operational-flow-design.md`

## Global Constraints

- Preserve the approved visual and functional pattern; no broad redesign or framework rewrite.
- `version.md` is the only manually maintained product-code version and uses `N.NNN`.
- Money remains integer cents and UI remains pt-BR.
- Preserve authentication, audit, CSRF, operation idempotency, writer-station, portability, backup/recovery, and legacy routes.
- Migrations are additive and reentrant; active installation and `Data` are never edited.
- Every behavior change follows RED → GREEN and receives fresh focused plus broad evidence.
- No production deployment, installation, push, or data mutation.

## Review Focus

- A failed multi-target subscription must leave no subscription, item, target, or partial audit event.
- A fleet or vehicle from another client must be rejected even when IDs are syntactically valid.
- Retried API requests with the same operation ID must not create a second subscription or financial entry.
- Legacy schema-8 subscriptions without targets must remain readable after migration.
- A payment must affect realized Finance/Overview totals exactly once and a reversal must remove it.

---

### Task 1: Stabilize the Baseline Database Lifecycle

**Files:**
- Modify: `src/ustracker/auth.py`
- Modify: `tests/test_r2_routes.py`

**Interfaces:**
- Consumes: `AuthService._connect() -> sqlite3.Connection`
- Produces: a closing connection context used by every AuthStore operation

- [ ] **Step 1: Add a failing Windows cleanup regression test**

Add `test_auth_store_releases_database_after_request_lifecycle`, which creates an app in a temporary directory, performs authenticated requests, drops app references, runs collection, and asserts the directory can be removed immediately.

- [ ] **Step 2: Run the focused test and confirm RED**

Run with the bundled runtime and expect `PermissionError` for `UserData/Auth/auth.db`.

- [ ] **Step 3: Close AuthStore connections deterministically**

Add `AuthService._connection()` as a context manager that commits/rolls back through the connection context and always closes it. Replace direct `with self._connect()` usages with the owned context.

- [ ] **Step 4: Run focused and route regression tests**

Expect both cleanup and existing authenticated route tests to pass without `ResourceWarning`.

- [ ] **Step 5: Commit**

Commit message: `fix: close auth database connections deterministically`

### Task 2: Establish Canonical Product Versioning

**Files:**
- Create: `version.md`
- Create: `src/ustracker/versioning.py`
- Create: `tools/sync_version.py`
- Modify: `src/ustracker/__init__.py`
- Modify: `src/ustracker/server.py`
- Modify: `tools/package.ps1`
- Modify: `tools/generate_sbom.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_r01_foundation.py`

**Interfaces:**
- Produces: `read_version(path: Path) -> str`, `sync_version(repo_root: Path) -> dict`
- Consumes: exact `N.NNN` text from source-root `version.md`

- [ ] **Step 1: Write failing version-authority tests**

Assert valid `1.001` parsing, invalid-format rejection, generated JSON/package metadata consistency, and health response version sourcing from the root file.

- [ ] **Step 2: Run tests and confirm RED because `version.md`/versioning do not exist**

- [ ] **Step 3: Implement parser and deterministic metadata synchronization**

The synchronization tool updates compatibility metadata from `version.md`; no generated file becomes independently authoritative. Packaging calls synchronization before reading metadata and copies `version.md` into the candidate root.

- [ ] **Step 4: Run focused tests and static scans for independent hardcoded product versions**

- [ ] **Step 5: Commit**

Commit message: `build: make version.md the product version authority`

### Task 3: Add Schema-9 Subscription Targets

**Files:**
- Modify: `src/ustracker/db.py`
- Create: `tests/test_r11_migration.py`

**Interfaces:**
- Produces: `subscription_targets(id, subscription_id, vehicle_id, fleet_id, created_at)`
- Preserves: schema-8 subscriptions and all existing tables

- [ ] **Step 1: Write failing schema-8→9 migration tests**

Assert table creation, exactly-one-target constraint, per-subscription uniqueness, cascade deletion, reentrant reopen, and legacy subscription readability.

- [ ] **Step 2: Run migration tests and confirm RED on missing schema 9**

- [ ] **Step 3: Implement additive migration and schema declaration**

Set `SCHEMA_VERSION = 9`; create the target table and indexes in both fresh schema and `current_version < 9` migration.

- [ ] **Step 4: Run focused migration tests twice against the same database**

- [ ] **Step 5: Commit**

Commit message: `feat: add subscription mobility targets`

### Task 4: Harden the Subscription Domain Operation

**Files:**
- Modify: `src/ustracker/services.py`
- Create: `tests/test_r11_subscription_domain.py`

**Interfaces:**
- Consumes: legacy `create_subscription(db, actor, payload)` callers
- Produces: hydrated subscription with `items`, `targets`, and `effective_total_cents`

- [ ] **Step 1: Write failing domain tests**

Cover client-context creation, active-monthly-only catalog, vehicle target, fleet target, mixed targets, duplicates, cross-client rejection, invalid fleet-company relation, rollback, price snapshot, and one audit event.

- [ ] **Step 2: Run the domain file and confirm each missing rule fails for the intended reason**

- [ ] **Step 3: Implement validation helpers and one transactional write**

Keep `create_subscription` as the compatibility entry point. Items describe commercial value; targets describe mobility and never multiply value.

- [ ] **Step 4: Add and test subscription hydration/listing helpers**

Expose plans, vehicles, fleets, client/company names, and effective total through backend read models.

- [ ] **Step 5: Run focused tests and existing backend tests**

- [ ] **Step 6: Commit**

Commit message: `feat: centralize validated subscription creation`

### Task 5: Prove API Idempotency and Financial Propagation

**Files:**
- Modify: `src/ustracker/server.py`
- Modify: `src/ustracker/commercial.py`
- Create: `tests/test_r11_routes.py`
- Create: `tests/test_r11_financial_flow.py`

**Interfaces:**
- Preserves: `POST /api/v1/subscriptions`
- Produces: hydrated `GET /api/v1/subscriptions` and Commercial read model

- [ ] **Step 1: Write failing API contract tests**

Exercise both context payloads through the same endpoint, unauthorized access, operation-ID replay, conflicting replay, and legacy payload compatibility.

- [ ] **Step 2: Write failing end-to-end financial tests**

Create client/company/vehicle-or-fleet/plan/subscription/charge/payment and assert Finance plus Overview reflect the payment once; reverse it and assert removal.

- [ ] **Step 3: Run focused tests and confirm RED**

- [ ] **Step 4: Implement hydrated route/read-model behavior without a second write path**

- [ ] **Step 5: Run focused API and financial suites GREEN**

- [ ] **Step 6: Commit**

Commit message: `feat: connect subscriptions to financial read models`

### Task 6: Build the Reusable Subscription Workflow UI

**Files:**
- Create: `frontend/ui/subscription-workflow.js`
- Modify: `frontend/ui/r2-ui.js`
- Modify: `frontend/pages/commercial.js`
- Modify: `frontend/app.js`
- Modify: `frontend/ui/help-catalog.js`
- Create: `tests/r11_subscription_workflow.test.mjs`

**Interfaces:**
- Produces: `renderSubscriptionWorkflow(model)`, `buildSubscriptionPayload(form, selections)`, and binding callbacks
- Consumes: hydrated clients, active monthly plans, client vehicles/fleets

- [ ] **Step 1: Write failing renderer/payload tests**

Assert Client Profile locks the current client, Commercial permits client-first selection, non-monthly plans are absent, target lists filter by client, duplicate selections are rejected, and payloads are identical apart from context.

- [ ] **Step 2: Run Node test and confirm RED on missing module**

- [ ] **Step 3: Implement the reusable drawer workflow with existing components/tokens**

- [ ] **Step 4: Wire Client Profile and Commercial to the same workflow and endpoint**

Successful actions close the drawer, show a toast, and refresh only the affected view; errors preserve the form and show feedback.

- [ ] **Step 5: Run focused UI tests and all Node tests**

- [ ] **Step 6: Commit**

Commit message: `feat: reuse subscription workflow across client and commercial`

### Task 7: Expose Subscription Relations in Mobility and Profiles

**Files:**
- Modify: `src/ustracker/mobility.py`
- Modify: `src/ustracker/services.py`
- Modify: `frontend/pages/mobility.js`
- Modify: `frontend/ui/r2-ui.js`
- Modify: `tests/test_r11_subscription_domain.py`
- Modify: `tests/r11_subscription_workflow.test.mjs`

**Interfaces:**
- Produces: vehicle/fleet/profile read models with current subscription summaries

- [ ] **Step 1: Write failing read-model and rendering tests**

Assert a vehicle and fleet show client, company, active subscription, plan, effective value, and start date without frontend joins.

- [ ] **Step 2: Run tests and confirm RED on missing relations**

- [ ] **Step 3: Implement backend projections and conservative UI presentation**

- [ ] **Step 4: Run focused Python/Node tests GREEN**

- [ ] **Step 5: Commit**

Commit message: `feat: expose subscription relations in mobility views`

### Task 8: R11 Gate, Version Promotion, and Evidence

**Files:**
- Modify: `version.md`
- Modify: generated compatibility metadata through `tools/sync_version.py`
- Modify: `docs/handoff/2026-10-02-codex-r11-r23/04_EXECUTION_LEDGER.md`
- Modify: `docs/handoff/2026-10-02-codex-r11-r23/05_ACCEPTANCE_MATRIX.csv`
- Create: `engineering/reports/R11-core-operational-flow/README.md`

**Interfaces:**
- Produces: R11 checkpoint at product version `1.002`, schema 9

- [ ] **Step 1: Run formatting/static checks and focused suites**

Run Python compile, JavaScript checks, migration, domain, route, financial, and UI suites.

- [ ] **Step 2: Run the complete Python and Node regressions**

Record exact commands, exit codes, skips, warnings, and environment limitations.

- [ ] **Step 3: Inspect diff for scope, secrets, paths, data risk, and compatibility**

- [ ] **Step 4: Promote `version.md` from `1.001` to `1.002` and synchronize generated metadata**

- [ ] **Step 5: Update ledger, acceptance matrix, and R11 evidence report**

- [ ] **Step 6: Commit the verified checkpoint**

Commit message: `chore: checkpoint verified R11 flow`

- [ ] **Step 7: Do not install or promote the candidate**

Package/build validation may produce a candidate only if local dependencies are available; physical Windows smoke and production promotion remain unverified and unauthorized.
