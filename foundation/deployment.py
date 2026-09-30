from __future__ import annotations

import fcntl
import os
import shutil
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .common import FoundationError, atomic_json, load_json, run_command
from .manifest import load_manifest
from .release import extract_verified_release


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

    def _link_target(self, link: Path) -> Path | None:
        if not link.is_symlink():
            if link.exists():
                raise FoundationError(
                    f"managed deployment pointer is not a link: {link}"
                )
            return None
        target = link.resolve()
        try:
            target.relative_to(self.deployments)
        except ValueError as exc:
            raise FoundationError(
                f"managed deployment pointer escapes deployment root: {link}"
            ) from exc
        if not target.is_dir():
            raise FoundationError(f"managed deployment pointer is dangling: {link}")
        return target

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

    @staticmethod
    def _run_recovery_hook(release: Path, hook: str) -> dict[str, Any]:
        try:
            return DeploymentManager._run_hook(release, hook, check=False)
        except Exception as exc:
            return {
                "hook": hook,
                "status": "failed",
                "returncode": -1,
                "error": str(exc),
            }

    @staticmethod
    def _run_deployment_recovery_hook(deployment: Path, hook: str) -> dict[str, Any]:
        try:
            record = load_json(deployment / "record.json")
            release = Path(record["release_path"])
        except (FoundationError, KeyError, TypeError) as exc:
            return {
                "hook": hook,
                "status": "failed",
                "returncode": -1,
                "error": str(exc),
            }
        return DeploymentManager._run_recovery_hook(release, hook)

    def install(self, archive: Path, checksum: Path | None = None) -> dict[str, Any]:
        if checksum is None:
            raise FoundationError("deployment install requires a release checksum")
        staging = self.releases / f".install-{os.getpid()}-{time.monotonic_ns()}"
        try:
            verification = extract_verified_release(archive, staging, checksum)
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
            if release.exists():
                raise FoundationError(f"release path already exists: {release}")
            os.replace(staging, release)
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
        finally:
            shutil.rmtree(staging, ignore_errors=True)

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

    def _unfinished_transactions(self) -> list[tuple[Path, dict[str, Any]]]:
        unfinished = []
        for record_path in sorted(self.transactions.glob("*/record.json")):
            record = load_json(record_path)
            if not isinstance(record, dict):
                raise FoundationError(
                    f"deployment transaction must be an object: {record_path}"
                )
            if record.get("status") == "started":
                unfinished.append((record_path.parent, record))
        return unfinished

    def _require_recovered(self) -> None:
        unfinished = self._unfinished_transactions()
        if unfinished:
            identifiers = ", ".join(
                str(record.get("transaction_id", path.name))
                for path, record in unfinished
            )
            raise FoundationError(
                f"unfinished deployment transaction(s): {identifiers}; run deploy recover"
            )

    def _activate(self, deployment: Path, operation: str) -> dict[str, Any]:
        self._require_recovered()
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
            candidate_cleanup = self._run_recovery_hook(candidate_release, "deactivate")
            self._atomic_link(self.current, old_current)
            recovery = None
            if old_current is not None:
                recovery = self._run_deployment_recovery_hook(old_current, "activate")
            recovery_failures = [
                summary
                for summary in (candidate_cleanup, recovery)
                if summary is not None and summary["returncode"] != 0
            ]
            transaction.update(
                {
                    "status": "started" if recovery_failures else "rolled_back",
                    "failure": str(exc),
                    "hooks": hooks,
                    "candidate_cleanup": candidate_cleanup,
                    "recovery": recovery,
                    "protected_state_deleted": False,
                }
            )
            if recovery_failures:
                transaction["recovery_failure"] = "; ".join(
                    f"{summary['hook']} hook returned {summary['returncode']}"
                    for summary in recovery_failures
                )
            else:
                transaction["completed_at"] = _now()
            atomic_json(tx_path / "record.json", transaction)
            if recovery_failures:
                raise FoundationError(
                    f"{exc}; automatic recovery incomplete: "
                    f"{transaction['recovery_failure']}"
                ) from exc
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

    def recover(self) -> dict[str, Any]:
        unfinished = self._unfinished_transactions()
        if not unfinished:
            raise FoundationError("there is no unfinished deployment transaction")
        if len(unfinished) != 1:
            raise FoundationError(
                "recovery requires exactly one unfinished deployment transaction"
            )
        tx_path, transaction = unfinished[0]
        required = {
            "schema_version": 1,
            "status": "started",
        }
        for key, value in required.items():
            if transaction.get(key) != value:
                raise FoundationError(f"invalid deployment transaction {key}")
        transaction_id = transaction.get("transaction_id")
        if transaction_id != tx_path.name:
            raise FoundationError("deployment transaction id does not match its path")
        if transaction.get("operation") not in {"deploy", "upgrade", "rollback"}:
            raise FoundationError("invalid deployment transaction operation")

        candidate_id = transaction.get("candidate")
        if not isinstance(candidate_id, str):
            raise FoundationError("deployment transaction candidate is invalid")
        candidate = self._deployment_path(candidate_id)

        old_id = transaction.get("from_current")
        if old_id is not None and not isinstance(old_id, str):
            raise FoundationError("deployment transaction from_current is invalid")
        old_current = self._deployment_path(old_id) if old_id is not None else None
        previous_id = transaction.get("from_previous")
        if previous_id is not None and not isinstance(previous_id, str):
            raise FoundationError("deployment transaction from_previous is invalid")
        old_previous = (
            self._deployment_path(previous_id) if previous_id is not None else None
        )

        current = self._link_target(self.current)
        self._link_target(self.previous)
        if current not in {candidate, old_current}:
            observed = current.name if current else "none"
            raise FoundationError(
                f"current deployment diverged during recovery: {observed}"
            )

        candidate_cleanup = self._run_deployment_recovery_hook(candidate, "deactivate")
        self._atomic_link(self.current, old_current)
        self._atomic_link(self.previous, old_previous)
        recovery = None
        if old_current is not None:
            recovery = self._run_deployment_recovery_hook(old_current, "activate")

        failures = [
            summary
            for summary in (candidate_cleanup, recovery)
            if summary is not None and summary["returncode"] != 0
        ]
        transaction.update(
            {
                "recovery_attempted_at": _now(),
                "candidate_cleanup": candidate_cleanup,
                "recovery": recovery,
                "protected_state_deleted": False,
            }
        )
        if failures:
            transaction["recovery_failure"] = "; ".join(
                f"{summary['hook']} hook returned {summary['returncode']}"
                for summary in failures
            )
            atomic_json(tx_path / "record.json", transaction)
            raise FoundationError(transaction["recovery_failure"])
        transaction.update(
            {
                "status": "recovered",
                "completed_at": _now(),
                "current": old_current.name if old_current else None,
                "previous": old_previous.name if old_previous else None,
            }
        )
        transaction.pop("recovery_failure", None)
        atomic_json(tx_path / "record.json", transaction)
        return transaction

    def deploy(self, deployment_id: str) -> dict[str, Any]:
        self._require_recovered()
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
        self._require_recovered()
        deployment = self._deployment_path(deployment_id)
        if self._link_target(self.current) == deployment:
            raise FoundationError(
                "candidate is already current; use deploy for idempotent verify"
            )
        return self._activate(deployment, "upgrade")

    def rollback(self) -> dict[str, Any]:
        self._require_recovered()
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
        unfinished = [
            record.get("transaction_id", path.name)
            for path, record in self._unfinished_transactions()
        ]
        return {
            "schema_version": 1,
            "overall_pass": current is not None and not unfinished,
            "current": current.name if current else None,
            "previous": previous.name if previous else None,
            "unfinished_transactions": unfinished,
            "protected_state_deleted": False,
        }
