from __future__ import annotations

import os
import stat
import subprocess
import tarfile
import tempfile
import unittest
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from foundation.common import FoundationError, atomic_json
from foundation.deployment import DeploymentManager
from foundation.evidence import package_evidence, record_evidence, verify_evidence
from foundation.manifest import load_manifest
from foundation.operations import (
    aggregate_canary,
    create_backup,
    restore_backup,
    run_canary,
    run_performance,
    run_soak,
    verify_backup,
)
from foundation.release import package_release, verify_release
from foundation.scaffold import initialize_project


def write(path: Path, text: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR)


def make_project(root: Path, version: str = "1.0.0", exit_code: int = 0) -> Path:
    write(root / "conan/profiles/linux", "[settings]\nos=Linux\n")
    write(root / "conan/locks/release.lock", '{"version":"0.5"}\n')
    write(
        root / "build/release/bin/sample-service",
        f'#!/bin/sh\nif [ "${{1:-}}" = --benchmark ]; then echo \'{{"ops_per_second":200000,"p99_ms":0.1}}\'; exit 0; fi\nexit {exit_code}\n',
        executable=True,
    )
    write(
        root / "foundation.toml",
        f'''schema_version = 1
[project]
name = "sample-service"
version = "{version}"
[build]
target = "sample_service"
test_target = "sample_tests"
profile = "conan/profiles/linux"
lockfile = "conan/locks/release.lock"
[release]
executables = ["build/release/bin/sample-service"]
[operations]
activate = []
verify = ["bin/sample-service", "--check"]
deactivate = []
canary = ["build/release/bin/sample-service", "--check"]
benchmark = ["build/release/bin/sample-service", "--benchmark"]
''',
    )
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
    return root / "foundation.toml"


class ManifestTests(unittest.TestCase):
    def test_reference_manifest_is_valid(self) -> None:
        manifest = load_manifest(Path("examples/hello-service/foundation.toml"))
        self.assertEqual(manifest.name, "hello-service")
        self.assertEqual(manifest.build["target"], "hello_service")

    def test_manifest_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            make_project(root)
            text = (root / "foundation.toml").read_text(encoding="utf-8")
            (root / "foundation.toml").write_text(
                text.replace(
                    'profile = "conan/profiles/linux"', 'profile = "../profile"'
                ),
                encoding="utf-8",
            )
            with self.assertRaises(FoundationError):
                load_manifest(root / "foundation.toml")

    def test_scaffold_creates_independent_project(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            output = Path(name) / "order-service"
            result = initialize_project("order-service", "1.2.3", output)
            self.assertTrue(result["overall_pass"])
            manifest = load_manifest(output / "foundation.toml")
            self.assertEqual(manifest.name, "order-service")
            self.assertIn(
                "project(order_service", (output / "CMakeLists.txt").read_text()
            )
            self.assertFalse((output / "build").exists())
            self.assertTrue((output / "deploy/order-service.service").is_file())
            self.assertTrue(
                (output / "include/order_service/request_parser.h").is_file()
            )
            workflow = (output / ".github/workflows/ci.yml").read_text(encoding="utf-8")
            self.assertIn("@v0.1.1", workflow)
            self.assertNotIn("@v1.2.3", workflow)
            operations_workflow = (
                output / ".github/workflows/operations.yml"
            ).read_text(encoding="utf-8")
            self.assertNotIn("self-hosted", operations_workflow)
            generated_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in output.rglob("*")
                if path.is_file()
            )
            self.assertNotIn("hello", generated_text.lower())


