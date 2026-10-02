# PORTABILITY + UPDATER CONTRACT

## Portability

Application identity is logical, not path-based.

Required roots:
- APP_ROOT: directory containing active product installation/executable.
- DATA_ROOT: configured/derived local data root.
- CACHE_ROOT: disposable cache.
- BACKUP_ROOT: recoverable backups.
- LOG_ROOT: logs/diagnostics.

Rules:
- APP_ROOT may move between drives/folders.
- Paths persisted externally must be relative or relocatable where possible.
- No feature may depend on installation name `UStracker` or drive C:.
- A copied/restored installation must recalculate runtime paths.
- Desktop shortcut repair is allowed but must target current APP_ROOT.

## Updater

Updater stages an update outside the live file set but inside a bounded managed staging location. Staging is not a second permanent installation.

State machine:
IDLE → CHECKED → DOWNLOADED → VERIFIED → BACKED_UP → STAGED → APPLYING → HEALTHCHECK → COMMITTED
Failure after BACKED_UP/APPLYING → ROLLBACK → HEALTHCHECK_OLD → FAILED_RECORDED.

Manifest minimum:
- product/version
- minimum/maximum supported source version
- target schema compatibility
- file list
- size/hash
- signature metadata when enabled
- package hash

Updater must not:
- recursively copy entire install into arbitrary `*-Final`/`*-Novo` folders
- mutate data before compatibility/backup gate
- leave active application half-updated
- delete previous recoverable version before successful healthcheck
