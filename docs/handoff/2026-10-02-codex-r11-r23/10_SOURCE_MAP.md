# SOURCE MAP

Primary frontend:
- frontend/app.js
- frontend/styles.css
- frontend/ui/*
- frontend/pages/*
- frontend/icons/*

Primary backend:
- src/ustracker/server.py
- src/ustracker/services.py
- src/ustracker/clients.py
- src/ustracker/mobility.py
- src/ustracker/catalog.py
- src/ustracker/commercial.py
- src/ustracker/finance.py
- src/ustracker/overview.py
- src/ustracker/attachments.py
- src/ustracker/db.py
- src/ustracker/backup.py
- src/ustracker/recovery.py
- src/ustracker/update.py
- src/ustracker/apply_update.py

Host/updater:
- host/Bootstrap/*
- host/Shell/*
- host/Updater/*
- host/Shared/RootPaths.cs

Current tests in reconstructed repository:
- tests/r01_foundation.test.mjs
- tests/r2_ui.test.mjs
- tests/test_r01_foundation.py
- tests/test_r2_backend.py
- tests/test_r2_regressions.py
- tests/test_r2_routes.py

IMPORTANT:
The historical test directory does not fully represent all schema8 increments. R11 work must first add/restore characterization tests for the current schema8 baseline before changing affected behavior.
