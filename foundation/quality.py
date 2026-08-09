from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .common import FoundationError

CPP_SUFFIXES = {".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}


def _tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode == 0:
        values = result.stdout.decode("utf-8").split("\0")
        return [root / value for value in values if value and (root / value).is_file()]
    return [
        path for path in root.rglob("*") if path.is_file() and ".git" not in path.parts
    ]


def _tool(*names: str) -> str:
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    raise FoundationError(f"required quality tool is unavailable: {' or '.join(names)}")


def _run(command: list[str], root: Path) -> None:
    result = subprocess.run(command, cwd=root, check=False)
    if result.returncode != 0:
        raise FoundationError(
            f"quality command failed ({result.returncode}): {' '.join(command)}"
        )


def run_quality(root: Path, mode: str = "fast", fix: bool = False) -> dict[str, object]:
    root = root.resolve()
    if mode not in {"fast", "deep"}:
        raise FoundationError(f"unsupported quality mode: {mode}")
    files = _tracked_files(root)
    cpp = [str(path.relative_to(root)) for path in files if path.suffix in CPP_SUFFIXES]
    python = [
        str(path.relative_to(root))
        for path in files
        if path.suffix == ".py" and path.name != ".cmake-format.py"
    ]
    shell = [str(path.relative_to(root)) for path in files if path.suffix == ".sh"]
    workflows = [
        str(path.relative_to(root))
        for path in files
        if ".github/workflows" in path.as_posix() and path.suffix in {".yml", ".yaml"}
    ]
    checks: list[str] = []
    if cpp:
        clang_format = _tool("clang-format-18", "clang-format")
        if fix:
            _run([clang_format, "-i", *cpp], root)
        _run([clang_format, "--dry-run", "--Werror", *cpp], root)
        checks.append("clang-format")
    if python:
        ruff = _tool("ruff")
        if fix:
            _run([ruff, "check", "--fix", *python], root)
            _run([ruff, "format", *python], root)
        _run([ruff, "check", *python], root)
        _run([ruff, "format", "--check", *python], root)
        checks.append("ruff")
    if shell:
        _run([_tool("shellcheck"), "--severity=style", *shell], root)
        checks.append("shellcheck")
    if workflows:
        _run([_tool("actionlint"), *workflows], root)
        checks.append("actionlint")
    if mode == "deep":
        cmake = [
            str(path.relative_to(root))
            for path in files
            if path.name == "CMakeLists.txt" or path.suffix == ".cmake"
        ]
        dockerfiles = [
            str(path.relative_to(root)) for path in files if path.name == "Dockerfile"
        ]
        if cmake:
            cmake_format = _tool("cmake-format")
            if fix:
                _run([cmake_format, "-i", *cmake], root)
            _run([cmake_format, "--check", *cmake], root)
            checks.append("cmake-format")
        _run([_tool("markdownlint-cli2")], root)
        checks.append("markdownlint")
        if dockerfiles:
            _run([_tool("hadolint"), *dockerfiles], root)
            checks.append("hadolint")
    return {
        "schema_version": 1,
        "overall_pass": True,
        "mode": mode,
        "fixed": fix,
        "checks": checks,
        "file_count": len(files),
    }
