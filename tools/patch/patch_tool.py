"""UStracker — Aplicador de Patch (lógica). Roda com o Python do UStracker instalado:

    <pasta do programa>\\Runtime\\python.exe -I patch_tool.py <comando> ...

Comandos (respondem UMA linha JSON; erro = {"error": "..."} e código 1):
    info    --root R --patch P                 confere o pacote e diz de qual versão para qual
    apply   --root R --patch P --backup-dir D  backup dos dados, aplica (volta sozinho se a versão nova não abrir)
    publish --patch P  (token do GitHub na entrada padrão)  lança no canal de atualização (todos os computadores)

Pacote .uspatch = zip com update.json (assinado com a chave de atualização) + UStracker-<versão>.usup (assinado).
Nada aqui guarda o token: ele chega pela entrada padrão e só vive na memória.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

REPO = 'TokDev-Carlos/UStracker'
BRANCH = 'main'
API = 'https://api.github.com'
DATA_DIRS = ('Auth', 'Production', 'Test')


class PatchError(Exception):
    pass


# --------------------------------------------------------------------------------------------- pacote
def read_patch(patch: Path, root: Path) -> tuple[dict, bytes]:
    """Open the .uspatch and check everything against THIS installation's update key. Returns (manifest, usup)."""
    from ustracker.update import inspect_package
    from ustracker.update_channel import FORMAT, LEVELS, _canonical, _public_key
    try:
        with zipfile.ZipFile(patch) as z:
            names = set(z.namelist())
            if 'update.json' not in names:
                raise PatchError('pacote sem update.json')
            manifest = json.loads(z.read('update.json').decode('utf-8'))
            pkg = str(manifest.get('package') or '')
            if not re.fullmatch(r'UStracker-[0-9.]+\.usup', pkg) or pkg not in names:
                raise PatchError('pacote incompleto (falta o .usup)')
            data = z.read(pkg)
    except zipfile.BadZipFile as exc:
        raise PatchError('o arquivo não é um pacote de patch do UStracker') from exc
    key = _public_key(root)
    body = {k: v for k, v in manifest.items() if k != 'sig'}
    try:
        key.verify(bytes.fromhex(manifest.get('sig') or ''), _canonical(body))
    except Exception as exc:
        raise PatchError('assinatura do pacote inválida (não foi gerado com a chave do UStracker)') from exc
    if manifest.get('format') != FORMAT or manifest.get('level') not in LEVELS or manifest.get('product') != 'UStracker':
        raise PatchError('pacote em formato desconhecido')
    if len(data) != int(manifest['size']) or hashlib.sha256(data).hexdigest() != manifest['sha256']:
        raise PatchError('pacote corrompido (tamanho/SHA-256 não confere)')
    with tempfile.TemporaryDirectory() as tmp:
        inner = Path(tmp) / pkg
        inner.write_bytes(data)
        try:
            info = inspect_package(inner, key)
        except Exception as exc:
            raise PatchError('assinatura do programa dentro do pacote inválida') from exc
    if str(info.get('to_version')) != str(manifest['version']):
        raise PatchError('o programa dentro do pacote não é da versão anunciada')
    return manifest, data


def installed_version(root: Path) -> str:
    try:
        return (root / 'version.md').read_text(encoding='utf-8').strip()
    except OSError as exc:
        raise PatchError(f'UStracker não encontrado em {root}') from exc


def cmd_info(root: Path, patch: Path) -> dict:
    from ustracker.update_channel import version_key
    manifest, _ = read_patch(patch, root)
    current = installed_version(root)
    return {'ok': True, 'from': current, 'to': manifest['version'], 'level': manifest['level'],
            'notes': manifest.get('notes', ''), 'newer': version_key(manifest['version']) > version_key(current)}


# --------------------------------------------------------------------------------------------- 1) esta máquina
def backup_data(root: Path, backup_dir: Path, label: str) -> str:
    """Copy the databases (Auth/Production/Test) and check the copies by SHA-256 before anything changes."""
    data = root / 'UserData'
    dest = backup_dir / f"Patch_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    copied = 0
    for name in DATA_DIRS:
        if (data / name).is_dir():
            shutil.copytree(data / name, dest / name, ignore=shutil.ignore_patterns('*.tmp', '*-journal'))
            for src in (data / name).rglob('*'):
                if src.is_file() and not src.name.endswith(('.tmp', '-journal')):
                    copy = dest / name / src.relative_to(data / name)
                    if hashlib.sha256(src.read_bytes()).hexdigest() != hashlib.sha256(copy.read_bytes()).hexdigest():
                        raise PatchError(f'backup não confere: {src.name}; nada foi alterado')
                    copied += 1
    if not copied:
        dest.mkdir(parents=True, exist_ok=True)
    return str(dest)


def cmd_apply(root: Path, patch: Path, backup_dir: Path, *, runner=None) -> dict:
    from ustracker.update_channel import version_key
    manifest, data = read_patch(patch, root)
    current = installed_version(root)
    if version_key(manifest['version']) <= version_key(current):
        raise PatchError(f"esta máquina já está na {current}; o pacote é da {manifest['version']}")
    saved = backup_data(root, backup_dir, f"{current}_para_{manifest['version']}")
    updates = root / 'UserData' / 'Updates'
    updates.mkdir(parents=True, exist_ok=True)
    (updates / 'pending.usup').write_bytes(data)
    (updates / 'pending.json').write_text(json.dumps({k: manifest[k] for k in ('version', 'level', 'notes', 'sha256')}),
                                          encoding='utf-8')
    # the installed program applies it: same path as the cloud update (rollback if the new version does not open)
    run = runner or (lambda: subprocess.run([sys.executable, '-m', 'ustracker.update_channel', '--apply-pending', '--root', str(root)],
                                            cwd=str(root), capture_output=True, text=True, timeout=1800,
                                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).returncode)
    code = run()
    now = installed_version(root)
    # the installed version decides: version.md only changes when the new version opened (else rollback).
    # (the 2.4.0 updater exits 1 even after applying — H-11)
    if now != manifest['version']:
        history = _last_history(root)
        raise PatchError(f"não aplicado ({history or 'código ' + str(code)}); versão instalada agora: {now}. Backup: {saved}")
    return {'ok': True, 'from': current, 'to': now, 'backup': saved, 'exit_code': code}


