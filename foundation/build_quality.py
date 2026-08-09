from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def check_build_artifacts(
    baseline_path: Path,
    binary: Path,
    elapsed_file: Path,
    output: Path,
    rebuild_binary: Path | None = None,
) -> dict[str, object]:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    elapsed = float(elapsed_file.read_text(encoding="ascii").strip())
    size = binary.stat().st_size
    binary_digest = _digest(binary)
    rebuild_digest = _digest(rebuild_binary) if rebuild_binary else None
    checks = {
        "build_time": elapsed <= float(baseline["maximum_clean_build_seconds"]),
        "binary_size": size <= int(baseline["maximum_release_binary_bytes"]),
        "reproducible_binary": rebuild_digest is None
        or rebuild_digest == binary_digest,
    }
    summary = {
        "schema_version": 1,
        "overall_pass": all(checks.values()),
        "checks": checks,
        "clean_build_seconds": elapsed,
        "binary_size_bytes": size,
        "binary_sha256": binary_digest,
        "rebuild_binary_sha256": rebuild_digest,
        "baseline": baseline,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check build time, binary size and reproducibility gates."
    )
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--elapsed-file", type=Path, required=True)
    parser.add_argument("--rebuild-binary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = check_build_artifacts(
        args.baseline,
        args.binary,
        args.elapsed_file,
        args.output,
        args.rebuild_binary,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
