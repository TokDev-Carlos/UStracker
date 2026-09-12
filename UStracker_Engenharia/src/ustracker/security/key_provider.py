"""Storage key boundary; its implementation is injected by the caller."""
from typing import Protocol
from uuid import UUID


class DatabaseKeyProvider(Protocol):
    def get_key(
        self, environment: str, dataset_id: UUID, purpose: str = "database"
    ) -> bytes:
        """Return key material scoped to the requested environment and dataset."""
        ...