def _last_history(root: Path) -> str:
    try:
        items = json.loads((root / 'UserData' / 'State' / 'update_history.json').read_text(encoding='utf-8'))
        last = items[-1] if isinstance(items, list) and items else {}
        return str(last.get('error') or last.get('result') or '')
    except Exception:
        return ''


# --------------------------------------------------------------------------------------------- 2) todos os sistemas
def parse_token(text: str) -> str:
    found = re.search(r'(github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})', text or '')
    if not found:
        raise PatchError('token do GitHub não encontrado no arquivo escolhido')
    return found.group(1)


class GitHub:
    def __init__(self, token: str, opener=None):
        self.token = token
        self.opener = opener or urllib.request.build_opener()

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Authorization': f'Bearer {self.token}', 'Accept': 'application/vnd.github+json',
                                              'User-Agent': 'UStracker-Patch', 'Content-Type': 'application/json'})
        try:
            with self.opener.open(req, timeout=120) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and method == 'GET':
                return {}
            if exc.code in (401, 403):
                raise PatchError('o GitHub recusou o token (sem permissão de escrita no repositório UStracker)') from exc
            raise PatchError(f'GitHub respondeu {exc.code}') from exc
        except urllib.error.URLError as exc:
            raise PatchError('sem internet para lançar na nuvem') from exc

    def get(self, path: str) -> dict:
        return self.call('GET', f'/repos/{REPO}/contents/{path}?ref={BRANCH}')

    def put(self, path: str, data: bytes, message: str, sha: str | None) -> dict:
        body = {'message': message, 'content': base64.b64encode(data).decode(), 'branch': BRANCH}
        if sha:
            body['sha'] = sha
        return self.call('PUT', f'/repos/{REPO}/contents/{path}', body)

    def delete(self, path: str, message: str, sha: str) -> dict:
        return self.call('DELETE', f'/repos/{REPO}/contents/{path}', {'message': message, 'sha': sha, 'branch': BRANCH})


def cmd_publish(root: Path, patch: Path, token: str, *, github=None) -> dict:
    """Upload the .usup first, then switch update.json (one atomic step for the computers), then drop the old .usup."""
    from ustracker.update_channel import version_key
    manifest, data = read_patch(patch, root)
    if installed_version(root) != manifest['version']:
        raise PatchError('aplique primeiro nesta máquina (opção 1) e confira; só então lance para todos')
    gh = github or GitHub(token)
    current = gh.get('updates/update.json')
    old = {}
    if current.get('content'):
        old = json.loads(base64.b64decode(current['content']).decode('utf-8'))
        if version_key(old.get('version')) >= version_key(manifest['version']):
            raise PatchError(f"a nuvem já anuncia a {old.get('version')}; nada lançado")
    msg = f"UStracker {manifest['version']}: lançamento pelo Aplicador de Patch"
    existing = gh.get(f"updates/{manifest['package']}")
    gh.put(f"updates/{manifest['package']}", data, msg, existing.get('sha'))
    text = json.dumps(manifest, indent=2, ensure_ascii=False).encode('utf-8')
    gh.put('updates/update.json', text, msg, current.get('sha'))
    check = gh.get('updates/update.json')
    if not check.get('content') or json.loads(base64.b64decode(check['content']).decode('utf-8')).get('sig') != manifest['sig']:
        raise PatchError('o canal não confirmou a versão nova; confira o repositório')
    removed = None
    if old.get('package') and old['package'] != manifest['package']:
        prev = gh.get(f"updates/{old['package']}")
        if prev.get('sha'):
            gh.delete(f"updates/{old['package']}", f"UStracker {manifest['version']}: remove pacote antigo", prev['sha'])
            removed = old['package']
    return {'ok': True, 'published': manifest['version'], 'previous': old.get('version'), 'removed': removed}


# --------------------------------------------------------------------------------------------- linha de comando
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=('info', 'apply', 'publish'))
    ap.add_argument('--root', required=True)
    ap.add_argument('--patch', required=True)
    ap.add_argument('--backup-dir')
    args = ap.parse_args(argv)
    root, patch = Path(args.root), Path(args.patch)
    try:
        if args.command == 'info':
            out = cmd_info(root, patch)
        elif args.command == 'apply':
            if not args.backup_dir:
                raise PatchError('informe a pasta de backup')
            out = cmd_apply(root, patch, Path(args.backup_dir))
        else:
            out = cmd_publish(root, patch, parse_token(sys.stdin.read()))
    except PatchError as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=True)); return 1
    except Exception as exc:  # never a stack trace on the screen
        print(json.dumps({'error': f'erro inesperado: {type(exc).__name__}: {exc}'[:400]}, ensure_ascii=True)); return 1
    print(json.dumps(out, ensure_ascii=True))  # ASCII: python -I on Windows prints in cp1252
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
