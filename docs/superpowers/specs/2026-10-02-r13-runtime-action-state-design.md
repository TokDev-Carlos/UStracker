# R13 Runtime Action State Design

## Goal

Every active mutation has one visible lifecycle: `IDLE → LOADING → SUCCESS|ERROR → IDLE`. A repeated activation while loading reuses the in-flight result, successful actions refresh their owning surface, and failed actions keep the current DOM/data visible while showing a Portuguese error.

## Design

Create a reusable `action-state` module with two layers:

1. A headless keyed runner owns in-flight deduplication, state transitions, and latest-response sequencing. It is deterministic under Node tests.
2. DOM helpers bind forms and buttons to the runner. They disable all submit controls in the action scope, set `aria-busy`, restore controls in `finally`, show unified toast feedback, and call an explicit refresh callback only after success.

The API client also coalesces identical concurrent mutations. This is defense in depth for any legacy handler not yet migrated and reuses one operation ID/request rather than issuing a second write.

Page refresh remains explicit: Client Profile refreshes its drawer, menu pages rerun their page loader, and overlays close only after successful mutation. A rejected mutation never clears or rerenders the prior surface.

For read races, a latest-only loader token is applied at the page navigation boundary so a slower response from an older navigation cannot overwrite a newer page.

## Scope

- Active create/edit/archive/upload/transfer/payment/fiscal/file flows in Clients, Mobility, Catalog, Commercial, Finance, Files, and System.
- Existing server idempotency and operation IDs remain unchanged.
- No database migration and no visual redesign.
- `version.md` advances from `1.003` to `1.004` only after the R13 gate passes.

## Verification

- Headless tests: double activation writes once; state order; error preservation; latest-response protection.
- Integration/static tests: active mutation handlers use the shared primitive and declare refresh ownership.
- Full Python/Node regression, syntax/compile checks, path/secret review, and evidence update.
