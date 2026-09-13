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
