from __future__ import annotations

import json
import re
from pathlib import Path


# Release 2 onward: semantic N.N.N (2.0.0, 2.0.1, 2.1.0…); 1.xxx installations used the legacy N.NNN.
VERSION_PATTERN = re.compile(r'^(?:[0-9]+\.[0-9]+\.[0-9]+|[0-9]+\.[0-9]{3})$')
METADATA_FILES = ('VERSION.json', 'current.json')


def _version_file(path: Path | str | None = None) -> Path:
    if path is not None:
        candidate = Path(path).resolve()
        if candidate.is_file():
            return candidate
        runtime_version = candidate / 'version.md'
        if runtime_version.is_file():
            return runtime_version
    for parent in Path(__file__).resolve().parents:
        candidate = parent / 'version.md'
        if candidate.is_file():
            return candidate
    raise FileNotFoundError('version.md not found in application hierarchy')


def read_version(path: Path | str | None = None) -> str:
    version_file = _version_file(path)
    value = version_file.read_text(encoding='utf-8').strip()
    if not VERSION_PATTERN.fullmatch(value):
        raise ValueError('product version must use N.N.N (or legacy N.NNN) format')
    return value


def sync_version(repo_root: Path | str) -> dict:
    root = Path(repo_root).resolve()
    version = read_version(root)
    updated = []
    for name in METADATA_FILES:
        path = root / name
        metadata = json.loads(path.read_text(encoding='utf-8'))
        metadata['version'] = version
        path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        updated.append(name)
    return {'version': version, 'updated': updated}
