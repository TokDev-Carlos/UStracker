# UStracker Public Release Sanitization Design

## Goal
Publish UStracker 1.00.01.000 from the functional package as a reproducible GitHub Release, while ensuring no operational credentials, user databases, workstation identity, browser profile, cache, or other local state is shipped.

## Source of truth
The functional portable ZIP produced/used on 2026-09-15 is the behavioral source for Python application code, frontend assets, and packaged documentation. The GitHub `main` branch remains the source for build/release tooling and native host source unless the portable package proves a source-level difference.

## Release boundary
Only source code, static frontend assets, public update verification key, documentation, dependency manifests, and build scripts belong in Git. `UserData` is runtime state. A release package may contain the empty `UserData/` directory but no file beneath it.

## Sanitization
The release gate must reject every non-directory member beneath `UserData/`, regardless of file extension. The public source and packaged text are scanned for credential/token prefixes, private-key material, e-mail literals, workstation names, and absolute user-profile paths. Test-only fictitious credentials remain permitted in tests.

## Functional preservation
Sync the package's `ustracker` Python modules and complete frontend tree to the preparation branch. Do not copy Runtime binaries, local databases, vaults, station state, WebView profile/cache, logs, compiled caches, or executed-install artifacts. Run Python syntax/tests, JS syntax/tests, package/release gate, and portable smoke in CI before promotion.

## Git workflow
Work only on `release/sanitize-1.00.01.000` until verification succeeds. Merge to `main` after review/CI. GitHub Release publication remains manually gated by the existing `workflow_dispatch` confirmation and must use the clean CI-built ZIP, never the uploaded executed-install ZIP.

## Historical metadata
Existing public commit metadata is not rewritten as part of this release because rewriting all public refs is destructive and does not retract already exposed metadata. New release content must not add operational personal data.
