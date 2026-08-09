from __future__ import annotations

import json
import os
import shutil
import statistics
import tarfile
import time
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .common import FoundationError, atomic_json, load_json, run_command, sha256_file
from .manifest import FoundationManifest


def _now() -> datetime:
    return datetime.now(UTC)


def create_backup(
    source: Path,
    output: Path,
    *,
    age_recipient: str = "",
    allow_plaintext: bool = False,
) -> dict[str, Any]:
    if not source.is_dir():
        raise FoundationError(f"backup source is not a directory: {source}")
    if output.exists():
        raise FoundationError(f"backup is create-only: {output}")
    if not age_recipient and not allow_plaintext:
        raise FoundationError("production backups require an age recipient")
    output.parent.mkdir(parents=True, exist_ok=True)
    encrypted = bool(age_recipient)
    if encrypted:
        with tempfile.TemporaryDirectory(prefix="cpp-foundation-backup-") as name:
            plain = Path(name) / "backup.tar.gz"
            with tarfile.open(plain, "w:gz", format=tarfile.PAX_FORMAT) as stream:
                stream.add(source, arcname="data", recursive=True)
            run_command(
                [
                    "age",
                    "--recipient",
                    age_recipient,
                    "--output",
                    str(output),
                    str(plain),
                ],
                cwd=source.parent,
            )
    else:
        with tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as stream:
            stream.add(source, arcname="data", recursive=True)
    summary = {
        "schema_version": 1,
        "overall_pass": True,
        "source": str(source),
        "archive": str(output),
        "archive_sha256": sha256_file(output),
        "created_at": _now().isoformat(timespec="seconds").replace("+00:00", "Z"),
        "encrypted": encrypted,
        "encryption": "age" if encrypted else "none-test-only",
    }
    atomic_json(output.with_suffix(output.suffix + ".json"), summary, create_only=True)
    return summary


def _plain_backup(archive: Path, summary: dict[str, Any], age_identity: Path | None):
    if summary.get("encrypted") is not True:
        return archive, None
    if age_identity is None:
        raise FoundationError("encrypted backup verification requires an age identity")
    temporary = tempfile.TemporaryDirectory(prefix="cpp-foundation-decrypt-")
    plain = Path(temporary.name) / "backup.tar.gz"
    run_command(
        [
            "age",
            "--decrypt",
            "--identity",
            str(age_identity),
            "--output",
            str(plain),
            str(archive),
        ],
        cwd=archive.parent,
    )
    return plain, temporary


def verify_backup(
    archive: Path, summary_path: Path, *, age_identity: Path | None = None
) -> dict[str, Any]:
    summary = load_json(summary_path)
    errors = []
    if sha256_file(archive) != summary.get("archive_sha256"):
        errors.append("backup archive digest mismatch")
    temporary = None
    try:
        plain, temporary = _plain_backup(archive, summary, age_identity)
        with tarfile.open(plain, "r:gz") as stream:
            for member in stream.getmembers():
                path = Path(member.name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or member.issym()
                    or member.islnk()
                ):
                    errors.append(f"unsafe backup member: {member.name}")
    except tarfile.TarError as exc:
        errors.append(f"invalid backup archive: {exc}")
    finally:
        if temporary is not None:
            temporary.cleanup()
    return {"schema_version": 1, "overall_pass": not errors, "errors": errors}


