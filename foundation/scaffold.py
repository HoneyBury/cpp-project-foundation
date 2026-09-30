from __future__ import annotations

import shutil
import subprocess
import sysconfig
from pathlib import Path

from .common import FoundationError
from .manifest import load_manifest, project_identifier, validate_version

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

QUALITY_ASSETS = (
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
    "scripts/bootstrap_dev.py",
    "scripts/bootstrap_github.py",
    "scripts/install_quality_tools.py",
)

LICENSE_CHOICES = ("MIT", "Apache-2.0", "proprietary", "none")


def _write_license(output: Path, license_name: str, project_name: str) -> None:
    destination = output / "LICENSE"
    if license_name == "none":
        destination.unlink(missing_ok=True)
        return
    if license_name not in LICENSE_CHOICES:
        raise FoundationError(
            f"unsupported license {license_name!r}; choose from {', '.join(LICENSE_CHOICES)}"
        )
    source = Path(__file__).with_name("licenses") / f"{license_name}.txt"
    text = source.read_text(encoding="utf-8").replace("{{PROJECT_NAME}}", project_name)
    destination.write_text(text, encoding="utf-8")


def _template_sources() -> tuple[Path, Path]:
    repository_root = Path(__file__).resolve().parents[1]
    repository_template = repository_root / "examples" / "hello-service"
    if repository_template.is_dir():
        return repository_template, repository_root
    installed_template = (
        Path(sysconfig.get_path("data"))
        / "share"
        / "cpp-project-foundation"
        / "template"
    )
    if installed_template.is_dir():
        return installed_template, installed_template
    raise FoundationError("cpp-service template is unavailable")


def resolve_template_asset(project_root: Path, relative: Path) -> Path:
    """Resolve repository-template overlays without weakening consumer checks."""
    current = project_root / relative
    if current.is_file():
        return current
    template, quality_root = _template_sources()
    if (
        project_root.resolve() == template.resolve()
        and relative.as_posix() in QUALITY_ASSETS
    ):
        return quality_root / relative
    return current


def initialize_project(
    name: str,
    version: str,
    output: Path,
    *,
    license_name: str = "MIT",
) -> dict[str, object]:
    identifier = project_identifier(name)
    validate_version(version)
    if license_name not in LICENSE_CHOICES:
        raise FoundationError(
            f"unsupported license {license_name!r}; choose from {', '.join(LICENSE_CHOICES)}"
        )
    if output.exists():
        raise FoundationError(f"project output already exists: {output}")
    template, quality_root = _template_sources()
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
    for value in QUALITY_ASSETS:
        source = quality_root / value
        destination = output / value
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    _write_license(output, license_name, name)
    class_name = "".join(part.capitalize() for part in name.split("-"))
    display_name = " ".join(part.capitalize() for part in name.split("-"))
    cmake_version = version.split("-", maxsplit=1)[0].split("+", maxsplit=1)[0]
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
        text = text.replace(
            "namespace service = hello;", f"namespace service = {identifier};"
        )
        text = text.replace("hello::", f"{identifier}::")
        text = text.replace('"hello/', f'"{identifier}/')
        relative = path.relative_to(output).as_posix()
        if relative == "CMakeLists.txt":
            text = text.replace(template_version, cmake_version)
        elif relative in {"conanfile.py", "foundation.toml"}:
            text = text.replace(template_version, version)
        if relative == "foundation.toml" and license_name == "none":
            text = text.replace(
                'include = ["deploy", "LICENSE"]', 'include = ["deploy"]'
            )
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
        "license": license_name,
        "source_formatted": bool(clang_format and cmake_format),
        "output": str(output),
        "next_steps": [
            "generate or review the Conan lockfile",
            "install and run the pinned quality tools",
            "run cpp-foundation validate",
            "open the first governed pull request",
        ],
    }
