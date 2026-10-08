"""2.3.0 — data the Adm Global never validated is set aside (never silently lost)."""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 2.3.1 — another Servidor saved the company cloud recently: restarting it is never allowed
RESTART_BLOCK_HOURS = 24
RESTART_WORD = 'RECOMEÇAR'


def saved_recently(saved_at: str | None) -> bool:
    if not saved_at:
        return False
    try:
        when = datetime.fromisoformat(str(saved_at).replace('Z', '+00:00'))
    except ValueError:
        return True  # unknown date: be safe
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - when < timedelta(hours=RESTART_BLOCK_HOURS)

# what belongs to a company dataset inside UserData (Logs and the WebView2 cache stay)
_DATASET = ('Auth', 'Production', 'Test', 'Media', 'Attachments', 'Public')
_STATE_FILES = ('cloud.json', 'cloud_restore.usbk', 'station.json', 'adm-global.ok')


def backup_old_root() -> Path:
    """Documentos\\UStracker_backup_old (the installer uses the same folder)."""
    forced = os.environ.get('USTRACKER_BACKUP_OLD')
    if forced:
        return Path(forced)
    return Path(os.path.expanduser('~')) / 'Documents' / 'UStracker_backup_old'


def retire_unvalidated_data(root, label: str = 'nuvem') -> str:
    """Copy the dataset to the backup folder, check the copy, then remove it from UserData. Returns the backup path."""
    data = Path(root) / 'UserData'
    dest = backup_old_root() / f"{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    dest.mkdir(parents=True, exist_ok=True)
    for name in _DATASET:
        if (data / name).exists():
            shutil.copytree(data / name, dest / name, dirs_exist_ok=True)
    for name in _STATE_FILES:
        if (data / 'State' / name).exists():
            (dest / 'State').mkdir(exist_ok=True)
            shutil.copy2(data / 'State' / name, dest / 'State' / name)
    if (data / 'Auth' / 'auth.db').exists() and not (dest / 'Auth' / 'auth.db').exists():
        raise OSError('backup of the old data failed; nothing was removed')
    for name in _DATASET:
        shutil.rmtree(data / name, ignore_errors=True)
    for name in _STATE_FILES:
        try:
            (data / 'State' / name).unlink()
        except FileNotFoundError:
            pass
    (data / 'Auth').mkdir(parents=True, exist_ok=True)
    return str(dest)


# ----------------------------------------------------------------------------- 2.5.0 começo limpo
# Toda instalação, de qualquer versão (2.2 → 2.4.x), entra na 2.5 sem dados antigos: backup completo
# conferido por SHA-256 em Documentos\UStracker_Backups\Pre-2.5_<data>, depois limpa. Tudo ou nada; uma vez só.
CLEAN_MARKER = 'inicio-2.5.json'
_CLEAN_KEEP = {'Logs', 'Updates', 'State'}            # State é limpo por dentro (fica só o cache do WebView2)
_STATE_KEEP = {'WebView2', CLEAN_MARKER}


def backups_root() -> Path:
    forced = os.environ.get('USTRACKER_BACKUPS')
    if forced:
        return Path(forced)
    return Path(os.path.expanduser('~')) / 'Documents' / 'UStracker_Backups'


def _sha256_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _old_items(data: Path) -> list[Path]:
    items = [p for p in data.iterdir() if p.name not in _CLEAN_KEEP] if data.exists() else []
    state = data / 'State'
    if state.exists():
        items += [p for p in state.iterdir() if p.name not in _STATE_KEEP]
    return items


def clean_start(root) -> dict:
    """Run once per installation (marker in UserData/State). Returns {'cleaned', 'backup'}."""
    import json
    data = Path(root) / 'UserData'
    marker = data / 'State' / CLEAN_MARKER
    if marker.exists():
        return {'cleaned': False, 'backup': None}
    items = _old_items(data)
    files = [f for item in items for f in ([item] if item.is_file() else [x for x in item.rglob('*') if x.is_file()])]
    dest = None
    if files:
        dest = backups_root() / f"Pre-2.5_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        sums = {}
        for f in files:
            rel = f.relative_to(data)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
            src_sum, dst_sum = _sha256_file(f), _sha256_file(target)
            if src_sum != dst_sum:
                raise OSError(f'backup não confere ({rel}); nada foi apagado')
            sums[rel.as_posix()] = src_sum
        (dest / 'SHA256SUMS.json').write_text(json.dumps(sums, indent=1), encoding='utf-8')
        for item in items:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({'at': datetime.now().isoformat(timespec='seconds'), 'backup': str(dest) if dest else None}),
                      encoding='utf-8')
    return {'cleaned': bool(files), 'backup': str(dest) if dest else None}
