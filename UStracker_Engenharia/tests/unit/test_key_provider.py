"""C07 boundary proof; no storage or Vault implementation is introduced."""
import importlib
import sys
from uuid import UUID

from tests.support.key_provider import StaticTestKeyProvider


def test_consumer_accepts_test_provider_without_loading_vault():
    try:
        boundary = importlib.import_module("ustracker.security.key_provider")
    except ModuleNotFoundError:
        raise AssertionError("DatabaseKeyProvider boundary is missing") from None

    def consume(provider: boundary.DatabaseKeyProvider, environment: str, dataset: UUID) -> bytes:
        return provider.get_key(environment, dataset)

    dataset = UUID("69a54618-2099-47d5-ae60-6607b1b7c308")
    provider = StaticTestKeyProvider({
        ("production", dataset, "database"): b"\x01" * 32,
        ("test", dataset, "database"): b"\x02" * 32,
    })
    assert consume(provider, "production", dataset) == b"\x01" * 32
    assert consume(provider, "test", dataset) == b"\x02" * 32
    assert not any(name.startswith("ustracker.security.vault") for name in sys.modules)
