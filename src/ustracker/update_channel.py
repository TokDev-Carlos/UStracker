"""G-05 — atualização pela nuvem.

Canal: pasta ``updates/`` do repositório público UStracker (``main``):
* ``update.json`` — versão, nível (``normal`` | ``critical``), notas, nome/SHA-256/tamanho do pacote, assinatura Ed25519
  (mesma chave das atualizações: ``Trust/update_public_key.pem``).
* ``UStracker-<versão>.usup`` — pacote assinado com o programa inteiro (``from_version: '*'``).

Comportamento:
* checa ao abrir e a cada 3 horas; baixa sozinho e confere assinatura + SHA-256;
* **normal**: aplica quando o sistema fecha (na próxima abertura, antes de subir) ou em "Atualizar agora"
  (Administrador, Gerente ou quem tiver a permissão ``update.apply``);
* **critical**: o sistema bloqueia e qualquer pessoa aplica na hora;
* depois de aplicar, confere se o programa novo abre; se não abrir, volta sozinho para a versão anterior.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

FORMAT = 'ustracker-update/1'
DEFAULT_CHANNEL = 'https://raw.githubusercontent.com/TokDev-Carlos/UStracker/main/updates/update.json'
CHECK_EVERY_SECONDS = 3 * 3600
LEVELS = ('normal', 'critical')
UTC = timezone.utc


class UpdateError(RuntimeError):
    pass


def version_key(version: str) -> tuple:
    parts = str(version or '0').strip().split('.')
    try:
        if len(parts) == 2:  # legacy N.NNN (1.007 → 1.0.7)
            return (int(parts[0]), 0, int(parts[1]))
        return tuple(int(p) for p in (parts + ['0', '0'])[:3])
    except ValueError:
        return (0, 0, 0)


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def _public_key(root: Path):
    path = Path(root) / 'Trust' / 'update_public_key.pem'
    if not path.exists():
        raise UpdateError('chave pública de atualização ausente')
    return serialization.load_pem_public_key(path.read_bytes())


def _installed(root: Path) -> str:
    return (Path(root) / 'version.md').read_text(encoding='utf-8').strip()


# ----------------------------------------------------------------------------- publicação (lado do desenvolvimento)
def build_release(source: Path | str, out_dir: Path | str, version: str, level: str, notes: str,
                  private_key: Ed25519PrivateKey) -> Path:
    """Package the program folder ``source`` and write update.json + .usup into ``out_dir``."""
    from .update import build_signed_package
    if level not in LEVELS:
        raise ValueError('level must be normal or critical')
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob('UStracker-*.usup'):
        old.unlink()
    pkg = build_signed_package(source, out_dir / f'UStracker-{version}.usup', '*', version, private_key)
    data = pkg.read_bytes()
    body = {'format': FORMAT, 'product': 'UStracker', 'version': version, 'level': level, 'notes': notes,
            'package': pkg.name, 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data),
            'published_at': datetime.now(UTC).isoformat()}
    signed = {**body, 'sig': private_key.sign(_canonical(body)).hex()}
    (out_dir / 'update.json').write_text(json.dumps(signed, indent=2, ensure_ascii=False), encoding='utf-8')
    return out_dir / 'update.json'


# ----------------------------------------------------------------------------- instalação
def skipped_version(root: Path, version: str) -> bool:
    """H-12 — the Aplicador's option 2 marks the machine that launched a version for the others to ignore it."""
    try:
        data = json.loads((Path(root) / 'UserData' / 'State' / 'update_skip.json').read_text(encoding='utf-8'))
        return str(data.get('version')) == str(version)
    except Exception:
        return False


def can_apply(status: dict, *, is_admin: bool, permissions) -> bool:
    if not status.get('available'):
        return False
    if status.get('level') == 'critical':
        return True
    return bool(is_admin or 'update.apply' in (permissions or ()))


