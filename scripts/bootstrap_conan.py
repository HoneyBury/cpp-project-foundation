#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def run(command: list[str], home: Path) -> None:
    subprocess.run(command, env={**os.environ, "CONAN_HOME": str(home)}, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure a repository-scoped Conan home."
    )
    parser.add_argument("--conan-home", type=Path, required=True)
    parser.add_argument("--remotes", type=Path)
    parser.add_argument("--no-remote", action="store_true")
    args = parser.parse_args()
    args.conan_home.mkdir(parents=True, exist_ok=True)
    run(["conan", "profile", "detect", "--force"], args.conan_home)
    run(["conan", "remote", "disable", "*"], args.conan_home)
    if not args.no_remote:
        remotes = [{"name": "conancenter", "url": "https://center2.conan.io"}]
        if args.remotes:
            remotes = json.loads(args.remotes.read_text(encoding="utf-8"))["remotes"]
        for remote in remotes:
            run(
                [
                    "conan",
                    "remote",
                    "add",
                    str(remote["name"]),
                    str(remote["url"]),
                    "--force",
                ],
                args.conan_home,
            )
            run(["conan", "remote", "enable", str(remote["name"])], args.conan_home)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
