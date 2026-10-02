# R11 Core Operational Flow — Verification Evidence

Date: 2026-10-02  
Source checkpoint: product version `1.002`, database schema `9`  
Implementation range: `4efbafd..be1373f`, followed by this checkpoint commit

## Delivered behavior

- `version.md` is the only manually maintained product-code version source; compatibility JSON and package/runtime consumers derive from it.
- Schema 9 adds additive, reentrant subscription targets for vehicles and fleets while preserving schema-8 records.
- `create_subscription` is the single validated transaction for Client Profile, Commercial, and legacy callers.
- Subscription reads are hydrated with client/company, plan items, targets, and effective total without multiplying value by targets.
- One reusable drawer supports Client Profile and Commercial; it filters active monthly plans and client mobility, includes immediate client-name filtering, retains errors in place, and refreshes the affected view after success.
- Charges and non-reversed payments remain the financial authority. Finance, Commercial, Dashboard, and Overview reconcile without a duplicate revenue write; reversal removes realized value while retaining history.
- Mobility and profile projections expose active subscription summaries, including legacy item-level vehicle relations.

## Fresh verification

All commands ran from `C:\UStracker\Development\r11-r23` with the bundled supported Python runtime at `C:\UStracker\System\Runtime\python.exe`.

| Check | Result |
|---|---|
| `python -m compileall -q src tests` | PASS |
| `node --check` for every `frontend/**/*.js` file | PASS |
| `test_r11_migration.py` | PASS — 2/2 |
| `test_r11_subscription_domain.py` | PASS — 5/5 |
| `test_r11_routes.py` | PASS — 2/2 |
| `test_r11_financial_flow.py` | PASS — 1/1 |
| `node --test tests/r11_subscription_workflow.test.mjs` | PASS — 5/5 |
| `python -m unittest discover -s tests -p 'test_*.py' -v` with `ResourceWarning` as error | PASS — 30/30, zero skips, zero warnings |
| `node --test tests/*.test.mjs` | PASS — 24/24 |
| Version sync after `version.md=1.002` | PASS — `VERSION.json` and `current.json` both `1.002`, schema `9` |
| Production absolute-path scan | PASS — zero matches |
| Likely embedded-secret scan | PASS after review — one match was the literal UI label `Senha ou PIN`, not a credential |

## Environment limitation

`dotnet build host\Bootstrap\Bootstrap.csproj -c Release -p:Platform=x64 --no-restore` could not start compilation because the machine lacks the .NET Framework 4.8 reference assemblies (`MSB3644`). The installed CLI is .NET SDK `10.0.400`. No dependency was installed automatically.

Therefore package creation, WebView2 startup, shortcut behavior, updater physical smoke, and Windows production installation remain explicitly unverified. No candidate was installed or promoted, and no real `Data` directory was read or mutated.

## Risk and compatibility review

- Changes are confined to source, tests, generated compatibility metadata, and evidence documents in the isolated worktree.
- Migration is additive and reentrant; it performs no forced backfill and keeps legacy subscriptions readable.
- API route `POST /api/v1/subscriptions` and legacy item `vehicle_id` remain compatible.
- Operation-ID replay returns the original response; conflicting input is rejected.
- The source diff contains no production dependency on `C:\UStracker` and no embedded credential.