class UpdateService:
    def __init__(self, root: Path | str, channel_url: str = DEFAULT_CHANNEL, opener=None):
        self.root = Path(root)
        self.channel_url = channel_url
        self.opener = opener or urllib.request.build_opener()
        self.dir = self.root / 'UserData' / 'Updates'
        self.state: dict = {'available': False, 'checked_at': None, 'error': None}
        self.manifest: dict | None = None
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.restart = self._restart_backend  # replaced in tests
        pending = self._pending()
        if pending:
            self.state.update(available=True, version=pending['version'], level=pending['level'],
                              notes=pending.get('notes', ''), downloaded=True)

    # -- canal
    def _get(self, url: str, timeout: float = 30) -> bytes:
        req = urllib.request.Request(f"{url}{'&' if '?' in url else '?'}t={int(time.time())}",
                                     headers={'Cache-Control': 'no-cache', 'User-Agent': 'UStracker'})
        with self.opener.open(req, timeout=timeout) as resp:
            return resp.read()

    def check(self) -> dict:
        with self.lock:
            try:
                manifest = json.loads(self._get(self.channel_url, 20))
                body = {k: v for k, v in manifest.items() if k != 'sig'}
                _public_key(self.root).verify(bytes.fromhex(manifest.get('sig') or ''), _canonical(body))
                if manifest.get('format') != FORMAT or manifest.get('level') not in LEVELS:
                    raise UpdateError('canal em formato desconhecido')
            except Exception as exc:  # offline, 404, assinatura inválida: nada a fazer
                self.state.update(checked_at=datetime.now(UTC).isoformat(), error=str(exc)[:200])
                if not self._pending():
                    self.state.update(available=False)
                return dict(self.state)
            newer = (version_key(manifest['version']) > version_key(_installed(self.root))
                     and not skipped_version(self.root, manifest['version']))
            pending = self._pending()
            self.manifest = manifest if newer else None
            self.state = {'available': newer, 'version': manifest['version'] if newer else None,
                          'level': manifest['level'] if newer else None, 'notes': manifest.get('notes', '') if newer else '',
                          'downloaded': bool(newer and pending and pending.get('version') == manifest['version']),
                          'checked_at': datetime.now(UTC).isoformat(), 'error': None, 'current': _installed(self.root)}
            return dict(self.state)

    def download(self) -> dict:
        from .update import inspect_package
        with self.lock:
            m = self.manifest
            if not m:
                return dict(self.state)
            url = self.channel_url.rsplit('/', 1)[0] + '/' + m['package']
            data = self._get(url, 300)
            if len(data) != int(m['size']) or hashlib.sha256(data).hexdigest() != m['sha256']:
                raise UpdateError('pacote baixado não confere (tamanho/SHA-256)')
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self.dir / 'pending.usup.tmp'
            tmp.write_bytes(data)
            try:
                inner = inspect_package(tmp, _public_key(self.root))
            except Exception as exc:
                tmp.unlink(missing_ok=True)
                raise UpdateError('assinatura do pacote inválida') from exc
            if str(inner.get('to_version')) != str(m['version']):
                tmp.unlink(missing_ok=True)
                raise UpdateError('o pacote não é da versão anunciada no canal')
            tmp.replace(self.dir / 'pending.usup')
            (self.dir / 'pending.json').write_text(json.dumps({k: m[k] for k in ('version', 'level', 'notes', 'sha256')}),
                                                   encoding='utf-8')
            self.state['downloaded'] = True
            return dict(self.state)

    def _pending(self) -> dict | None:
        try:
            return json.loads((self.dir / 'pending.json').read_text(encoding='utf-8'))
        except Exception:
            return None

    # -- ciclo em segundo plano
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name='ustracker-updates', daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        if self._stop.wait(20):
            return
        while not self._stop.is_set():
            try:
                if self.check().get('available') and not self.state.get('downloaded'):
                    self.download()
            except Exception as exc:
                self.state['error'] = str(exc)[:200]
            if self._stop.wait(CHECK_EVERY_SECONDS):
                return

    # -- "Atualizar agora": reinicia o backend na mesma porta, aplicando o pendente antes de subir
    def _restart_backend(self) -> None:
        state = json.loads((self.root / 'UserData' / 'State' / 'backend.json').read_text(encoding='utf-8'))
        args = [sys.executable, '-m', 'ustracker.server', '--root', str(self.root), '--port', str(state['port']),
                '--wait-pid', str(os.getpid())]
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        subprocess.Popen(args, cwd=str(self.root), creationflags=flags, close_fds=True)