class ReleaseAndDeploymentTests(unittest.TestCase):
    def package(
        self, parent: Path, version: str, exit_code: int = 0
    ) -> tuple[Path, Path]:
        root = parent / f"source-{version}-{exit_code}"
        root.mkdir()
        manifest = load_manifest(make_project(root, version, exit_code))
        output = parent / f"dist-{version}-{exit_code}"
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        with patch.dict(os.environ, {"FOUNDATION_CANDIDATE_REVISION": commit}):
            result = package_release(manifest, output)
        return Path(result["archive"]), Path(result["checksum"])

    def test_package_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            archive, checksum = self.package(Path(name), "1.0.0")
            result = verify_release(archive, checksum)
            self.assertTrue(result["overall_pass"])
            self.assertGreater(result["file_count"], 3)
            with tarfile.open(archive, "r:gz") as stream:
                sbom_member = next(
                    member
                    for member in stream.getmembers()
                    if member.name.endswith("/sbom.spdx.json")
                )
                sbom = json.load(stream.extractfile(sbom_member))
            self.assertEqual(sbom["documentDescribes"], ["SPDXRef-Package"])

    def test_checksum_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            archive, checksum = self.package(Path(name), "1.0.0")
            with archive.open("ab") as stream:
                stream.write(b"tamper")
            with self.assertRaises(FoundationError):
                verify_release(archive, checksum)

    def test_archive_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            archive = Path(name) / "bad.tar.gz"
            payload = Path(name) / "payload"
            payload.write_text("x", encoding="utf-8")
            with tarfile.open(archive, "w:gz") as stream:
                stream.add(payload, arcname="../escape")
            with self.assertRaises(FoundationError):
                verify_release(archive)

    def test_upgrade_rollback_and_failed_candidate_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            parent = Path(name)
            first_archive, first_checksum = self.package(parent, "1.0.0")
            second_archive, second_checksum = self.package(parent, "1.1.0")
            bad_archive, bad_checksum = self.package(parent, "1.2.0", 7)
            manager = DeploymentManager(parent / "opt", parent / "state")
            first = manager.install(first_archive, first_checksum)
            manager.deploy(first["deployment_id"])
            second = manager.install(second_archive, second_checksum)
            manager.upgrade(second["deployment_id"])
            self.assertEqual(manager.status()["current"], second["deployment_id"])
            manager.rollback()
            self.assertEqual(manager.status()["current"], first["deployment_id"])
            bad = manager.install(bad_archive, bad_checksum)
            with self.assertRaises(FoundationError):
                manager.upgrade(bad["deployment_id"])
            status = manager.status()
            self.assertTrue(status["overall_pass"])
            self.assertEqual(status["current"], first["deployment_id"])


class OperationsTests(unittest.TestCase):
    def test_evidence_is_create_only_and_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            summary = root / "summary.json"
            atomic_json(summary, {"overall_pass": True})
            evidence = root / "evidence"
            record_evidence(
                evidence,
                kind="daily",
                record_id="2026-08-09",
                summaries=[summary],
            )
            with self.assertRaises(FoundationError):
                record_evidence(
                    evidence,
                    kind="daily",
                    record_id="2026-08-09",
                    summaries=[summary],
                )
            self.assertTrue(verify_evidence(evidence)["overall_pass"])
            package = package_evidence(evidence, root / "evidence.tar.gz")
            self.assertFalse(package["off_host_copy_verified"])

    def test_backup_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "data"
            write(source / "nested/value.txt", "preserved\n")
            archive = root / "backup.tar.gz"
            summary = create_backup(source, archive, allow_plaintext=True)
            summary_path = archive.with_suffix(archive.suffix + ".json")
            self.assertTrue(verify_backup(archive, summary_path)["overall_pass"])
            destination = root / "restored"
            restore_backup(archive, summary_path, destination)
            self.assertEqual(
                (destination / "nested/value.txt").read_text(), "preserved\n"
            )
            self.assertFalse(summary["encrypted"])

    def test_canary_soak_and_performance(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            manifest = load_manifest(make_project(root))
            evidence = root / "canary"
            end = datetime(2026, 8, 9, 0, 3, tzinfo=UTC)
            for minute in range(3):
                run_canary(
                    manifest,
                    evidence,
                    candidate="candidate-a",
                    now=end - timedelta(minutes=3 - minute),
                )
            aggregate = aggregate_canary(
                evidence,
                end=end,
                duration=timedelta(minutes=3),
                candidate="candidate-a",
            )
            self.assertTrue(aggregate["overall_pass"])
            soak = run_soak(
                manifest,
                root / "soak.json",
                duration_seconds=0.05,
                interval_seconds=0.01,
            )
            self.assertTrue(soak["overall_pass"])
            perf = run_performance(
                manifest,
                root / "perf.json",
                repetitions=3,
                minimum_ops_per_second=100000,
                maximum_p99_ms=1,
            )
            self.assertTrue(perf["overall_pass"])


if __name__ == "__main__":
    unittest.main()
