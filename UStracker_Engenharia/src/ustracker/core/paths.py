"""Portable release authority (PECSUS 1.2.1 sections 3 and 15)."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from uuid import UUID


@dataclass(frozen=True, order=True)
class BuildVersion:
    ba: int
    es: int
    in_: int
    se: int

    @classmethod
    def parse(cls, value: str) -> BuildVersion:
        """Parse canonical BA.ES.IN.SE, preserving numeric ordering."""
        if not isinstance(value, str) or not re.fullmatch(
            r"(0|[1-9][0-9]*)\.([0-9]{2})\.([0-9]{2})\.([0-9]{3})", value
        ):
            raise ValueError("Invalid BA/ES/IN/SE version")
        return cls(*(int(part) for part in value.split(".")))

    def __str__(self) -> str:
        return f"{self.ba}.{self.es:02d}.{self.in_:02d}.{self.se:03d}"


def _read_object(path: Path, fields: set[str]) -> dict:
    def unique(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON authority field")
            result[key] = value
        return result

    with path.open(encoding="utf-8-sig") as stream:
        value = json.load(stream, object_pairs_hook=unique)
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("Invalid release document fields")
    return value


def _reject_links(path: Path) -> None:
    for component in (path, *path.parents):
        if component.is_symlink() or component.is_junction():
            raise ValueError("Release paths cannot contain symlinks or junctions")


@dataclass(frozen=True)
class RootPaths:
    root: Path
    release: Path
    runtime: Path
    webview2_runtime: Path
    version: BuildVersion
    dataset: UUID
    sequence: int

    @classmethod
    def resolve(cls, executable: Path) -> RootPaths:
        """Validate the active release without creating or mutating any files."""
        if not executable.is_absolute():
            raise ValueError("Executable path must be absolute")
        if str(executable).startswith(("\\\\", "//")) or ".." in executable.parts:
            raise ValueError("Executable must be on an unambiguous local path")
        _reject_links(executable)
        if not executable.is_file():
            raise FileNotFoundError(executable)
        root = executable.parent
        for variable in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
            synchronized = os.environ.get(variable)
            if synchronized and root.resolve().is_relative_to(Path(synchronized).resolve()):
                raise ValueError("Synchronized folders cannot contain the active root")
        _reject_links(root / "current.json")
        current = _read_object(root / "current.json", {"release", "dataset", "sequence"})
        relative = current["release"]
        if not isinstance(relative, str) or not relative.startswith("Releases/"):
            raise ValueError("Active release must be under Releases")
        version = BuildVersion.parse(relative.removeprefix("Releases/"))
        if not isinstance(current["dataset"], str):
            raise ValueError("Dataset must be a UUID string")
        dataset = UUID(current["dataset"])
        if str(dataset) != current["dataset"]:
            raise ValueError("Dataset UUID must be canonical")
        sequence = current["sequence"]
        if type(sequence) is not int or sequence < 1:
            raise ValueError("Sequence must be a positive integer")
        release = root / relative
        _reject_links(release / "VERSION.json")
        authority = _read_object(release / "VERSION.json", {"version"})
        if BuildVersion.parse(authority["version"]) != version:
            raise ValueError("VERSION.json does not match active release")
        runtime = release / "Runtime"
        webview = release / "WebView2Runtime"
        _reject_links(runtime / "pythonw.exe")
        _reject_links(webview)
        if not (runtime / "pythonw.exe").is_file():
            raise FileNotFoundError(runtime / "pythonw.exe")
        if not webview.is_dir():
            raise FileNotFoundError(webview)
        return cls(root, release, runtime, webview, version, dataset, sequence)
