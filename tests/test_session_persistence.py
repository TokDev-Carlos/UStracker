from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from ustracker.server import create_app


def _csrf(client: TestClient) -> str:
    response = client.get('/api/v1/auth/csrf')
    assert response.status_code == 200
    return response.json()['csrf']


def _authenticated_client(tmp_path: Path) -> TestClient:
    client = TestClient(create_app(tmp_path))
    csrf = _csrf(client)
    response = client.post(
        '/api/v1/auth/bootstrap',
        json={'name': 'Admin 1', 'password': 'StrongPass!123'},
        headers={'X-CSRF-Token': csrf},
    )
    assert response.status_code == 200
    for slot, ticket in enumerate(response.json()['tickets'], start=2):
        csrf = _csrf(client)
        enrolled = client.post(
            '/api/v1/auth/enroll',
            json={'ticket': ticket, 'name': f'Admin {slot}', 'password': f'StrongPass!{slot}xx'},
            headers={'X-CSRF-Token': csrf},
        )
        assert enrolled.status_code == 200
    csrf = _csrf(client)
    login = client.post(
        '/api/v1/auth/login',
        json={'name': 'Admin 1', 'password': 'StrongPass!123', 'environment': 'test'},
        headers={'X-CSRF-Token': csrf},
    )
    assert login.status_code == 200
    return client


def test_frontend_refresh_does_not_detach_authenticated_session():
    source = Path('frontend/app.js').read_text(encoding='utf-8')
    assert "window.addEventListener('pagehide'" not in source
    assert "fetch('/api/v1/shell/detach'" not in source


def test_shell_reuses_persistent_webview_profile_and_does_not_delete_it():
    source = Path('host/Shell/MainWindow.xaml.cs').read_text(encoding='utf-8')
    assert 'Guid.NewGuid()' not in source
    assert 'Directory.Delete(profile, true)' not in source
    assert 'Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "UStracker", "WebView2")' in source


def test_shell_detach_does_not_revoke_session(tmp_path: Path):
    client = _authenticated_client(tmp_path)
    before = client.get('/api/v1/auth/me')
    assert before.status_code == 200

    detached = client.post('/api/v1/shell/detach')
    assert detached.status_code == 200

    after = client.get('/api/v1/auth/me')
    assert after.status_code == 200
    assert after.json()['name'] == 'Admin 1'


def test_authenticated_read_activity_refreshes_idle_timeout(tmp_path: Path):
    client = _authenticated_client(tmp_path)
    auth = client.app.state.auth
    token = client.cookies.get('us_session')
    session = auth.get_session(token)
    assert session is not None
    old_activity = auth._now() - timedelta(minutes=59)
    session.last_human_activity = old_activity

    dashboard = client.get('/api/v1/dashboard')
    assert dashboard.status_code == 200
    assert session.last_human_activity > old_activity
