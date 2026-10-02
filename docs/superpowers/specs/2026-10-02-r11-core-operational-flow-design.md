# R11 Core Operational Flow Design

## Intent

Deliver one coherent operational chain from client registration through company, vehicle or fleet, monthly plan, subscription, payment, Finance, and Overview. Preserve the approved visual language and all existing authentication, audit, CSRF, idempotency, writer-station, portability, backup, and compatibility behavior.

## Scope

R11 is the first implementation increment. It includes the minimum supporting work required to make its acceptance gate reliable:

- establish `version.md` as the manually maintained product-code version authority;
- characterize and resolve the baseline database-handle cleanup failure before product changes;
- create subscriptions from Client Profile or Commercial through one backend operation;
- persist explicit vehicle and fleet subscription targets;
- restrict new subscription catalog selections to active monthly plans;
- propagate realized payments to Finance and Overview through the existing financial ledger, without duplicate revenue writes;
- refresh affected UI state after successful operations without a manual page reload;
- retain legacy routes and records.

R12-R23 remain separate increments and are not pulled into R11 except for small reusable seams that R11 directly requires.

## Version Authority

The source root contains `version.md` in the exact `N.NNN` format. The current development value is `1.001`. Runtime metadata needed for compatibility may still exist, but it must be generated or validated from `version.md`; it is not independently authored. R11 promotes the value to `1.002` only after its acceptance gate is green.

Database schema versions remain separate compatibility metadata. They do not represent the product-code version.

## Data Model

Schema 9 adds `subscription_targets` as an additive, reentrant migration:

- `id` primary key;
- `subscription_id` required foreign key with cascade deletion;
- exactly one of `vehicle_id` or `fleet_id` is populated;
- target rows are unique within a subscription;
- `created_at` records when the target relation was established.

Commercial line items remain in `subscription_items`. This keeps plan, quantity, and effective price separate from mobility scope, avoids multiplying financial value when multiple targets are selected, and preserves a stable fleet relationship if its vehicle membership changes later.

Legacy subscriptions without target rows remain readable and valid. No destructive migration or forced backfill is performed.

## Domain Operation

`create_subscription` remains the compatibility entry point and becomes the sole authoritative operation for both UI flows. It validates before writing:

- client exists, is not archived, and is eligible for a new subscription;
- at least one active catalog plan in category `MENSAL` is supplied;
- every target vehicle or fleet exists, is active, belongs to the same client, and is not duplicated;
- a fleet is linked to a company belonging to the same client;
- start date, due day, quantities, and prices are valid;
- effective unit prices are copied from the catalog unless a permitted explicit value is supplied;
- one transaction writes the subscription, items, targets, and one audit event.

The existing operation-ID wrapper provides retry idempotency at the API boundary. Reusing an operation ID with the same payload returns the prior result; reusing it with different input remains an error.

## API and Read Models

`POST /api/v1/subscriptions` remains the single creation endpoint. Its payload accepts `target_vehicle_ids` and `target_fleet_ids` while retaining legacy item payload compatibility.

Subscription list/profile responses expose hydrated plans and targets so the Client Profile, Commercial, Mobility, Finance, and Overview screens do not reproduce relationship logic in JavaScript.

Existing endpoints and aliases remain available. No new endpoint duplicates subscription creation.

## User Experience

Both entry points use one reusable subscription drawer/form:

- Client Profile opens `Nova Assinatura` with the current client preselected and locked.
- Commercial opens the same workflow with client selection first.
- Only active monthly plans are shown.
- Vehicle and fleet choices are filtered by the selected client.
- Loading, success, and failure states use existing buttons, drawer, toast, tokens, icons, spacing, and typography.
- A successful create closes the drawer, shows feedback, and refreshes only the affected profile or Commercial state.
- A successful payment refreshes Finance data and causes subsequent Overview reads to reflect realized revenue; no second revenue record is written.

No broad visual redesign, framework change, or unbounded selector is introduced.

## Financial Semantics

Subscription creation does not create revenue. Charges represent amounts due. Payments that are not reversed represent realized subscription revenue. Paid direct sales remain realized purchase revenue. Overview derives values from these ledgers and never from a duplicated summary write.

The effective subscription amount is the sum of `subscription_items.quantity * unit_price_cents`. Targets do not multiply that amount.

## Failure Handling and Compatibility

All validation occurs before the transaction commits. Cross-client mobility, inactive or non-monthly catalog entries, invalid dates, invalid values, and duplicate targets return validation errors without partial writes.

Legacy subscriptions, routes, billing-cycle fields, and schema-8 data remain readable. Migration 9 only creates the new relation table and indexes. Backup/restore continues to include the database as a whole.

## Verification

R11 requires fresh RED-to-GREEN evidence for:

- client-context and commercial-context creation using the same domain operation;
- monthly-only plan validation;
- vehicle and fleet targets;
- cross-client rejection and transaction rollback;
- operation-ID idempotency and audit event creation;
- realized payment propagation without double counting;
- UI client locking, target filtering, feedback, and no-F5 refresh;
- migration from schema 8 and legacy subscription readability;
- all existing Node and Python tests;
- source compilation/static checks and version metadata consistency.

Windows physical smoke and package promotion remain required before a production release. This design does not authorize deployment, installation, push, or production-data mutation.
