import io
import json
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ustracker.recovery import export_recovery, import_recovery
from ustracker.update import build_signed_package, inspect_package, safe_extract


def test_signed_update_rejects_tamper_and_traversal(tmp_path):
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'VERSION.json').write_text('{"version":"1.00.01.000"}', encoding='utf-8')
    pkg = tmp_path / 'patch.usup'
    build_signed_package(source, pkg, '1.00.00.000', '1.00.01.000', private)
    manifest = inspect_package(pkg, public)
    assert manifest['to_version'] == '1.00.01.000'

    out = tmp_path / 'out'
    safe_extract(pkg, out, public)
    assert (out / 'VERSION.json').exists()

    # Create a validly signed but structurally unsafe package to prove traversal is denied.
    bad_source = tmp_path / 'bad'
    bad_source.mkdir()
    (bad_source / 'ok.txt').write_text('ok', encoding='utf-8')
    bad = tmp_path / 'bad.usup'
    build_signed_package(bad_source, bad, '1', '2', private)
    with zipfile.ZipFile(bad, 'a') as z:
        z.writestr('../escape.txt', 'x')
    with pytest.raises(ValueError):
        safe_extract(bad, tmp_path / 'badout', public)


def test_recovery_export_round_trip(tmp_path):
    source = tmp_path / 'root'
    (source / 'UserData' / 'Auth').mkdir(parents=True)
    (source / 'UserData' / 'Auth' / 'auth.db').write_bytes(b'auth-data')
    (source / 'UserData' / 'Auth' / 'vault.json').write_text('{"x":1}', encoding='utf-8')
    (source / 'UserData' / 'Production').mkdir(parents=True)
    (source / 'UserData' / 'Production' / 'ustracker.db').write_bytes(b'production-data')
    (source / 'UserData' / 'Test').mkdir(parents=True)
    (source / 'UserData' / 'Test' / 'ustracker.db').write_bytes(b'test-data')
    (source / 'UserData' / 'State').mkdir(parents=True)
    (source / 'UserData' / 'State' / 'station.json').write_text('{"local":true}', encoding='utf-8')
    pkg = tmp_path / 'recovery.usre'
    export_recovery(source, pkg, 'correct horse battery staple')
    raw = pkg.read_bytes()
    assert b'auth-data' not in raw

    out = tmp_path / 'restored'
    import_recovery(pkg, out, 'correct horse battery staple')
    assert (out / 'UserData' / 'Auth' / 'auth.db').read_bytes() == b'auth-data'
    assert (out / 'UserData' / 'Production' / 'ustracker.db').read_bytes() == b'production-data'
    assert (out / 'UserData' / 'Test' / 'ustracker.db').read_bytes() == b'test-data'
    assert not (out / 'UserData' / 'State').exists()
    with pytest.raises(Exception):
        import_recovery(pkg, tmp_path / 'wrong', 'wrong passphrase')
