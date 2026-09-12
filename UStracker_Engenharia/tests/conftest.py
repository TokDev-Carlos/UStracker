"""Keep each test run in an isolated, writable engineering directory."""
from pathlib import Path
from uuid import uuid4


def pytest_configure(config):
    if config.option.basetemp is None:
        root = Path(__file__).resolve().parents[1]
        runs = root / "Artifacts/TestRuns"
        runs.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(runs / uuid4().hex)
