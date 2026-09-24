#!/usr/bin/env python3
"""Create a local Python environment and install cpp-project-foundation."""

from __future__ import annotations

import argparse
import subprocess
import sys
import venv
from pathlib import Path


def main() -> int:
    if sys.version_info < (3, 11):  # noqa: UP036 - provide a clear runtime message
        raise SystemExit(
            "bootstrap_dev.py requires Python 3.11 or newer; "
            f"detected Python {sys.version_info.major}.{sys.version_info.minor}."
        )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv", type=Path, default=Path(".venv"))
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="create the virtual environment without installing the package",
    )
    args = parser.parse_args()
    venv_dir = args.venv.resolve()
    python = venv_dir / "bin/python"
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(venv_dir)
    if not args.skip_install:
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-e",
                ".",
            ],
            check=True,
        )
    print(f"virtual environment: {venv_dir}")
    print(f"activate with: source {venv_dir}/bin/activate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
