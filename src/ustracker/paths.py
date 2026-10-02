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
