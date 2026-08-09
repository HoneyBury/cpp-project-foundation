#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import runpy
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION_RE = re.compile(r"^\s*uses:\s*([^#\s]+)@([^\s#]+)", re.MULTILINE)
SBOM_PATH_RE = re.compile(r"^\s*sbom-path:\s*([^#\s]+)", re.MULTILINE)
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
FOUNDATION_VERSION_RE = re.compile(r"v\d+\.\d+\.\d+\Z")


def main() -> int:
    errors = []
    foundation_version = runpy.run_path(ROOT / "foundation/__init__.py")["__version__"]
    expected_foundation_revision = f"v{foundation_version}"
    required = [
        ".clang-format",
        ".clang-tidy",
        ".editorconfig",
        ".github/CODEOWNERS",
        ".github/dependabot.yml",
        "CONTRIBUTING.md",
        "README.md",
        "README.zh-CN.md",
        "SECURITY.md",
        ".github/workflows/ci.yml",
        ".github/workflows/codeql.yml",
        ".github/workflows/deep-quality.yml",
        ".github/workflows/quality.yml",
        ".github/workflows/security.yml",
        ".github/workflows/release.yml",
        ".github/workflows/publish-pypi.yml",
        "examples/hello-service/.github/dependabot.yml",
        "docs/publishing.md",
        "docs/publishing.zh-CN.md",
        "quality/baseline.json",
        "quality/npm/package-lock.json",
        "quality/npm/package.json",
        "quality/tools.json",
        "requirements/quality.txt",
        "ruff.toml",
    ]
    for value in required:
        if not (ROOT / value).is_file():
            errors.append(f"missing governance file: {value}")
    readme_links = {
        "README.md": "README.zh-CN.md",
        "README.zh-CN.md": "README.md",
    }
    for readme, target in readme_links.items():
        path = ROOT / readme
        if path.is_file() and target not in path.read_text(encoding="utf-8"):
            errors.append(f"README language switch is missing: {readme} -> {target}")
    workflows = sorted((ROOT / ".github/workflows").glob("*.yml")) + sorted(
        (ROOT / "examples/hello-service/.github/workflows").glob("*.yml")
    )
    for workflow in workflows:
        text = workflow.read_text(encoding="utf-8")
        if "permissions:" not in text:
            errors.append(f"workflow has no explicit permissions: {workflow.name}")
        for sbom_path in SBOM_PATH_RE.findall(text):
            if "*" in sbom_path or "?" in sbom_path:
                errors.append(
                    f"attestation sbom-path must be an exact file: "
                    f"{workflow.name}: {sbom_path}"
                )
        for action, revision in ACTION_RE.findall(text):
            if action.startswith("./"):
                continue
            if action.startswith(
                "HoneyBury/cpp-project-foundation/"
            ) and FOUNDATION_VERSION_RE.fullmatch(revision):
                if revision != expected_foundation_revision:
                    errors.append(
                        f"foundation action is not on {expected_foundation_revision}: "
                        f"{action}@{revision}"
                    )
                continue
            if SHA_RE.fullmatch(revision) is None:
                errors.append(
                    f"action is not pinned to a full SHA: {action}@{revision}"
                )
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_metadata = pyproject["project"]
    if project_metadata.get("readme", {}).get("file") != "README.md":
        errors.append("Python package README metadata is missing")
    if project_metadata.get("license") != "MIT":
        errors.append("Python package SPDX license metadata is missing")
    if "Repository" not in project_metadata.get("urls", {}):
        errors.append("Python package repository URL is missing")
    for requirement in pyproject["build-system"]["requires"]:
        if "==" not in requirement:
            errors.append(
                f"Python build dependency is not exactly pinned: {requirement}"
            )
    for requirement in (
        (ROOT / "requirements/quality.txt").read_text(encoding="utf-8").splitlines()
    ):
        if requirement and not requirement.startswith("#") and "==" not in requirement:
            errors.append(f"quality dependency is not exactly pinned: {requirement}")
    npm_package = json.loads(
        (ROOT / "quality/npm/package.json").read_text(encoding="utf-8")
    )
    npm_lock = json.loads(
        (ROOT / "quality/npm/package-lock.json").read_text(encoding="utf-8")
    )
    markdownlint_version = npm_package["dependencies"]["markdownlint-cli2"]
    if (
        npm_lock["packages"]["node_modules/markdownlint-cli2"]["version"]
        != markdownlint_version
    ):
        errors.append("markdownlint-cli2 package and lock versions differ")
    manifest = tomllib.loads(
        (ROOT / "examples/hello-service/foundation.toml").read_text(encoding="utf-8")
    )
    versions = {
        "foundation package": foundation_version,
        "Python project": pyproject["project"]["version"],
        "reference manifest": manifest["project"]["version"],
    }
    if len(set(versions.values())) != 1:
        errors.append(f"foundation versions are inconsistent: {versions}")
    for lockfile in sorted(ROOT.glob("**/conan/locks/*.lock")):
        lock = json.loads(lockfile.read_text(encoding="utf-8"))
        for reference in lock.get("requires", []):
            if "#" not in reference:
                errors.append(f"Conan recipe revision is not pinned: {lockfile}")
            if "%" in reference:
                errors.append(
                    f"Conan lock contains a remote-specific timestamp: {lockfile}"
                )
    if errors:
        print(*errors, sep="\n", file=sys.stderr)
        return 1
    print("repository governance: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
