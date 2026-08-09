from __future__ import annotations

import fcntl
import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .common import FoundationError, atomic_json, load_json, run_command
from .manifest import load_manifest
from .release import extract_verified_release, verify_release


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class DeploymentManager:
    def __init__(self, root: Path, state_root: Path):
        self.root = root.resolve()
        self.state_root = state_root.resolve()
        self.releases = self.root / "releases"
        self.deployments = self.root / "deployments"
        self.current = self.root / "current"
        self.previous = self.root / "previous"
        self.transactions = self.state_root / "transactions"
        for path in (self.releases, self.deployments, self.transactions):
            path.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def locked(self):
        lock_path = self.state_root / "deployment.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+", encoding="utf-8") as stream:
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise FoundationError(
                    "another deployment operation holds the lock"
                ) from exc
            yield

    def _deployment_path(self, deployment_id: str) -> Path:
        if not deployment_id or Path(deployment_id).name != deployment_id:
            raise FoundationError("invalid deployment id")
        path = (self.deployments / deployment_id).resolve()
        try:
            path.relative_to(self.deployments)
        except ValueError as exc:
            raise FoundationError("deployment escapes managed root") from exc
        if not path.is_dir():
            raise FoundationError(f"unknown deployment: {deployment_id}")
        return path

    @staticmethod
    def _link_target(link: Path) -> Path | None:
        if not link.is_symlink():
            return None
        return link.resolve()

    @staticmethod
    def _atomic_link(link: Path, target: Path | None) -> None:
        temporary = link.parent / f".{link.name}.new-{os.getpid()}"
        temporary.unlink(missing_ok=True)
        if target is None:
            link.unlink(missing_ok=True)
            return
        os.symlink(target, temporary)
        os.replace(temporary, link)

    @staticmethod
    def _run_hook(release: Path, hook: str, *, check: bool = True) -> dict[str, Any]:
        manifest = load_manifest(release / "foundation.toml")
        command = manifest.hook(hook)
        if not command:
            return {"hook": hook, "status": "skipped", "returncode": 0}
        started = time.monotonic()
        result = run_command(
            command,
            cwd=release,
            env={"FOUNDATION_RELEASE_DIR": str(release)},
            timeout=float(manifest.operations.get("hook_timeout_seconds", 300)),
            check=False,
        )
        summary = {
            "hook": hook,
            "status": "passed" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "stdout_tail": result.stdout[-2000:],
            "stderr_tail": result.stderr[-2000:],
        }
        if check and result.returncode != 0:
            raise FoundationError(f"{hook} hook failed: {summary['stderr_tail']}")
        return summary

    def install(self, archive: Path, checksum: Path | None = None) -> dict[str, Any]:
        verification = verify_release(archive, checksum)
        digest = verification["archive_sha256"]
        deployment_id = (
            f"v{verification['version']}-{digest[:12]}-{verification['platform']}"
        )
        deployment = self.deployments / deployment_id
        if deployment.exists():
            existing = load_json(deployment / "record.json")
            if existing.get("archive_sha256") != digest:
                raise FoundationError(
                    "existing deployment id has a different archive digest"
                )
            return {**existing, "idempotent": True}
        release = self.releases / deployment_id
        extract_verified_release(archive, release)
        deployment.mkdir()
        record = {
            "schema_version": 1,
            "deployment_id": deployment_id,
            "project": verification["project"],
            "version": verification["version"],
            "platform": verification["platform"],
            "archive_sha256": digest,
            "release_path": str(release),
            "installed_at": _now(),
            "status": "installed",
            "protected_state_deleted": False,
        }
        atomic_json(deployment / "record.json", record, create_only=True)
        return record

    def _transaction(
        self, operation: str, payload: dict[str, Any]
    ) -> tuple[Path, dict[str, Any]]:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        transaction_id = f"{stamp}-{operation}-{os.getpid()}"
        path = self.transactions / transaction_id
        path.mkdir()
        record = {
            "schema_version": 1,
            "transaction_id": transaction_id,
            "operation": operation,
            "started_at": _now(),
            "status": "started",
            **payload,
        }
        atomic_json(path / "record.json", record)
        return path, record

    def _activate(self, deployment: Path, operation: str) -> dict[str, Any]:
        candidate_record = load_json(deployment / "record.json")
        candidate_release = Path(candidate_record["release_path"])
        old_current = self._link_target(self.current)
        old_previous = self._link_target(self.previous)
        tx_path, transaction = self._transaction(
            operation,
            {
                "candidate": deployment.name,
                "from_current": old_current.name if old_current else None,
                "from_previous": old_previous.name if old_previous else None,
            },
        )
        self._atomic_link(self.current, deployment)
        hooks: list[dict[str, Any]] = []
        try:
            hooks.append(self._run_hook(candidate_release, "activate"))
            hooks.append(self._run_hook(candidate_release, "verify"))
        except Exception as exc:
            candidate_cleanup = self._run_hook(
                candidate_release, "deactivate", check=False
            )
            self._atomic_link(self.current, old_current)
            recovery = None
            if old_current is not None:
                previous_record = load_json(old_current / "record.json")
                recovery = self._run_hook(
                    Path(previous_record["release_path"]), "activate", check=False
                )
            transaction.update(
                {
                    "status": "rolled_back",
                    "completed_at": _now(),
                    "failure": str(exc),
                    "hooks": hooks,
                    "candidate_cleanup": candidate_cleanup,
                    "recovery": recovery,
                    "protected_state_deleted": False,
                }
            )
            atomic_json(tx_path / "record.json", transaction)
            raise
        if old_current is not None and old_current != deployment:
            self._atomic_link(self.previous, old_current)
        candidate_record["status"] = "verified"
        candidate_record["verified_at"] = _now()
        atomic_json(deployment / "record.json", candidate_record)
        transaction.update(
            {
                "status": "passed",
                "completed_at": _now(),
                "current": deployment.name,
                "previous": old_current.name if old_current else None,
                "hooks": hooks,
                "protected_state_deleted": False,
            }
        )
        atomic_json(tx_path / "record.json", transaction)
        return transaction

    def deploy(self, deployment_id: str) -> dict[str, Any]:
        deployment = self._deployment_path(deployment_id)
        if self._link_target(self.current) == deployment:
            record = load_json(deployment / "record.json")
            verification = self._run_hook(Path(record["release_path"]), "verify")
            return {
                "schema_version": 1,
                "operation": "deploy",
                "current": deployment_id,
                "idempotent": True,
                "verification": verification,
                "status": "passed",
            }
        return self._activate(deployment, "deploy")

    def upgrade(self, deployment_id: str) -> dict[str, Any]:
        deployment = self._deployment_path(deployment_id)
        if self._link_target(self.current) == deployment:
            raise FoundationError(
                "candidate is already current; use deploy for idempotent verify"
            )
        return self._activate(deployment, "upgrade")

    def rollback(self) -> dict[str, Any]:
        previous = self._link_target(self.previous)
        current = self._link_target(self.current)
        if previous is None or current is None or previous == current:
            raise FoundationError(
                "rollback requires distinct current and previous deployments"
            )
        result = self._activate(previous, "rollback")
        self._atomic_link(self.previous, current)
        result["previous"] = current.name
        transaction = self.transactions / result["transaction_id"] / "record.json"
        atomic_json(transaction, result)
        return result

    def verify(self) -> dict[str, Any]:
        current = self._link_target(self.current)
        if current is None:
            raise FoundationError("there is no current deployment")
        record = load_json(current / "record.json")
        verification = self._run_hook(Path(record["release_path"]), "verify")
        return {
            "schema_version": 1,
            "overall_pass": True,
            "current": current.name,
            "archive_sha256": record["archive_sha256"],
            "verification": verification,
        }

    def status(self) -> dict[str, Any]:
        current = self._link_target(self.current)
        previous = self._link_target(self.previous)
        unfinished = []
        for record_path in sorted(self.transactions.glob("*/record.json")):
            record = load_json(record_path)
            if record.get("status") == "started":
                unfinished.append(record.get("transaction_id"))
        return {
            "schema_version": 1,
            "overall_pass": current is not None and not unfinished,
            "current": current.name if current else None,
            "previous": previous.name if previous else None,
            "unfinished_transactions": unfinished,
            "protected_state_deleted": False,
        }
