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
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
FOUNDATION_VERSION_RE = re.compile(r"v\d+\.\d+\.\d+\Z")


def main() -> int:
    errors = []
    required = [
        ".github/CODEOWNERS",
        "CONTRIBUTING.md",
        "README.md",
        "README.zh-CN.md",
        "SECURITY.md",
        ".github/workflows/ci.yml",
        ".github/workflows/security.yml",
        ".github/workflows/release.yml",
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
    workflows = sorted(ROOT.glob("**/.github/workflows/*.yml"))
    for workflow in workflows:
        text = workflow.read_text(encoding="utf-8")
        if "permissions:" not in text:
            errors.append(f"workflow has no explicit permissions: {workflow.name}")
        for action, revision in ACTION_RE.findall(text):
            if action.startswith("./"):
                continue
            if action.startswith(
                "HoneyBury/cpp-project-foundation/"
            ) and FOUNDATION_VERSION_RE.fullmatch(revision):
                continue
            if SHA_RE.fullmatch(revision) is None:
                errors.append(
                    f"action is not pinned to a full SHA: {action}@{revision}"
                )
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    for requirement in pyproject["build-system"]["requires"]:
        if "==" not in requirement:
            errors.append(
                f"Python build dependency is not exactly pinned: {requirement}"
            )
    manifest = tomllib.loads(
        (ROOT / "examples/hello-service/foundation.toml").read_text(encoding="utf-8")
    )
    versions = {
        "foundation package": runpy.run_path(ROOT / "foundation/__init__.py")[
            "__version__"
        ],
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
