"""C06/unit support for C01: reject ambiguous or escaping active releases."""
import importlib
import json
import os
from pathlib import Path
import subprocess

import pytest


@pytest.fixture
def api():
    try:
        return importlib.import_module("ustracker.core.paths")
    except ModuleNotFoundError:
        pytest.fail("RootPaths/version API has not been implemented")


@pytest.fixture
def candidate(tmp_path):
    root = tmp_path / "Teste UStracker ç º"
    release = root / "Releases/1.00.00.000"
    (release / "Runtime").mkdir(parents=True)
    (release / "WebView2Runtime").mkdir()
    (release / "Runtime/pythonw.exe").write_bytes(b"unit fixture, not executable")
    (root / "UStracker.exe").write_bytes(b"unit fixture, not executable")
    (release / "VERSION.json").write_text('{"version":"1.00.00.000"}')
    (root / "current.json").write_text(json.dumps({
        "release": "Releases/1.00.00.000",
        "dataset": "69a54618-2099-47d5-ae60-6607b1b7c308",
        "sequence": 1,
    }))
    return root


def test_numeric_version_order_and_round_trip(api):
    versions = [api.BuildVersion.parse(v) for v in
                ["1.00.00.010", "1.00.00.000", "10.00.00.000", "2.00.00.000"]]
    assert [str(v) for v in sorted(versions)] == [
        "1.00.00.000", "1.00.00.010", "2.00.00.000", "10.00.00.000"]


@pytest.mark.parametrize("value", ["1.0.00.000", "01.00.00.000", "1.00.00",
    "1.00.00.-01", "1.00.00.1000", "v1.00.00.000", "1.00.00.000\n", 1, None])
def test_version_rejects_noncanonical_values(api, value):
    with pytest.raises(ValueError):
        api.BuildVersion.parse(value)


def test_root_uses_executable_not_working_directory(api, candidate, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths = api.RootPaths.resolve(candidate / "UStracker.exe")
    assert paths.root == candidate
    assert paths.release == candidate / "Releases/1.00.00.000"
    assert paths.runtime == paths.release / "Runtime"
    assert paths.webview2_runtime == paths.release / "WebView2Runtime"
    assert str(paths.version) == "1.00.00.000"


def test_moving_tree_changes_root_without_absolute_state(api, candidate, tmp_path):
    before = api.RootPaths.resolve(candidate / "UStracker.exe")
    moved = candidate.rename(tmp_path / "Movido ç")
    after = api.RootPaths.resolve(moved / "UStracker.exe")
    assert before.release.relative_to(before.root) == after.release.relative_to(after.root)
    assert after.root == moved


@pytest.mark.parametrize("target", ["../Releases/1.00.00.000", "Releases/../1.00.00.000",
    "C:/Releases/1.00.00.000", "/Releases/1.00.00.000", "Releases\\1.00.00.000",
    "Releases//1.00.00.000", "Runtime/1.00.00.000", "Releases/latest",
    "Releases/1.00.00.000/", "Releases/1.00.00.000.", "Releases/1.00.00.000:ads"])
def test_current_rejects_unsafe_release(api, candidate, target):
    current = json.loads((candidate / "current.json").read_text())
    current["release"] = target
    (candidate / "current.json").write_text(json.dumps(current))
    with pytest.raises(ValueError):
        api.RootPaths.resolve(candidate / "UStracker.exe")


@pytest.mark.parametrize("relative", ["current.json", "Releases/1.00.00.000/VERSION.json",
    "Releases/1.00.00.000/Runtime/pythonw.exe", "UStracker.exe"])
def test_missing_required_file_fails(api, candidate, relative):
    (candidate / relative).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        api.RootPaths.resolve(candidate / "UStracker.exe")


def test_missing_webview_runtime_is_not_accepted(api, candidate):
    (candidate / "Releases/1.00.00.000/WebView2Runtime").rmdir()
    with pytest.raises((ValueError, FileNotFoundError)):
        api.RootPaths.resolve(candidate / "UStracker.exe")


def test_version_json_is_release_authority(api, candidate):
    (candidate / "Releases/1.00.00.000/VERSION.json").write_text(
        '{"version":"1.00.00.010"}')
    with pytest.raises(ValueError):
        api.RootPaths.resolve(candidate / "UStracker.exe")


@pytest.mark.parametrize("field,value", [("dataset", "../production"),
    ("dataset", "not-a-uuid"), ("sequence", True), ("sequence", 0),
    ("sequence", 1.0), ("version", "1.00.00.000")])
def test_current_rejects_invalid_dataset_sequence_or_extra_version(api, candidate, field, value):
    current = json.loads((candidate / "current.json").read_text())
    current[field] = value
    (candidate / "current.json").write_text(json.dumps(current))
    with pytest.raises(ValueError):
        api.RootPaths.resolve(candidate / "UStracker.exe")


def test_json_duplicate_authority_is_rejected(api, candidate):
    (candidate / "Releases/1.00.00.000/VERSION.json").write_text(
        '{"version":"9.99.99.999","version":"1.00.00.000"}')
    with pytest.raises(ValueError):
        api.RootPaths.resolve(candidate / "UStracker.exe")


def test_relative_executable_is_rejected(api):
    with pytest.raises(ValueError):
        api.RootPaths.resolve(Path("UStracker.exe"))


@pytest.mark.parametrize("relative", ["Releases", "Releases/1.00.00.000/Runtime",
                                     "Releases/1.00.00.000/WebView2Runtime"])
def test_junction_cannot_redirect_candidate_outside_root(api, candidate, tmp_path, relative):
    source = candidate / relative
    external = source.rename(tmp_path / "external")
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    quote = lambda p: "'" + str(p).replace("'", "''") + "'"
    result = subprocess.run([str(powershell), "-NoProfile", "-Command",
        "$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path "
        + quote(source) + " -Value " + quote(external) + " | Out-Null"],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    try:
        with pytest.raises(ValueError):
            api.RootPaths.resolve(candidate / "UStracker.exe")
    finally:
        source.rmdir()  # Removes this junction only; no recursive operation.


def test_known_synchronized_root_is_rejected(api, candidate, monkeypatch):
    monkeypatch.setenv("OneDrive", str(candidate.parent))
    with pytest.raises(ValueError):
        api.RootPaths.resolve(candidate / "UStracker.exe")


def test_unc_root_is_rejected_before_filesystem_access(api):
    with pytest.raises(ValueError):
        api.RootPaths.resolve(Path(r"\\server\share\UStracker.exe"))


@pytest.mark.parametrize("drive_type", [0, 1, 4, 5])
def test_remote_unknown_or_readonly_drive_is_rejected(api, candidate, monkeypatch, drive_type):
    monkeypatch.setattr(api, "_drive_type", lambda anchor: drive_type, raising=False)
    with pytest.raises(ValueError):
        api.RootPaths.resolve(candidate / "UStracker.exe")


@pytest.mark.parametrize("drive_type", [2, 3, 6])
def test_local_drive_types_are_accepted(api, candidate, monkeypatch, drive_type):
    monkeypatch.setattr(api, "_drive_type", lambda anchor: drive_type, raising=False)
    assert api.RootPaths.resolve(candidate / "UStracker.exe").root == candidate
