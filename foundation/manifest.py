from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import FoundationError, relative_path


NAME_RE = re.compile(r"[a-z][a-z0-9-]{1,62}\Z")
VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\Z")


@dataclass(frozen=True)
class FoundationManifest:
    path: Path
    data: dict[str, Any]

    @property
    def root(self) -> Path:
        return self.path.parent

    @property
    def name(self) -> str:
        return str(self.data["project"]["name"])

    @property
    def version(self) -> str:
        return str(self.data["project"]["version"])

    @property
    def build(self) -> dict[str, Any]:
        return dict(self.data["build"])

    @property
    def release(self) -> dict[str, Any]:
        return dict(self.data["release"])

    @property
    def operations(self) -> dict[str, Any]:
        return dict(self.data.get("operations", {}))

    @property
    def observability(self) -> dict[str, Any]:
        return dict(self.data.get("observability", {}))

    def hook(self, name: str) -> list[str]:
        value = self.operations.get(name, [])
        return [str(item) for item in value]


def _require_table(document: dict[str, Any], key: str) -> dict[str, Any]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise FoundationError(f"foundation manifest requires [{key}]")
    return value


def _command(table: dict[str, Any], key: str) -> None:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise FoundationError(f"operations.{key} must be an array of command arguments")


def validate_manifest(document: Any, root: Path) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise FoundationError("foundation manifest schema_version must be 1")
    project = _require_table(document, "project")
    build = _require_table(document, "build")
    release = _require_table(document, "release")
    name = project.get("name")
    version = project.get("version")
    if not isinstance(name, str) or NAME_RE.fullmatch(name) is None:
        raise FoundationError("project.name must be a lowercase DNS-style slug")
    if not isinstance(version, str) or VERSION_RE.fullmatch(version) is None:
        raise FoundationError("project.version must be a semantic version")
    for key in ("target", "test_target", "profile", "lockfile"):
        if not isinstance(build.get(key), str) or not build[key].strip():
            raise FoundationError(f"build.{key} must be a non-empty string")
    relative_path(root, str(build["profile"]), must_exist=True)
    relative_path(root, str(build["lockfile"]), must_exist=True)
    executables = release.get("executables")
    if not isinstance(executables, list) or not executables:
        raise FoundationError("release.executables must contain at least one path")
    for value in [*executables, *release.get("include", [])]:
        if not isinstance(value, str) or not value.strip():
            raise FoundationError("release paths must be non-empty strings")
        relative_path(root, value)
    operations = document.get("operations", {})
    if not isinstance(operations, dict):
        raise FoundationError("operations must be a table")
    for key in ("activate", "verify", "deactivate", "canary", "benchmark"):
        _command(operations, key)
    if not operations.get("verify"):
        raise FoundationError(
            "operations.verify must define a fail-closed verification hook"
        )
    return document


def load_manifest(path: Path) -> FoundationManifest:
    resolved = path.resolve()
    try:
        document = tomllib.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise FoundationError(
            f"cannot read foundation manifest {resolved}: {exc}"
        ) from exc
    return FoundationManifest(resolved, validate_manifest(document, resolved.parent))


def export_environment(manifest: FoundationManifest, destination: Path) -> None:
    values = {
        "FOUNDATION_PROJECT_NAME": manifest.name,
        "FOUNDATION_PROJECT_VERSION": manifest.version,
        "FOUNDATION_CMAKE_TARGET": str(manifest.build["target"]),
        "FOUNDATION_TEST_TARGET": str(manifest.build["test_target"]),
        "FOUNDATION_CONAN_PROFILE": str(manifest.build["profile"]),
        "FOUNDATION_CONAN_LOCKFILE": str(manifest.build["lockfile"]),
        "FOUNDATION_FUZZ_TARGETS": " ".join(manifest.build.get("fuzz_targets", [])),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            if "\n" in value:
                raise FoundationError(f"environment value contains newline: {key}")
            stream.write(f"{key}={value}\n")
    for key, value in values.items():
        os.environ[key] = value
