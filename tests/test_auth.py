from pathlib import Path
from ustracker.auth import AuthService


def test_three_slot_bootstrap_enrollment_and_login(tmp_path: Path):
    auth = AuthService(tmp_path)
    status = auth.setup_status()
    assert status['slots'] == 3 and status['enrolled'] == 0
    result = auth.bootstrap('Carlos', 'StrongPass!123')
    assert len(result['tickets']) == 2
    auth.enroll(result['tickets'][0], 'Admin 2', 'StrongPass!456')
    auth.enroll(result['tickets'][1], 'Admin 3', 'StrongPass!789')
    assert auth.setup_status()['complete'] is True
    session = auth.login('Carlos', 'StrongPass!123')
    assert session.slot == 1
    assert len(session.db_key) == 32
    auth.logout(session.token)
    assert auth.get_session(session.token) is None
