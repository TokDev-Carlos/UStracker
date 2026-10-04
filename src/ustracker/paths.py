from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProductPaths:
    """Portable product paths derived exclusively from the selected root."""

    app_root: Path

    @classmethod
    def from_root(cls, root: Path | str) -> "ProductPaths":
        return cls(Path(root).expanduser().resolve())

    @property
    def data_root(self) -> Path:
        return self.app_root / "UserData"

    @property
    def state_root(self) -> Path:
        return self.data_root / "State"

    @property
    def cache_root(self) -> Path:
        return self.data_root / "Cache"

    @property
    def backup_root(self) -> Path:
        return self.data_root / "Backups"

    @property
    def log_root(self) -> Path:
        return self.data_root / "Logs"

    def ensure_runtime_directories(self) -> None:
        for path in (self.data_root, self.state_root, self.cache_root, self.backup_root, self.log_root):
            path.mkdir(parents=True, exist_ok=True)


def resolve_stored_path(root: Path | str, value: Path | str) -> Path:
    """Resolve a data path stored in the database or a journal.

    Accepts both the portable layout (``UserData/...``) and the 1.001 System+Data layout
    (``Data/...``), with either slash style, and always maps into ``APP_ROOT/UserData``.
    Absolute paths and parent traversal are refused.
    """
    from pathlib import PurePosixPath
    normalized = str(value or '').replace('\\', '/')
    relative = PurePosixPath(normalized)
    if not normalized or relative.is_absolute() or ':' in (relative.parts[0] if relative.parts else '') or '..' in relative.parts:
        raise ValueError('stored data path must be relative and cannot traverse parents')
    if relative.parts[0].casefold() not in {'data', 'userdata'}:
        raise ValueError('stored data path must begin with Data or UserData')
    base = ProductPaths.from_root(root).data_root
    candidate = base.joinpath(*relative.parts[1:]).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise ValueError('stored data path escapes UserData') from exc
    return candidate
