from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any

from .common import run_command, sha256_file
from .manifest import FoundationManifest


def _git(root: Path, *arguments: str) -> str:
    result = run_command(["git", *arguments], cwd=root, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def build_provenance(
    manifest: FoundationManifest, configuration: str
) -> dict[str, Any]:
    commit = _git(manifest.root, "rev-parse", "HEAD")
    candidate = os.environ.get("FOUNDATION_CANDIDATE_REVISION") or os.environ.get(
        "GITHUB_SHA", commit
    )
    if candidate:
        resolved = (
            _git(manifest.root, "rev-parse", f"{candidate}^{{commit}}") or candidate
        )
    else:
        resolved = "unversioned"
    lockfile = manifest.root / str(manifest.build["lockfile"])
    source_tree_clean = not bool(
        _git(manifest.root, "status", "--porcelain", "--untracked-files=normal")
    )
    return {
        "schema_version": 1,
        "project": manifest.name,
        "version": manifest.version,
        "candidate_revision": resolved,
        "git_commit": commit or "unversioned",
        "revision_matches_checkout": bool(commit and resolved == commit),
        "source_tree_clean": source_tree_clean,
        "git_ref": os.environ.get("GITHUB_REF_NAME")
        or _git(manifest.root, "branch", "--show-current")
        or "detached",
        "workflow": os.environ.get("GITHUB_WORKFLOW", "local"),
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "runner": os.environ.get("RUNNER_NAME") or platform.node() or "local",
        "runner_os": os.environ.get("RUNNER_OS") or platform.system(),
        "runner_arch": os.environ.get("RUNNER_ARCH") or platform.machine(),
        "build_configuration": configuration,
        "conan_lockfile": str(manifest.build["lockfile"]),
        "conan_lockfile_sha256": sha256_file(lockfile),
    }
