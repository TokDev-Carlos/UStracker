from datetime import date, timedelta
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient

from ustracker.apply_update import apply as apply_update
from ustracker.auth import AuthService
from ustracker.backup import create_backup, prune_backups
from ustracker.db import Database
from ustracker.extensions import create_fleet, transfer_vehicle, verify_audit_chain
from ustracker.services import create_client, create_vehicle
from ustracker.station import ensure_station, relinquish_writer, require_writer
from ustracker.update import build_signed_package


def _admin(root: Path):
    auth = AuthService(root)
    boot = auth.bootstrap('Owner', 'owner-password-123')
    auth.enroll(boot['tickets'][0], 'Admin 2', 'admin2-password-123')
    auth.enroll(boot['tickets'][1], 'Admin 3', 'admin3-password-123')
    return auth.login('Owner', 'owner-password-123')


def _setup_api(tmp_path: Path):
    app = __import__('ustracker.server', fromlist=['create_app']).create_app(tmp_path)
    client = TestClient(app)
    csrf = client.get('/api/v1/auth/csrf').json()['csrf']
    boot = client.post('/api/v1/auth/bootstrap', json={'name':'Owner','password':'owner-password-123'}, headers={'X-CSRF-Token':csrf}).json()
    for i, ticket in enumerate(boot['tickets'], 2):
        csrf = client.get('/api/v1/auth/csrf').json()['csrf']
        r = client.post('/api/v1/auth/enroll', json={'ticket':ticket,'name':f'Admin {i}','password':f'admin-{i}-password-123'}, headers={'X-CSRF-Token':csrf})
        assert r.status_code == 200
    csrf = client.get('/api/v1/auth/csrf').json()['csrf']
    login = client.post('/api/v1/auth/login', json={'name':'Owner','password':'owner-password-123','environment':'production'}, headers={'X-CSRF-Token':csrf})
    assert login.status_code == 200, login.text
    return client, login.json()['csrf']


def test_idempotent_mutation_replays_same_result_and_rejects_changed_input(tmp_path):
    client, csrf = _setup_api(tmp_path)
    headers = {'X-CSRF-Token':csrf, 'X-Operation-ID':'idem-client-0001'}
    p = {'legal_name':'Cliente Idempotente'}
    first = client.post('/api/v1/clients', json=p, headers=headers)
    assert first.status_code == 201, first.text
    second = client.post('/api/v1/clients', json=p, headers=headers)
    assert second.status_code == 201 and second.json()['id'] == first.json()['id']
    changed = client.post('/api/v1/clients', json={'legal_name':'Outro'}, headers=headers)
    assert changed.status_code == 422
    assert len(client.get('/api/v1/clients').json()['items']) == 1


def test_station_transfer_enforces_single_writer(tmp_path, monkeypatch):
    session = _admin(tmp_path)
    db = Database(tmp_path, 'production', session.db_key)
    first = ensure_station(tmp_path, db)
    assert first['is_writer'] == 1
    transfer = relinquish_writer(tmp_path, db)
    assert transfer['writer_relinquished'] is True
    with pytest.raises(PermissionError):
        require_writer(tmp_path, db)

    # Receiving PC has no transferred local State identity.
    (tmp_path/'UserData'/'State'/'station.json').unlink()
    monkeypatch.setenv('COMPUTERNAME', 'RECEIVER-PC')
    second = ensure_station(tmp_path, db)
    assert second['id'] != first['id']
    assert second['is_writer'] == 1
    assert second['generation'] == transfer['generation']
    assert require_writer(tmp_path, db)['id'] == second['id']
    old = db.one('SELECT status,is_writer FROM stations WHERE id=?', (first['id'],))
    assert old['status'] == 'TRANSFERRED' and old['is_writer'] == 0


