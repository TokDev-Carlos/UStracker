# R12 Bounded Entity Search — Verification Evidence

Date: 2026-10-02  
Source checkpoint: product version `1.003`, database schema `9`  
Implementation range: `d06e166..50d7ade`, followed by this checkpoint commit

## Delivered behavior

- Authenticated `GET /api/v1/entities/clients` searches active clients by normalized name, company, document, phone, and e-mail.
- Search is case- and accent-insensitive, returns no rows for an empty query, defaults to 20 rows, and caps every response at 30.
- The reusable autocomplete debounces by 200 ms, rejects stale responses, exposes loading/error/empty states, supports ArrowUp/ArrowDown/Enter/Escape, and clears both visible and identifier state.
- Subscription, direct purchase, payment, mobility filter, vehicle creation, fleet creation, and vehicle transfer use the same bounded client-search component.
- Vehicles, charges, companies, and fleets remain dependent on the selected client. Fleet lookup is authenticated, client-filtered, and capped at 100.
- Commercial and Finance snapshots no longer transfer an unbounded client list.

## Fresh verification

All commands ran from `C:\UStracker\Development\r11-r23` with the bundled supported Python runtime at `C:\UStracker\System\Runtime\python.exe`.

| Check | Result |
|---|---|
| `python -m compileall -q src tests` | PASS |
| `node --check` for every `frontend/**/*.js` file | PASS |
| `test_r12_client_search.py` | PASS — 2/2 with 1,005-record fixture |
| `test_r12_routes.py` | PASS — 3/3, including authenticated caps |
| `r12_entity_autocomplete.test.mjs` | PASS — 4/4 |
| `r12_workflow_integration.test.mjs` | PASS — 4/4 |
| `r12_mobility_autocomplete.test.mjs` | PASS — 3/3 |
| Full Python regression with `ResourceWarning` as error | PASS — 35/35, zero skips, zero warnings |
| Full Node regression | PASS — 35/35 |
| Engineering guard/structure regression | PASS — 14/14 |
| Version sync after `version.md=1.003` | PASS — `VERSION.json` and `current.json` both `1.003`, schema `9` |
| Production absolute-path scan | PASS — zero matches |
| Likely embedded-secret scan | PASS after review — the only match is the literal UI label `Senha ou PIN`, not a credential |

## Environment limitation

`dotnet build host\Bootstrap\Bootstrap.csproj -c Release -p:Platform=x64 --no-restore --nologo` again stopped before compilation with `MSB3644`: the machine has .NET SDK `10.0.400` but lacks the .NET Framework 4.8 reference assemblies. No dependency was installed automatically.

No package was built, installed, or promoted. The active installation and real `Data` directory were not read or mutated.

## Risk and compatibility review

- No schema migration was required; schema remains 9.
- Existing mutation payloads retain `client_id`, `fleet_id`, `vehicle_id`, and `charge_id` semantics.
- The existing `/fleets` read remains available but is now capped at 100; client-filtered consumers use `client_id` explicitly.
- Empty autocomplete input never falls back to a full client query or DOM option list.
- Changes are confined to source, tests, generated compatibility metadata, and evidence documents in the isolated worktree.
