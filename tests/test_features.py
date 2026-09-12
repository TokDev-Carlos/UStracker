from pathlib import Path

from ustracker.auth import AuthService
from ustracker.backup import create_backup, restore_backup, verify_backup
from ustracker.db import Database
from ustracker.services import (
    apply_credit,
    create_catalog,
    create_client,
    create_payment,
    create_subscription,
    generate_charge,
    reverse_payment,
)


def _admin(root: Path):
    auth = AuthService(root)
    boot = auth.bootstrap('Owner', 'owner-password-123')
    auth.enroll(boot['tickets'][0], 'Admin 2', 'admin2-password-123')
    auth.enroll(boot['tickets'][1], 'Admin 3', 'admin3-password-123')
    return auth.login('Owner', 'owner-password-123')


def test_payment_credit_reverse_is_transactionally_consistent(tmp_path, monkeypatch):
    monkeypatch.setenv('USTRACKER_DEV_PLAINTEXT', '1')
    session = _admin(tmp_path)
    db = Database(tmp_path, 'production', session.db_key)
    client = create_client(db, session.slot, {'legal_name': 'Cliente A'})
    item = create_catalog(db, session.slot, {'code': 'P01', 'name': 'Plano', 'kind': 'PLAN', 'category': 'Mensal', 'price': '100.00'})
    sub = create_subscription(db, session.slot, {
        'client_id': client['id'], 'signed_on': '2026-09-01', 'start_on': '2026-09-01', 'due_day': 10,
        'items': [{'catalog_id': item['id'], 'description': 'Plano', 'quantity': 1, 'unit_price': '100.00'}],
    })
    charge = generate_charge(db, session.slot, sub['id'], '2026-09')
    pay = create_payment(db, session.slot, {
        'client_id': client['id'], 'amount': '150.00', 'create_credit': True,
        'allocations': [{'charge_id': charge['id'], 'amount': '100.00'}],
    })
    credit = db.one('SELECT * FROM credits WHERE id=?', (pay['credit_id'],))
    assert credit['balance_cents'] == 5000

    # A second charge receives part of the credit. Reversing the originating
    # payment must also reverse this derived use instead of double counting cash.
    sub2 = create_subscription(db, session.slot, {
        'client_id': client['id'], 'signed_on': '2026-10-01', 'start_on': '2026-10-01', 'due_day': 10,
        'items': [{'catalog_id': item['id'], 'description': 'Plano', 'quantity': 1, 'unit_price': '100.00'}],
    })
    charge2 = generate_charge(db, session.slot, sub2['id'], '2026-10')
    apply_credit(db, session.slot, credit['id'], charge2['id'], '25.00')
    reverse_payment(db, session.slot, pay['id'])

    assert db.one('SELECT status FROM credits WHERE id=?', (credit['id'],))[0] == 'REVERSED'
    assert db.one('SELECT COUNT(*) FROM credit_allocations WHERE credit_id=? AND active=1', (credit['id'],))[0] == 0
    assert db.one('SELECT COUNT(*) FROM payment_allocations WHERE payment_id=? AND active=1', (pay['id'],))[0] == 0


def test_encrypted_backup_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv('USTRACKER_DEV_PLAINTEXT', '1')
    session = _admin(tmp_path)
    db = Database(tmp_path, 'production', session.db_key)
    original = create_client(db, session.slot, {'legal_name': 'Antes do backup'})
    backup = create_backup(tmp_path, db, session.vrk)
    assert backup.read_bytes().startswith(b'USTRACKER_LOCAL_BACKUP_V1')
    verify_backup(backup, session.vrk)

    create_client(db, session.slot, {'legal_name': 'Depois do backup'})
    assert db.one('SELECT COUNT(*) FROM clients')[0] == 2
    restore_backup(tmp_path, db, session.vrk, backup)
    reopened = Database(tmp_path, 'production', session.db_key)
    assert reopened.one('SELECT COUNT(*) FROM clients')[0] == 1
    assert reopened.one('SELECT legal_name FROM clients WHERE id=?', (original['id'],))[0] == 'Antes do backup'
