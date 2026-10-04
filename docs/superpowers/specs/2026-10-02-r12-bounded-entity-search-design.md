# R12 Bounded Entity Search Design

## Intent

Replace unbounded client selectors in active workflows with one reusable, keyboard-accessible autocomplete backed by a bounded authenticated API. Preserve the current visual language and existing mutation payloads.

## Backend contract

`GET /api/v1/entities/clients?q=<text>&limit=<n>` requires an authenticated session. Empty input returns no rows. The limit defaults to 20 and is capped at 30. Results contain only selector-safe fields (`id`, display name, document, company, phone/email) and match folded name, active document, active company, or phone data case- and accent-insensitively.

The database connection registers a deterministic `fold_text` SQL function so filtering and bounding occur before results leave the backend. Existing `/clients` and `/search` routes remain compatible.

## Frontend contract

`EntityAutocomplete` is a reusable component with:

- a text input, hidden selected ID, bounded result list, clear action, loading and error states;
- 200 ms debounce;
- request sequence/cancellation protection so a stale response cannot replace newer results;
- ArrowUp/ArrowDown/Enter/Escape keyboard behavior;
- no results rendered for empty input;
- callback when selection or clearing changes dependent state.

Client Profile may keep a locked hidden client ID. Commercial subscription, direct purchase, payment, mobility creation/filter/transfer, and any other active editable client selector use the reusable search component. Payload field names remain `client_id`.

## Compatibility and risk

No schema migration is required. Client listing remains available for tables, but forms stop loading it solely to populate selectors. Backend results are bounded to 30. Search errors remain local to the form and do not erase a valid prior selection.

R12 promotes `version.md` from `1.002` to `1.003` only after focused and broad gates pass. Package installation and production promotion remain outside scope.
