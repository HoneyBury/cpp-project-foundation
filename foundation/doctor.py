from __future__ import annotations

import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from . import __version__
from .manifest import load_manifest

FOUNDATION_REF_RE = re.compile(
    r"HoneyBury/cpp-project-foundation/[^\s@]+@(v\d+\.\d+\.\d+)"
)


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def run_doctor(
    root: Path, manifest_path: Path, *, strict_tools: bool = False
) -> dict[str, Any]:
    project_root = root.resolve()
    path = (
        manifest_path if manifest_path.is_absolute() else project_root / manifest_path
    )
    checks: list[dict[str, str]] = []
    try:
        manifest = load_manifest(path)
    except (OSError, ValueError, RuntimeError) as exc:
        checks.append(_check("manifest", "fail", str(exc)))
        manifest = None
    else:
        checks.append(_check("manifest", "pass", f"{manifest.name} {manifest.version}"))

    required_files = (
        "CMakeLists.txt",
        "conanfile.py",
        ".github/workflows/ci.yml",
        ".github/workflows/quality.yml",
        ".github/workflows/release.yml",
        "quality/baseline.json",
    )
    missing = [
        value for value in required_files if not (project_root / value).is_file()
    ]
    checks.append(
        _check(
            "project-contract",
            "fail" if missing else "pass",
            f"missing: {', '.join(missing)}" if missing else "required files present",
        )
    )

    expected_ref = f"v{__version__}"
    refs: set[str] = set()
    workflows = project_root / ".github/workflows"
    if workflows.is_dir():
        for workflow in workflows.glob("*.yml"):
            refs.update(FOUNDATION_REF_RE.findall(workflow.read_text(encoding="utf-8")))
    if not refs:
        checks.append(
            _check("foundation-version", "fail", "no reusable workflow ref found")
        )
    elif refs == {expected_ref}:
        checks.append(_check("foundation-version", "pass", expected_ref))
    else:
        checks.append(
            _check(
                "foundation-version",
                "warn",
                f"installed {expected_ref}; workflow refs: {', '.join(sorted(refs))}",
            )
        )

    required_tools = ("git", "cmake")
    optional_tools = ("ninja", "conan", "docker")
    for tool in (*required_tools, *optional_tools):
        available = shutil.which(tool)
        required = strict_tools or tool in required_tools
        checks.append(
            _check(
                f"tool:{tool}",
                "pass" if available else ("fail" if required else "warn"),
                available or "not found on PATH",
            )
        )

    supported_platform = platform.system() == "Linux" and platform.machine() in {
        "x86_64",
        "amd64",
    }
    checks.append(
        _check(
            "platform",
            "pass" if supported_platform else "warn",
            f"{platform.system()} {platform.machine()}; production baseline is Linux x86_64",
        )
    )

    git = shutil.which("git")
    if git and (project_root / ".git").exists():
        result = subprocess.run(
            [git, "status", "--porcelain=v1"],
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
        )
        dirty = bool(result.stdout.strip())
        checks.append(
            _check(
                "source-tree",
                "warn" if dirty else "pass",
                "dirty; release packaging will fail" if dirty else "clean",
            )
        )

    if manifest is not None:
        release_paths = [
            project_root / value for value in manifest.release["executables"]
        ]
        built = [
            str(path.relative_to(project_root))
            for path in release_paths
            if path.is_file()
        ]
        checks.append(
            _check(
                "release-binaries",
                "pass" if len(built) == len(release_paths) else "warn",
                f"present: {', '.join(built)}" if built else "not built yet",
            )
        )

    counts = {
        status: sum(item["status"] == status for item in checks)
        for status in ("pass", "warn", "fail")
    }
    return {
        "schema_version": 1,
        "overall_pass": counts["fail"] == 0,
        "foundation_version": __version__,
        "root": str(project_root),
        "counts": counts,
        "checks": checks,
    }
