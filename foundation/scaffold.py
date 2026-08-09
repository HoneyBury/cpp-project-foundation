from __future__ import annotations

import shutil
from pathlib import Path

from .common import FoundationError
from .manifest import NAME_RE, VERSION_RE


TEXT_SUFFIXES = {
    "",
    ".cpp",
    ".h",
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
    identifier = name.replace("-", "_")
    class_name = "".join(part.capitalize() for part in name.split("-"))
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        if path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        text = text.replace("hello-service", name)
        text = text.replace("hello_service", identifier)
        text = text.replace("hello_core", f"{identifier}_core")
        text = text.replace("hello_requests_total", f"{identifier}_requests_total")
        text = text.replace("HelloService", class_name)
        text = text.replace("hello service", name)
        text = text.replace("namespace hello", f"namespace {identifier}")
        text = text.replace("hello::", f"{identifier}::")
        text = text.replace('"hello/', f'"{identifier}/')
        text = text.replace("0.1.0", version)
        path.write_text(text, encoding="utf-8")
    for path in sorted(
        output.rglob("*"), key=lambda item: len(item.parts), reverse=True
    ):
        replacement = path.name.replace("hello-service", name)
        if replacement == "hello":
            replacement = identifier
        if replacement != path.name:
            path.rename(path.with_name(replacement))
    return {
        "schema_version": 1,
        "overall_pass": True,
        "project": name,
        "version": version,
        "output": str(output),
        "next_steps": [
            "generate or review the Conan lockfile",
            "run cpp-foundation validate",
            "open the first governed pull request",
        ],
    }
