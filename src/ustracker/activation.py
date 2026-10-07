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
