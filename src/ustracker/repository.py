from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .db import Database


class Repository(Protocol):
    """Domain-facing persistence boundary; remote implementations may follow later."""

    def database(self, environment: str, key: bytes) -> Database: ...


@dataclass(frozen=True)
class LocalRepository:
    root: Path

    def database(self, environment: str, key: bytes) -> Database:
        return Database(self.root, environment, key)
