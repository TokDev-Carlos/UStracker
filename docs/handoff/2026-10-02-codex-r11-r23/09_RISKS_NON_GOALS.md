# RISKS / NON-GOALS

## High-risk surfaces
- subscription/payment double counting
- cross-client vehicle/fleet association
- schema migrations and backup/restore
- authentication/authorization
- SQLCipher access
- updater interruption/rollback
- portability/path assumptions
- attachment encryption and file validation

## Non-goals for this cycle
- new frontend framework
- remote database provider deployment
- Google Drive as live shared SQLite database
- mobile-first redesign
- production deployment
- credential rotation
- deletion of compatibility routes before R23 evidence
- speculative features outside R11..R23
