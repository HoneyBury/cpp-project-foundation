from __future__ import annotations

import os
import re
import shutil
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .common import (
    FoundationError,
    atomic_json,
    load_json,
    relative_path,
    sha256_file,
)

VALID_KINDS = {"daily", "weekly", "incident", "final", "release", "deployment"}


def _snapshot_matches(path: Path, digest: str, size: int) -> bool:
    return (
        not path.is_symlink()
        and path.is_file()
        and path.stat().st_size == size
        and sha256_file(path) == digest
    )


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
    if not summaries:
        raise FoundationError("at least one evidence summary is required")
    if attributes is not None and not isinstance(attributes, dict):
        raise FoundationError("evidence attributes must be an object")
    references = []
    for summary in summaries:
        if not summary.is_file():
            raise FoundationError(f"evidence summary not found: {summary}")
        if summary.is_symlink() or summary.name in {"", ".", ".."}:
            raise FoundationError(f"evidence summary must be a regular file: {summary}")
        digest = sha256_file(summary)
        source_size = summary.stat().st_size
        relative_snapshot = Path("raw") / digest[:2] / f"{digest}-{summary.name}"
        destination = relative_path(
            root,
            relative_snapshot.as_posix(),
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if not _snapshot_matches(destination, digest, source_size):
                raise FoundationError(
                    f"existing evidence snapshot is invalid: {destination}"
                )
        else:
            handle, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", dir=destination.parent
            )
            os.close(handle)
            temporary = Path(temporary_name)
            try:
                shutil.copy2(summary, temporary)
                if not _snapshot_matches(temporary, digest, source_size):
                    raise FoundationError("evidence snapshot changed while copying")
                try:
                    os.link(temporary, destination)
                except FileExistsError:
                    if not _snapshot_matches(destination, digest, source_size):
                        raise FoundationError(
                            f"existing evidence snapshot is invalid: {destination}"
                        ) from None
            finally:
                temporary.unlink(missing_ok=True)
        references.append(
            {
                "source_name": summary.name,
                "snapshot": relative_snapshot.as_posix(),
                "sha256": digest,
                "size_bytes": source_size,
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
        "attributes": attributes if attributes is not None else {},
        "secret_material_recorded": False,
    }
    path = relative_path(root, f"records/{kind}/{record_id}.json")
    atomic_json(path, record, create_only=True)
    return {**record, "path": str(path)}


def verify_evidence(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    records = 0
    expected_files: set[Path] = set()
    required_fields = {
        "schema_version",
        "kind",
        "record_id",
        "recorded_at",
        "summaries",
        "attributes",
        "secret_material_recorded",
    }
    for record_path in sorted((root / "records").glob("*/*.json")):
        records += 1
        expected_files.add(record_path.resolve())
        try:
            record = load_json(record_path)
            if not isinstance(record, dict) or set(record) != required_fields:
                raise FoundationError("record must contain exactly the schema fields")
            if record["schema_version"] != 1:
                raise FoundationError("schema_version must be 1")
            kind = record["kind"]
            if kind not in VALID_KINDS or kind != record_path.parent.name:
                raise FoundationError("kind does not match the record path")
            record_id = record["record_id"]
            if (
                not isinstance(record_id, str)
                or not record_id
                or Path(record_id).name != record_id
                or f"{record_id}.json" != record_path.name
            ):
                raise FoundationError("record_id does not match the record path")
            if not isinstance(record["recorded_at"], str) or not record["recorded_at"]:
                raise FoundationError("recorded_at must be a non-empty string")
            try:
                recorded_at = datetime.fromisoformat(
                    record["recorded_at"].replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise FoundationError(
                    "recorded_at must be an ISO-8601 timestamp"
                ) from exc
            if recorded_at.tzinfo is None:
                raise FoundationError("recorded_at must include a timezone")
            if not isinstance(record["attributes"], dict):
                raise FoundationError("attributes must be an object")
            if record["secret_material_recorded"] is not False:
                raise FoundationError("secret_material_recorded must be false")
            summaries = record["summaries"]
            if not isinstance(summaries, list) or not summaries:
                raise FoundationError("summaries must be a non-empty array")
            for reference in summaries:
                if not isinstance(reference, dict) or set(reference) != {
                    "source_name",
                    "snapshot",
                    "sha256",
                    "size_bytes",
                }:
                    raise FoundationError("summary reference has invalid fields")
                source_name = reference["source_name"]
                digest = reference["sha256"]
                size = reference["size_bytes"]
                if (
                    not isinstance(source_name, str)
                    or source_name in {"", ".", ".."}
                    or Path(source_name).name != source_name
                    or not isinstance(digest, str)
                    or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                    or isinstance(size, bool)
                    or not isinstance(size, int)
                    or size < 0
                ):
                    raise FoundationError("summary reference metadata is invalid")
                expected = Path("raw") / digest[:2] / f"{digest}-{source_name}"
                if reference["snapshot"] != expected.as_posix():
                    raise FoundationError("snapshot is not content-addressed")
                snapshot = relative_path(root, reference["snapshot"], must_exist=True)
                if snapshot.is_symlink() or not snapshot.is_file():
                    raise FoundationError("snapshot must be a regular file")
                expected_files.add(snapshot.resolve())
                if snapshot.stat().st_size != size or sha256_file(snapshot) != digest:
                    raise FoundationError("snapshot size or digest does not match")
        except (FoundationError, KeyError, TypeError) as exc:
            errors.append(f"invalid record {record_path}: {exc}")

    if root.exists():
        for path in root.rglob("*"):
            if path.is_symlink():
                errors.append(f"symbolic link is not allowed: {path}")
            elif not (path.is_dir() or path.is_file()):
                errors.append(f"special file is not allowed: {path}")
            elif path.is_file() and path.resolve() not in expected_files:
                errors.append(f"unexpected evidence file: {path}")
    return {
        "schema_version": 1,
        "overall_pass": not errors and records > 0,
        "record_count": records,
        "errors": errors,
    }


def package_evidence(root: Path, output: Path) -> dict[str, Any]:
    try:
        output.resolve().relative_to(root.resolve())
    except ValueError:
        pass
    else:
        raise FoundationError("evidence package must be outside the evidence root")
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
