from __future__ import annotations

import shutil
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .common import FoundationError, atomic_json, load_json, sha256_file

VALID_KINDS = {"daily", "weekly", "incident", "final", "release", "deployment"}


def record_evidence(
    root: Path,
    *,
    kind: str,
    record_id: str,
    summaries: list[Path],
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if kind not in VALID_KINDS:
        raise FoundationError(f"unsupported evidence kind: {kind}")
    if not record_id or Path(record_id).name != record_id:
        raise FoundationError("record id must be a single path component")
    raw_root = root / "raw"
    references = []
    for summary in summaries:
        if not summary.is_file():
            raise FoundationError(f"evidence summary not found: {summary}")
        digest = sha256_file(summary)
        destination = raw_root / digest[:2] / f"{digest}-{summary.name}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            shutil.copy2(summary, temporary)
            if sha256_file(temporary) != digest:
                raise FoundationError("evidence snapshot changed while copying")
            temporary.replace(destination)
        references.append(
            {
                "source_name": summary.name,
                "snapshot": str(destination.relative_to(root)),
                "sha256": digest,
                "size_bytes": summary.stat().st_size,
            }
        )
    record = {
        "schema_version": 1,
        "kind": kind,
        "record_id": record_id,
        "recorded_at": datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "summaries": references,
        "attributes": attributes or {},
        "secret_material_recorded": False,
    }
    path = root / "records" / kind / f"{record_id}.json"
    atomic_json(path, record, create_only=True)
    return {**record, "path": str(path)}


def verify_evidence(root: Path) -> dict[str, Any]:
    errors = []
    records = 0
    for record_path in sorted((root / "records").glob("*/*.json")):
        records += 1
        record = load_json(record_path)
        for reference in record.get("summaries", []):
            snapshot = root / str(reference.get("snapshot", ""))
            if not snapshot.is_file() or sha256_file(snapshot) != reference.get(
                "sha256"
            ):
                errors.append(f"invalid snapshot for {record_path}: {snapshot}")
    return {
        "schema_version": 1,
        "overall_pass": not errors and records > 0,
        "record_count": records,
        "errors": errors,
    }


def package_evidence(root: Path, output: Path) -> dict[str, Any]:
    verification = verify_evidence(root)
    if not verification["overall_pass"]:
        raise FoundationError("evidence tree is not valid")
    if output.exists():
        raise FoundationError(f"evidence package already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as stream:
        stream.add(root, arcname="evidence", recursive=True)
    digest = sha256_file(output)
    checksum = output.with_suffix(output.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    return {
        "schema_version": 1,
        "overall_pass": True,
        "archive": str(output),
        "sha256": digest,
        "record_count": verification["record_count"],
        "off_host_copy_verified": False,
    }