def restore_backup(
    archive: Path,
    summary_path: Path,
    destination: Path,
    *,
    age_identity: Path | None = None,
) -> dict[str, Any]:
    verification = verify_backup(archive, summary_path, age_identity=age_identity)
    if not verification["overall_pass"]:
        raise FoundationError("backup verification failed")
    if destination.exists():
        raise FoundationError(f"restore destination must not exist: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.restore-{os.getpid()}"
    temporary.mkdir()
    decrypt_temporary = None
    try:
        summary = load_json(summary_path)
        plain, decrypt_temporary = _plain_backup(archive, summary, age_identity)
        with tarfile.open(plain, "r:gz") as stream:
            stream.extractall(temporary, filter="data")
        shutil.move(str(temporary / "data"), destination)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
        if decrypt_temporary is not None:
            decrypt_temporary.cleanup()
    return {
        "schema_version": 1,
        "overall_pass": True,
        "archive_sha256": sha256_file(archive),
        "destination": str(destination),
    }


def run_canary(
    manifest: FoundationManifest,
    evidence_root: Path,
    *,
    candidate: str,
    timeout: float = 60.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    command = manifest.hook("canary") or manifest.hook("verify")
    instant = (now or _now()).replace(second=0, microsecond=0)
    minute = instant.strftime("%Y%m%dT%H%MZ")
    path = evidence_root / "samples" / f"{minute}.json"
    started = time.monotonic()
    result = run_command(command, cwd=manifest.root, timeout=timeout, check=False)
    sample = {
        "schema_version": 1,
        "project": manifest.name,
        "candidate": candidate,
        "sample_minute": instant.isoformat().replace("+00:00", "Z"),
        "success": result.returncode == 0,
        "latency_ms": round((time.monotonic() - started) * 1000, 3),
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-1000:],
        "stderr_tail": result.stderr[-1000:],
    }
    atomic_json(path, sample, create_only=True)
    return sample


def aggregate_canary(
    evidence_root: Path,
    *,
    end: datetime,
    duration: timedelta,
    candidate: str,
) -> dict[str, Any]:
    start = end - duration
    expected = int(duration.total_seconds() // 60)
    samples = []
    invalid = []
    cursor = start
    while cursor < end:
        path = evidence_root / "samples" / f"{cursor.strftime('%Y%m%dT%H%MZ')}.json"
        if path.is_file():
            sample = load_json(path)
            if sample.get("candidate") != candidate:
                invalid.append(path.name)
            else:
                samples.append(sample)
        cursor += timedelta(minutes=1)
    success = sum(item.get("success") is True for item in samples)
    coverage = len(samples) / expected if expected else 0.0
    availability = success / expected if expected else 0.0
    latencies = sorted(float(item.get("latency_ms", 0)) for item in samples)
    p99 = (
        latencies[min(len(latencies) - 1, int(len(latencies) * 0.99))]
        if latencies
        else None
    )
    return {
        "schema_version": 1,
        "overall_pass": coverage >= 0.999 and availability >= 0.999 and not invalid,
        "candidate": candidate,
        "window_start": start.isoformat().replace("+00:00", "Z"),
        "window_end": end.isoformat().replace("+00:00", "Z"),
        "expected_samples": expected,
        "recorded_samples": len(samples),
        "successful_samples": success,
        "coverage": coverage,
        "availability": availability,
        "p99_ms": p99,
        "invalid_samples": invalid,
    }


def run_soak(
    manifest: FoundationManifest,
    output: Path,
    *,
    duration_seconds: float,
    interval_seconds: float,
) -> dict[str, Any]:
    if duration_seconds <= 0 or interval_seconds <= 0:
        raise FoundationError("soak duration and interval must be positive")
    command = manifest.hook("canary") or manifest.hook("verify")
    start = time.monotonic()
    samples = []
    while True:
        scheduled = start + len(samples) * interval_seconds
        delay = scheduled - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        if time.monotonic() - start >= duration_seconds and samples:
            break
        sample_start = time.monotonic()
        result = run_command(
            command, cwd=manifest.root, timeout=interval_seconds, check=False
        )
        samples.append(
            {
                "elapsed_seconds": round(sample_start - start, 3),
                "success": result.returncode == 0,
                "latency_ms": round((time.monotonic() - sample_start) * 1000, 3),
            }
        )
    elapsed = time.monotonic() - start
    summary = {
        "schema_version": 1,
        "overall_pass": all(item["success"] for item in samples)
        and elapsed >= duration_seconds * 0.99,
        "duration_target_seconds": duration_seconds,
        "duration_elapsed_seconds": round(elapsed, 3),
        "sample_count": len(samples),
        "failures": sum(not item["success"] for item in samples),
        "samples": samples,
    }
    atomic_json(output, summary)
    return summary


def run_performance(
    manifest: FoundationManifest,
    output: Path,
    *,
    repetitions: int,
    minimum_ops_per_second: float,
    maximum_p99_ms: float,
) -> dict[str, Any]:
    if repetitions < 1:
        raise FoundationError("performance repetitions must be positive")
    command = manifest.hook("benchmark")
    if not command:
        raise FoundationError("operations.benchmark is required")
    results = []
    for _ in range(repetitions):
        completed = run_command(command, cwd=manifest.root)
        try:
            payload = json.loads(completed.stdout)
            ops = float(payload["ops_per_second"])
            p99 = float(payload["p99_ms"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise FoundationError(
                "benchmark must emit JSON ops_per_second and p99_ms"
            ) from exc
        results.append({"ops_per_second": ops, "p99_ms": p99})
    median_ops = statistics.median(item["ops_per_second"] for item in results)
    max_p99 = max(item["p99_ms"] for item in results)
    summary = {
        "schema_version": 1,
        "overall_pass": median_ops >= minimum_ops_per_second
        and max_p99 <= maximum_p99_ms,
        "repetitions": repetitions,
        "median_ops_per_second": median_ops,
        "maximum_p99_ms": max_p99,
        "gates": {
            "minimum_ops_per_second": minimum_ops_per_second,
            "maximum_p99_ms": maximum_p99_ms,
        },
        "results": results,
    }
    atomic_json(output, summary)
    return summary
