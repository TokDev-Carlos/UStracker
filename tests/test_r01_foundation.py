from pathlib import Path
import unittest

from ustracker.money import parse_money_api


ROOT = Path(__file__).resolve().parents[1]


class R01FoundationTests(unittest.TestCase):
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
