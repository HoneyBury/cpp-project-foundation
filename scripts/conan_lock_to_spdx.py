#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from foundation.sbom import conan_lock_to_spdx

    parser = argparse.ArgumentParser(
        description="Convert a Conan lock into a scan-ready SPDX SBOM."
    )
    parser.add_argument("--lockfile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = conan_lock_to_spdx(args.lockfile, args.output)
    print(f"Conan SPDX dependencies: {result['dependency_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
