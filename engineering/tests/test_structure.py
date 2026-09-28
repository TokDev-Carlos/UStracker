import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]


class EngineeringStructureTests(unittest.TestCase):
    def test_required_control_files_exist(self):
        required = [
            'engineering/README.md',
            'engineering/ARCHITECTURE.md',
            'engineering/EXECUTION_CONTRACT.md',
            'engineering/APPROVAL.json',
            'engineering/EXECUTION_STATE.json',
            'engineering/config/project.json',
            'engineering/config/path-policy.json',
            'engineering/config/test-matrix.json',
            'engineering/config/baseline_snapshot.json',
            'engineering/tools/Invoke-Preflight.ps1',
            'engineering/tools/New-Increment.ps1',
            'engineering/tools/Invoke-Verification.ps1',
            'engineering/tools/New-Checkpoint.ps1',
            'engineering/tools/Build-Candidate.ps1',
            'engineering/supabase/migrations/0001_engineering_registry.sql',
        ]
        missing = [p for p in required if not (ROOT / p).is_file()]
        self.assertEqual(missing, [])

    def test_execution_starts_locked(self):
        approval = json.loads((ROOT / 'engineering/APPROVAL.json').read_text(encoding='utf-8'))
        state = json.loads((ROOT / 'engineering/EXECUTION_STATE.json').read_text(encoding='utf-8'))
        self.assertFalse(approval['user_approved_execution'])
        self.assertEqual(state['phase'], 'PREPARED_AWAITING_USER_CONFIRMATION')
        self.assertFalse(state['functional_plan_started'])

    def test_project_config_uses_schema3_baseline_and_schema8_target(self):
        config = json.loads((ROOT / 'engineering/config/project.json').read_text(encoding='utf-8'))
        self.assertEqual(config['baseline_version'], '1.00.01.000')
        self.assertEqual(config['baseline_schema_version'], 3)
        self.assertEqual(config['planned_schema_version'], 8)
        self.assertEqual(config['baseline_tag'], 'baseline/1.00.01.000-schema3')

    def test_all_planned_changesets_are_prepared_and_locked(self):
        paths = sorted((ROOT / 'engineering/changesets').glob('R*.json'))
        self.assertEqual(len(paths), 10)
        for path in paths:
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(data['status'], 'PREPARED', path.name)
            self.assertFalse(data['user_approved_execution'], path.name)
            self.assertTrue(data['acceptance_checks'], path.name)
            self.assertLessEqual(data['schema_to'] - data['schema_from'], 1, path.name)
            self.assertGreaterEqual(data['schema_to'], data['schema_from'], path.name)

    def test_supabase_migration_uses_private_dedicated_schema(self):
        sql = (ROOT / 'engineering/supabase/migrations/0001_engineering_registry.sql').read_text(encoding='utf-8').lower()
        self.assertIn('create schema if not exists ustracker_eng', sql)
        self.assertIn('revoke all on schema ustracker_eng from public', sql)
        self.assertNotIn('create table public.', sql)

    def test_powershell_wrappers_avoid_known_windows_powershell_51_traps(self):
        preflight = (ROOT / 'engineering/tools/Invoke-Preflight.ps1').read_text(encoding='utf-8')
        verification = (ROOT / 'engineering/tools/Invoke-Verification.ps1').read_text(encoding='utf-8')
        new_increment = (ROOT / 'engineering/tools/New-Increment.ps1').read_text(encoding='utf-8')
        build_candidate = (ROOT / 'engineering/tools/Build-Candidate.ps1').read_text(encoding='utf-8')
        self.assertNotIn('$IsWindows', preflight)
        self.assertIn('| Write-Host', verification)
        self.assertNotIn("if ($LASTEXITCODE -ne 0) { throw 'Preflight nao aprovado.' }", new_increment)
        self.assertNotIn("if ($LASTEXITCODE -ne 0) { throw 'Empacotamento falhou.' }", build_candidate)


if __name__ == '__main__':
    unittest.main()
