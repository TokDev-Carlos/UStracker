"""G-05 — publica uma versão no canal de atualização (pasta updates/ do repositório).

Uso (lado do desenvolvimento, nunca na máquina do cliente):
    python tools/publish_update.py --version 2.1.0 --level normal --notes "..." --key <update_signing_key.pem>
O pacote leva o programa inteiro (ustracker + frontend + Docs + metadados). Nunca leva UserData nem Trust.
A chave privada fica só no cofre Chaves-Tokens/UStracker/update_signing_key.pem.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from ustracker.update_channel import build_release  # noqa: E402


def stage(repo: Path, out: Path) -> Path:
    """Program folder exactly as it sits inside C:\\UStracker."""
    shutil.copytree(repo / 'src' / 'ustracker', out / 'Runtime' / 'Lib' / 'site-packages' / 'ustracker',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(repo / 'frontend', out / 'frontend', ignore=shutil.ignore_patterns('node_modules', 'package.json'))
    docs = out / 'Docs'; docs.mkdir()
    for folder in (repo / 'release' / 'Docs', repo / 'docs'):
        for name in ('MANUAL_USUARIO.md', 'RECUPERACAO.md', 'NUVEM_GOOGLE_DRIVE.md', 'RELEASE_2.0.0.md'):
            if (folder / name).exists() and not (docs / name).exists():
                shutil.copy2(folder / name, docs / name)
    if (repo / 'cloud' / 'Code.gs').exists():
        shutil.copy2(repo / 'cloud' / 'Code.gs', docs / 'UStracker-Cloud-Code.gs')
    for name in ('VERSION.json', 'current.json', 'version.md'):
        shutil.copy2(repo / name, out / name)
    for leia in (repo / 'release' / 'LEIA-ME.txt', repo / 'installer' / 'LEIA-ME.txt'):
        if leia.exists():
            shutil.copy2(leia, out / 'LEIA-ME.txt'); break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', required=True)
    ap.add_argument('--level', choices=('normal', 'critical'), default='normal')
    ap.add_argument('--notes', default='')
    ap.add_argument('--key', required=True, help='update_signing_key.pem (Ed25519, cofre Chaves-Tokens)')
    ap.add_argument('--repo', default=str(ROOT))
    args = ap.parse_args()
    repo = Path(args.repo)
    if (repo / 'version.md').read_text(encoding='utf-8').strip() != args.version:
        raise SystemExit('version.md does not match --version')
    key = serialization.load_pem_private_key(Path(args.key).read_bytes(), password=None)
    with tempfile.TemporaryDirectory() as tmp:
        src = stage(repo, Path(tmp) / 'program')
        manifest = build_release(src, repo / 'updates', args.version, args.level, args.notes, key)
    print(manifest)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
