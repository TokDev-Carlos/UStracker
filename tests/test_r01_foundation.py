from pathlib import Path
import json
import subprocess
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ustracker.money import parse_money_api


class R01FoundationTests(unittest.TestCase):
    def test_version_authority_accepts_only_major_dot_three_digits(self):
        from ustracker.versioning import read_version

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'version.md').write_text('1.234', encoding='utf-8')
            self.assertEqual(read_version(root), '1.234')

            (root / 'version.md').write_text('1.23', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'N.NNN'):
                read_version(root)

            (root / 'version.md').unlink()
            self.assertEqual(read_version(root), (ROOT / 'version.md').read_text(encoding='utf-8').strip())

    def test_version_sync_derives_compatibility_metadata(self):
        from ustracker.versioning import sync_version

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'version.md').write_text('1.001', encoding='utf-8')
            (root / 'VERSION.json').write_text(json.dumps({
                'product': 'UStracker', 'version': 'legacy', 'schema_version': 8,
            }), encoding='utf-8')
            (root / 'current.json').write_text(json.dumps({
                'product': 'UStracker', 'version': 'legacy', 'schema_version': 8,
            }), encoding='utf-8')

            result = sync_version(root)

            version = json.loads((root / 'VERSION.json').read_text(encoding='utf-8'))
            current = json.loads((root / 'current.json').read_text(encoding='utf-8'))
            self.assertEqual(result, {'version': '1.001', 'updated': ['VERSION.json', 'current.json']})
            self.assertEqual((version['version'], current['version']), ('1.001', '1.001'))
            self.assertEqual((version['schema_version'], current['schema_version']), (8, 8))

    def test_application_version_comes_from_runtime_root(self):
        from ustracker.server import create_app

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'version.md').write_text('7.321', encoding='utf-8')

            app = create_app(root)

            self.assertEqual(app.version, '7.321')

    def test_updater_reads_canonical_version_file(self):
        from ustracker.apply_update import _version

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'version.md').write_text('2.345', encoding='utf-8')
            (root / 'VERSION.json').write_text(json.dumps({'version': 'legacy'}), encoding='utf-8')

            self.assertEqual(_version(root), '2.345')

    def test_sbom_uses_canonical_product_version(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'SBOM.json'
            subprocess.run(
                [sys.executable, str(ROOT / 'tools/generate_sbom.py'), str(output)],
                check=True,
                capture_output=True,
                text=True,
            )
            sbom = json.loads(output.read_text(encoding='utf-8'))
            product = next(component for component in sbom['components'] if component['name'] == 'UStracker')

            self.assertEqual(product['version'], (ROOT / 'version.md').read_text(encoding='utf-8').strip())

    def test_api_money_accepts_legacy_decimal_and_ptbr_without_losing_cents(self):
        self.assertEqual(parse_money_api('1234.56'), 123456)
        self.assertEqual(parse_money_api('1.234,56'), 123456)
        self.assertEqual(parse_money_api('R$ 1.234,56'), 123456)
        self.assertEqual(parse_money_api('-R$ 12,34'), -1234)

    def test_windows_projects_declare_real_application_icons(self):
        bootstrap = (ROOT / 'host/Bootstrap/Bootstrap.csproj').read_text(encoding='utf-8')
        shell = (ROOT / 'host/Shell/Shell.csproj').read_text(encoding='utf-8')
        xaml = (ROOT / 'host/Shell/MainWindow.xaml').read_text(encoding='utf-8')
        self.assertIn('<ApplicationIcon>Assets\\UStracker.ico</ApplicationIcon>', bootstrap)
        self.assertIn('<ApplicationIcon>Assets\\UStracker.ico</ApplicationIcon>', shell)
        self.assertIn('Icon="Assets/UStracker.ico"', xaml)
        for rel in ['host/Bootstrap/Assets/UStracker.ico', 'host/Shell/Assets/UStracker.ico']:
            data = (ROOT / rel).read_bytes()
            self.assertGreater(len(data), 100)
            self.assertEqual(data[:4], b'\x00\x00\x01\x00')

    def test_bootstrap_has_idempotent_desktop_shortcut_service(self):
        source = (ROOT / 'host/Bootstrap/DesktopShortcut.cs').read_text(encoding='utf-8')
        program = (ROOT / 'host/Bootstrap/Program.cs').read_text(encoding='utf-8')
        self.assertIn('Environment.SpecialFolder.DesktopDirectory', source)
        self.assertIn('UStracker.lnk', source)
        self.assertIn('CreateOrUpdate', source)
        self.assertIn('Path.Combine(RootPaths.ProductRoot, "UStracker.exe")', source)
        self.assertIn('DesktopShortcut.CreateOrUpdate()', program)


if __name__ == '__main__':
    unittest.main()
