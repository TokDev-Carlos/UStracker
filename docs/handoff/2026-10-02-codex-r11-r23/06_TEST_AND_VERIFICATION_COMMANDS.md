# TEST / VERIFICATION COMMANDS

Discover repository-native commands first. Current source snapshot contains Python unittest and Node test files.

## Baseline checks

```bash
git status --short --branch
python -m compileall -q src tests
node --check frontend/app.js
node --test tests/*.test.mjs
python -m unittest discover -s tests -p 'test_*.py' -v
```

Expected caveat:
- `sqlcipher3`-specific tests can be unavailable outside supported runtime/Windows. Record SKIP/ERROR accurately; do not report as PASS.

## Static portability scan

```bash
grep -RIn --exclude-dir=.git -E 'C:\\\\UStracker|C:/UStracker|Users\\\\[^\\]+' source/src source/frontend source/host
```

Any match must be classified as:
- product defect
- documentation/example
- Windows test fixture

## JS/runtime checks

Run `node --check` for every changed `.js` entrypoint/module when no build tool exists.

## Python checks

Run focused tests first, then full unittest discovery. Compile changed Python modules.

## .NET / Windows

Use supported Windows environment for:
- restore/build host Bootstrap/Shell/Updater
- WebView2 startup
- icon/window/shortcut smoke
- portable path scenarios
- updater apply/rollback

Do not infer Windows success from Linux source checks.
