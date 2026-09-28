import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))

import guard


class GuardTests(unittest.TestCase):
    def test_schema_progress_allows_same_or_single_step_only(self):
        self.assertEqual(guard.validate_schema_progress(3, 3), [])
        self.assertEqual(guard.validate_schema_progress(3, 4), [])
        self.assertTrue(guard.validate_schema_progress(3, 5))
        self.assertTrue(guard.validate_schema_progress(4, 3))

    def test_normalize_increment_id_rejects_unsafe_names(self):
        self.assertEqual(guard.normalize_increment_id('R2 Clientes'), 'r2-clientes')
        self.assertEqual(guard.normalize_increment_id('  Task_01  '), 'task-01')
        with self.assertRaises(ValueError):
            guard.normalize_increment_id('***')

    def test_diff_policy_blocks_forbidden_and_out_of_scope_paths(self):
        policy = {
            'always_forbidden': ['src/ustracker/auth.py', 'src/ustracker/crypto.py'],
            'always_allowed': ['engineering/**'],
        }
        changeset = {
            'allowed_paths': ['frontend/**'],
            'explicitly_allowed_sensitive_paths': [],
        }
        violations = guard.check_diff_policy(
            ['frontend/app.js', 'engineering/ledgers/progress.md', 'src/ustracker/auth.py', 'README.md'],
            policy,
            changeset,
        )
        self.assertIn('forbidden:src/ustracker/auth.py', violations)
        self.assertIn('out-of-scope:README.md', violations)
        self.assertNotIn('out-of-scope:frontend/app.js', violations)

    def test_diff_policy_can_explicitly_allow_sensitive_path(self):
        policy = {'always_forbidden': ['src/ustracker/db.py'], 'always_allowed': ['engineering/**']}
        changeset = {
            'allowed_paths': ['src/ustracker/db.py'],
            'explicitly_allowed_sensitive_paths': ['src/ustracker/db.py'],
        }
        self.assertEqual(guard.check_diff_policy(['src/ustracker/db.py'], policy, changeset), [])

    def test_verify_snapshot_detects_changed_missing_and_unexpected_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'a.txt').write_text('A', encoding='utf-8')
            (root / 'b.txt').write_text('B', encoding='utf-8')
            snapshot = guard.snapshot_files(root, excludes=[])
            (root / 'a.txt').write_text('changed', encoding='utf-8')
            (root / 'b.txt').unlink()
            (root / 'c.txt').write_text('C', encoding='utf-8')
            result = guard.verify_snapshot(root, snapshot, excludes=[])
            self.assertEqual(result['changed'], ['a.txt'])
            self.assertEqual(result['missing'], ['b.txt'])
            self.assertEqual(result['unexpected'], ['c.txt'])

    def test_validate_changeset_requires_approval_false_before_execution(self):
        data = {
            'id': 'r1-foundation',
            'baseline_version': '1.00.01.000',
            'schema_from': 3,
            'schema_to': 3,
            'status': 'PREPARED',
            'user_approved_execution': False,
            'allowed_paths': ['frontend/**'],
            'explicitly_allowed_sensitive_paths': [],
            'acceptance_checks': ['node --test tests/r2_ui.test.mjs'],
        }
        self.assertEqual(guard.validate_changeset(data), [])
        data['user_approved_execution'] = 'yes'
        self.assertTrue(guard.validate_changeset(data))

    def test_sensitive_path_scan_blocks_userdata_databases_and_private_key_files(self):
        paths = ['frontend/app.js', 'UserData/Auth/auth.db', '.env', 'certs/release.pfx', 'Trust/update_public_key.pem']
        findings = guard.detect_forbidden_tracked_paths(paths)
        self.assertIn('UserData/Auth/auth.db', findings)
        self.assertIn('.env', findings)
        self.assertIn('certs/release.pfx', findings)
        self.assertNotIn('Trust/update_public_key.pem', findings)

    def test_private_key_marker_is_detected_but_public_key_is_not(self):
        self.assertTrue(guard.contains_private_key_marker(b'-----BEGIN PRIVATE KEY-----'))
        self.assertFalse(guard.contains_private_key_marker(b'-----BEGIN PUBLIC KEY-----'))
        self.assertFalse(guard.contains_private_key_marker(b"marker = b'-----BEGIN PRIVATE KEY-----'"))


if __name__ == '__main__':
    unittest.main()
