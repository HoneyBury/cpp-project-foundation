from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from . import __version__
from .common import sha256_file
from .manifest import load_manifest
from .scaffold import initialize_project

MANAGED_PATTERNS = (
    ".clang-format",
    ".clang-tidy",
    ".cmake-format.py",
    ".editorconfig",
    ".gitignore",
    ".iwyu.imp",
    ".markdownlint-cli2.yaml",
    ".shellcheckrc",
    ".github/dependabot.yml",
    "cmake/FoundationQuality.cmake",
    "conan/profiles/*",
    "quality/**/*",
    "requirements/quality.txt",
    "ruff.toml",
    "scripts/install_quality_tools.py",
)


def _managed_files(root: Path) -> list[Path]:
    files: set[Path] = set()
    for pattern in MANAGED_PATTERNS:
        files.update(path for path in root.glob(pattern) if path.is_file())
    return sorted(files)


def compare_template(root: Path, manifest_path: Path) -> dict[str, Any]:
    project_root = root.resolve()
    path = (
        manifest_path if manifest_path.is_absolute() else project_root / manifest_path
    )
    manifest = load_manifest(path)
    with tempfile.TemporaryDirectory(prefix="cpp-foundation-template-diff-") as name:
        expected_root = Path(name) / manifest.name
        initialize_project(manifest.name, manifest.version, expected_root)
        changes: list[dict[str, str]] = []
        for expected in _managed_files(expected_root):
            relative = expected.relative_to(expected_root)
            current = project_root / relative
            if not current.is_file():
                changes.append({"path": str(relative), "status": "missing"})
            elif sha256_file(current) != sha256_file(expected):
                changes.append({"path": str(relative), "status": "modified"})
    counts = {
        status: sum(item["status"] == status for item in changes)
        for status in ("missing", "modified")
    }
    return {
        "schema_version": 1,
        "overall_pass": not changes,
        "foundation_version": __version__,
        "project": manifest.name,
        "root": str(project_root),
        "counts": counts,
        "changes": changes,
    }
