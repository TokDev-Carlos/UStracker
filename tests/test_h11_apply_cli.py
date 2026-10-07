"""H-11 (2.4.0) — Aplicador no PC: o processo `--apply-pending` devolvia código 1 mesmo aplicando
(_log era definido depois do `if __name__ == '__main__'`), e o JSON do patch_tool saía em cp1252 (python -I)."""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, 'PYTHONPATH': str(ROOT / 'src'), 'USTRACKER_DEV_PLAINTEXT': '1'}


class ApplyCli(unittest.TestCase):
    def test_apply_pending_process_can_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'UserData' / 'Updates').mkdir(parents=True)
            (root / 'UserData' / 'Updates' / 'pending.usup').write_bytes(b'not a package')
            (root / 'UserData' / 'Updates' / 'pending.json').write_text('{}')
            subprocess.run([sys.executable, '-m', 'ustracker.update_channel', '--apply-pending', '--root', str(root)],
                           env=ENV, capture_output=True, text=True, timeout=120)
            hist = root / 'UserData' / 'State' / 'update_history.json'
            self.assertTrue(hist.exists(), 'o processo precisa conseguir gravar o histórico (_log definido antes do main)')
            self.assertEqual(json.loads(hist.read_text(encoding='utf-8'))[-1]['result'], 'failed')

    def test_patch_tool_output_is_ascii_json(self):
        import importlib.util, io
        spec = importlib.util.spec_from_file_location('patch_tool_h11', ROOT / 'tools' / 'patch' / 'patch_tool.py')
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        def boom(*a, **k): raise mod.PatchError('não aplicado; a máquina continua')
        mod.cmd_info = boom
        raw = io.BytesIO(); fake = io.TextIOWrapper(raw, encoding='cp1252')  # like python -I on Windows
        old = sys.stdout; sys.stdout = fake
        try:
            mod.main(['info', '--root', '.', '--patch', 'x.uspatch'])
        finally:
            fake.flush(); sys.stdout = old
        line = raw.getvalue().decode('ascii').strip()  # ASCII only: survives any Windows code page
        self.assertEqual(json.loads(line)['error'], 'não aplicado; a máquina continua')

if __name__ == '__main__':
    unittest.main()
