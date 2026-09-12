"""Synthetic key provider, deliberately confined to engineering tests."""
from uuid import UUID


class StaticTestKeyProvider:
    def __init__(self, keys: dict[tuple[str, UUID, str], bytes]):
        self._keys = dict(keys)

    def get_key(self, environment: str, dataset_id: UUID, purpose: str = "database") -> bytes:
        return self._keys[(environment, dataset_id, purpose)]
