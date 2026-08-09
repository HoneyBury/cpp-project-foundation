from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .common import FoundationError
from .manifest import NAME_RE, VERSION_RE, load_manifest

TEXT_SUFFIXES = {
    "",
    ".cpp",
    ".h",
    ".md",
    ".py",
    ".txt",
    ".toml",
    ".yml",
    ".yaml",
    ".sh",
    ".service",
}


def initialize_project(name: str, version: str, output: Path) -> dict[str, object]:
    if NAME_RE.fullmatch(name) is None:
        raise FoundationError("project name must be a lowercase DNS-style slug")
    if VERSION_RE.fullmatch(version) is None:
        raise FoundationError("project version must be semantic")
    if output.exists():
        raise FoundationError(f"project output already exists: {output}")
    template = Path(__file__).resolve().parents[1] / "examples" / "hello-service"
    if not template.is_dir():
        raise FoundationError("cpp-service template is unavailable")
    template_version = load_manifest(template / "foundation.toml").version
    shutil.copytree(
        template,
        output,
        ignore=shutil.ignore_patterns(
            "build",
            ".conan2",
            ".venv",
            "runtime",
            "CMakeUserPresets.json",
            "__pycache__",
        ),
    )
    foundation_root = template.parents[1]
    quality_assets = (
        ".clang-format",
        ".clang-tidy",
        ".cmake-format.py",
        ".editorconfig",
        ".gitignore",
        ".markdownlint-cli2.yaml",
        ".shellcheckrc",
        "quality/baseline.json",
        "quality/npm/package-lock.json",
        "quality/npm/package.json",
        "quality/tools.json",
        "requirements/quality.txt",
        "ruff.toml",
        "scripts/install_quality_tools.py",
    )
    for value in quality_assets:
        source = foundation_root / value
        destination = output / value
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    identifier = name.replace("-", "_")
    class_name = "".join(part.capitalize() for part in name.split("-"))
    display_name = " ".join(part.capitalize() for part in name.split("-"))
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        if path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        text = text.replace("hello-service", name)
        text = text.replace("hello_service", identifier)
        text = text.replace("hello_core", f"{identifier}_core")
        text = text.replace("hello_requests_total", f"{identifier}_requests_total")
        text = text.replace("HelloService", class_name)
        text = text.replace("Hello Service", display_name)
        text = text.replace("hello service", name)
        text = text.replace("namespace hello", f"namespace {identifier}")
        text = text.replace("hello::", f"{identifier}::")
        text = text.replace('"hello/', f'"{identifier}/')
        if path.relative_to(output).as_posix() in {
            "CMakeLists.txt",
            "conanfile.py",
            "foundation.toml",
        }:
            text = text.replace(template_version, version)
        path.write_text(text, encoding="utf-8")
    for path in sorted(
        output.rglob("*"), key=lambda item: len(item.parts), reverse=True
    ):
        replacement = path.name.replace("hello-service", name)
        if replacement == "hello":
            replacement = identifier
        if replacement != path.name:
            path.rename(path.with_name(replacement))
    clang_format = shutil.which("clang-format-18") or shutil.which("clang-format")
    if clang_format:
        cpp_files = [
            str(path)
            for path in output.rglob("*")
            if path.is_file() and path.suffix in {".cpp", ".h"}
        ]
        subprocess.run([clang_format, "-i", *cpp_files], check=True)
    cmake_format = shutil.which("cmake-format")
    if cmake_format:
        cmake_files = [
            str(path)
            for path in output.rglob("*")
            if path.is_file()
            and (path.name == "CMakeLists.txt" or path.suffix == ".cmake")
        ]
        subprocess.run([cmake_format, "-i", *cmake_files], check=True)
    return {
        "schema_version": 1,
        "overall_pass": True,
        "project": name,
        "version": version,
        "source_formatted": bool(clang_format and cmake_format),
        "output": str(output),
        "next_steps": [
            "generate or review the Conan lockfile",
            "install and run the pinned quality tools",
            "run cpp-foundation validate",
            "open the first governed pull request",
        ],
    }
