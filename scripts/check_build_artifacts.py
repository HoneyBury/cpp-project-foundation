#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from foundation.build_quality import main as check_build

    return check_build()


if __name__ == "__main__":
    raise SystemExit(main())