def test_fleet_vehicle_transfer_uses_revision_and_keeps_ownership_history(tmp_path):
    session = _admin(tmp_path)
    db = Database(tmp_path, 'production', session.db_key)
    c1 = create_client(db, session.slot, {'legal_name':'Cliente 1'})
    c2 = create_client(db, session.slot, {'legal_name':'Cliente 2'})
    f1 = create_fleet(db, session.slot, {'client_id':c1['id'], 'name':'Frota A'})
    vehicle = create_vehicle(db, session.slot, {'client_id':c1['id'], 'fleet_id':f1['id'], 'plate':'ABC1D23', 'type':'CARRO'})
    with pytest.raises(ValueError):
        transfer_vehicle(db, session.slot, vehicle['id'], {'client_id':c2['id'], 'expected_revision':99})
    original = db.one('SELECT * FROM ownerships WHERE vehicle_id=? AND effective_to IS NULL', (vehicle['id'],))
    start = date.fromisoformat(original['effective_from'])
    with pytest.raises(ValueError):
        transfer_vehicle(
            db, session.slot, vehicle['id'],
            {'client_id':c2['id'], 'expected_revision':1, 'effective_from':(start - timedelta(days=1)).isoformat()},
        )
    transfer_on = (start + timedelta(days=1)).isoformat()
    moved = transfer_vehicle(db, session.slot, vehicle['id'], {'client_id':c2['id'], 'expected_revision':1, 'effective_from':transfer_on})
    assert moved['client_id'] == c2['id'] and moved['revision'] == 2
    history = db.query('SELECT * FROM ownerships WHERE vehicle_id=? ORDER BY effective_from', (vehicle['id'],))
    assert len(history) == 2
    assert history[0]['effective_to'] == transfer_on


def test_audit_chain_detects_tampering(tmp_path):
    session = _admin(tmp_path)
    db = Database(tmp_path, 'production', session.db_key)
    create_client(db, session.slot, {'legal_name':'Auditado'})
    assert verify_audit_chain(db)['ok'] is True
    with db.transaction() as con:
        con.execute("UPDATE audit_events SET event_hash='tampered' WHERE id=(SELECT MIN(id) FROM audit_events)")
    result = verify_audit_chain(db)
    assert result['ok'] is False and result['broken_at_id'] == 1


def test_backup_retention_prunes_old_files(tmp_path):
    session = _admin(tmp_path)
    db = Database(tmp_path, 'production', session.db_key)
    create_client(db, session.slot, {'legal_name':'Backup'})
    first = create_backup(tmp_path, db, session.vrk)
    second = create_backup(tmp_path, db, session.vrk)
    assert first.exists() and second.exists() and first != second
    removed = prune_backups(tmp_path, 'production', keep=1)
    assert len(removed) == 1
    assert len(list((tmp_path/'UserData'/'Backups').glob('UStracker_production_*.usbk'))) == 1


def test_updater_records_full_protocol_and_verifies_switch(tmp_path):
    root = tmp_path/'product'; root.mkdir()
    (root/'Trust').mkdir(); (root/'UserData'/'State').mkdir(parents=True)
    (root/'VERSION.json').write_text(json.dumps({'version':'1.00.01.000'}), encoding='utf-8')
    (root/'old.txt').write_text('old', encoding='utf-8')
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    (root/'Trust'/'update_public_key.pem').write_bytes(public.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
    source = tmp_path/'patchsrc'; source.mkdir()
    (source/'VERSION.json').write_text(json.dumps({'version':'1.00.02.000'}), encoding='utf-8')
    (source/'new.txt').write_text('new', encoding='utf-8')
    package = tmp_path/'patch.usup'
    build_signed_package(source, package, '1.00.01.000', '1.00.02.000', private)
    result = apply_update(root, package)
    assert result['state'] == 'ACCEPTED'
    assert json.loads((root/'VERSION.json').read_text())['version'] == '1.00.02.000'
    assert (root/'new.txt').read_text() == 'new'
    journal = json.loads((root/'UserData'/'State'/'update_journal.json').read_text())
    assert journal['state'] == 'ACCEPTED'
