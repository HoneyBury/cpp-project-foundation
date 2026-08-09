#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create an isolated, exactly pinned Conan environment."
    )
    parser.add_argument("--venv", type=Path, required=True)
    parser.add_argument("--version", default="2.8.1")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    python = args.venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        if args.offline:
            print("Conan environment is missing in offline mode", file=sys.stderr)
            return 1
        venv.EnvBuilder(with_pip=True, clear=True).create(args.venv)
    check = subprocess.run(
        [str(python), "-c", "import conan; print(conan.__version__)"],
        text=True,
        capture_output=True,
        check=False,
    )
    if check.returncode != 0 or check.stdout.strip() != args.version:
        if args.offline:
            print(
                f"Conan {args.version} is unavailable in the pinned environment",
                file=sys.stderr,
            )
            return 1
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                f"conan=={args.version}",
            ],
            check=True,
        )
    conan = args.venv / ("Scripts/conan.exe" if os.name == "nt" else "bin/conan")
    print(conan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
