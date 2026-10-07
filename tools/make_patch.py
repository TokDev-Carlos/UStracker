"""Gera o pacote de patch (.uspatch) desta versão para o Aplicador de Patch.

Uso (lado do desenvolvimento): python tools/make_patch.py --level normal --notes "..." --key <update_signing_key.pem> --out <pasta>
Saída: <pasta>/UStracker-<versão>.uspatch (update.json assinado + UStracker-<versão>.usup assinado) e .sha256.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from publish_update import stage  # noqa: E402
from ustracker.update_channel import build_release  # noqa: E402


def make_patch(repo: Path, out: Path, level: str, notes: str, key) -> Path:
    version = (repo / 'version.md').read_text(encoding='utf-8').strip()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = stage(repo, Path(tmp) / 'program')
        rel = Path(tmp) / 'release'
        manifest = build_release(src, rel, version, level, notes, key)
        pkg = next(rel.glob('UStracker-*.usup'))
        target = out / f'UStracker-{version}.uspatch'
        with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_STORED) as z:
            z.write(manifest, 'update.json')
            z.write(pkg, pkg.name)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (out / (target.name + '.sha256')).write_text(f'{digest}  {target.name}\n', encoding='utf-8')
    return target


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', choices=('normal', 'critical'), default='normal')
    ap.add_argument('--notes', default='')
    ap.add_argument('--key', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--repo', default=str(ROOT))
    args = ap.parse_args()
    key = serialization.load_pem_private_key(Path(args.key).read_bytes(), password=None)
    print(make_patch(Path(args.repo), Path(args.out), args.level, args.notes, key))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
