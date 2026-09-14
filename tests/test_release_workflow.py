from pathlib import Path


def test_release_requires_explicit_manual_confirmation():
    text = Path('.github/workflows/build-release.yml').read_text(encoding='utf-8')
    assert 'pull_request:' in text
    assert 'publish_release:' in text
    assert 'release_confirmation:' in text
    assert "github.event_name == 'workflow_dispatch'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "inputs.publish_release == true" in text
    assert "inputs.release_confirmation == 'PUBLICAR RELEASE USTRACKER'" in text
    assert 'tools\\smoke_portable.ps1' in text


def test_python_verification_propagates_native_command_failures():
    text = Path('.github/workflows/build-release.yml').read_text(encoding='utf-8')
    commands = [
        'python -m pytest -q',
        'python -m compileall -q src',
        'node --check frontend\\app.js',
        'node tests\\test_frontend_boot.js',
        'node tests\\test_frontend_boot_error.js',
    ]
    for command in commands:
        start = text.index(command)
        following = text[start:start + 180]
        assert '$LASTEXITCODE' in following, f'{command} must propagate non-zero exit status'