def _sanity(root: Path) -> bool:
    """Does the new program import? Runs in a fresh Python so the new files are the ones loaded."""
    try:
        out = subprocess.run([sys.executable, '-c', 'import ustracker.server'], cwd=str(root), timeout=120,
                             capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return out.returncode == 0
    except Exception:
        return False


def _root_writable(root: Path) -> bool:
    probe = Path(root) / f'.write-test-{os.getpid()}'
    try:
        probe.write_bytes(b'')
        probe.unlink()
        return True
    except OSError:
        return False


def _run_elevated(root: Path) -> int | None:
    """Program Files (2.2.0): only an administrator writes the program. Ask Windows (UAC) and wait.

    Returns the exit code, or None when elevation is not possible or was refused."""
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('fMask', ctypes.c_ulong), ('hwnd', wintypes.HWND),
                    ('lpVerb', wintypes.LPCWSTR), ('lpFile', wintypes.LPCWSTR), ('lpParameters', wintypes.LPCWSTR),
                    ('lpDirectory', wintypes.LPCWSTR), ('nShow', ctypes.c_int), ('hInstApp', wintypes.HINSTANCE),
                    ('lpIDList', ctypes.c_void_p), ('lpClass', wintypes.LPCWSTR), ('hkeyClass', wintypes.HKEY),
                    ('dwHotKey', wintypes.DWORD), ('hIconOrMonitor', wintypes.HANDLE), ('hProcess', wintypes.HANDLE)]
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x00000040 | 0x00000400  # SEE_MASK_NOCLOSEPROCESS | SEE_MASK_FLAG_NO_UI
    info.lpVerb = 'runas'
    info.lpFile = sys.executable
    info.lpParameters = f'-m ustracker.update_channel --apply-pending --root "{root}"'
    info.lpDirectory = str(root)
    info.nShow = 0
    try:
        if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)) or not info.hProcess:
            return None
        ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, 15 * 60 * 1000)
        code = wintypes.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(info.hProcess)
        return int(code.value)
    except Exception:
        return None


def apply_pending(root: Path | str, sanity=_sanity, *, elevate=_run_elevated) -> dict | None:
    """Install the downloaded package (app closed). Returns the journal, or None when nothing is pending."""
    root = Path(root)
    pdir = root / 'UserData' / 'Updates'
    pkg, meta = pdir / 'pending.usup', pdir / 'pending.json'
    if not pkg.exists() or not meta.exists():
        return None
    if not _root_writable(root):
        code = elevate(root)
        if code == 0:
            return {'result': 'applied', 'elevated': True}
        if code is None:
            _log(root, {'result': 'waiting', 'error': 'precisa da permissão de administrador do Windows (UAC)'})
            raise UpdateError('a atualização precisa da permissão de administrador do Windows; ela fica guardada para a próxima vez')
        raise UpdateError('a atualização não foi aplicada (veja Sistema › Atualização)')
    return _apply_here(root, sanity)


def _apply_here(root: Path, sanity=_sanity) -> dict:
    from .apply_update import _replace_file, apply
    pdir = root / 'UserData' / 'Updates'
    pkg, meta = pdir / 'pending.usup', pdir / 'pending.json'
    keep = pdir / 'previous'
    try:
        journal = apply(root, pkg, keep_rollback=keep)
    except Exception as exc:
        pkg.unlink(missing_ok=True); meta.unlink(missing_ok=True)
        _log(root, {'result': 'failed', 'error': str(exc)[:300]})
        raise UpdateError(f'atualização não aplicada: {exc}') from exc
    if not sanity(root):
        files = json.loads((keep / 'files.json').read_text(encoding='utf-8'))
        for entry in reversed(files):
            rel = Path(entry['path']); old = keep / rel; dst = root / rel
            if old.exists():
                _replace_file(old, dst)
            elif dst.exists():
                dst.unlink()
        pkg.unlink(missing_ok=True); meta.unlink(missing_ok=True)
        _log(root, {'result': 'rolled_back', 'version': journal.get('to')})
        raise UpdateError('a versão nova não abriu; o sistema voltou para a anterior')
    pkg.unlink(missing_ok=True); meta.unlink(missing_ok=True)
    shutil.rmtree(keep, ignore_errors=True)
    _precompile(root)
    _log(root, {'result': 'applied', 'from': journal.get('from'), 'to': journal.get('to')})
    return journal


def _precompile(root: Path) -> None:
    """Faster first start: compile the new code once (only matters where users cannot write the program)."""
    try:
        import compileall
        import ustracker
        compileall.compile_dir(str(Path(ustracker.__file__).parent), quiet=1)
    except Exception:
        pass


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply-pending', action='store_true')
    parser.add_argument('--root', required=True)
    args = parser.parse_args(argv)
    if not args.apply_pending:
        return 2
    try:
        return 0 if _apply_here(Path(args.root)) else 1
    except Exception as exc:
        try:
            _log(Path(args.root), {'result': 'failed', 'error': str(exc)[:300]})
        except Exception:
            pass
        return 1



def _log(root: Path, entry: dict) -> None:
    path = Path(root) / 'UserData' / 'State' / 'update_history.json'
    try:
        items = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        items = []
    items.append({**entry, 'at': datetime.now(UTC).isoformat()})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items[-50:], indent=2), encoding='utf-8')


if __name__ == '__main__':  # last line: everything above (incl. _log) must be defined first
    raise SystemExit(main())
