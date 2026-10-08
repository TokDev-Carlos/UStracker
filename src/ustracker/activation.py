"""2.5.0 — começo limpo: toda instalação antiga é guardada (backup conferido) e começa sem dados."""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path


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
