from __future__ import annotations

import json
import os
import stat
import subprocess
import tarfile
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from foundation.build_quality import check_build_artifacts
from foundation.common import FoundationError, atomic_json
from foundation.deployment import DeploymentManager
from foundation.doctor import run_doctor
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
from foundation.reporting import render_operations_report
from foundation.sbom import conan_lock_to_spdx
from foundation.scaffold import initialize_project
from foundation.template_diff import compare_template


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
    def test_build_quality_enforces_size_time_and_reproducibility(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            baseline = root / "baseline.json"
            atomic_json(
                baseline,
                {
                    "maximum_clean_build_seconds": 10,
                    "maximum_release_binary_bytes": 16,
                },
            )
            binary = root / "service-a"
            rebuild = root / "service-b"
            binary.write_bytes(b"deterministic")
            rebuild.write_bytes(b"deterministic")
            elapsed = root / "elapsed.txt"
            elapsed.write_text("1.25\n", encoding="ascii")
            result = check_build_artifacts(
                baseline, binary, elapsed, root / "summary.json", rebuild
            )
            self.assertTrue(result["overall_pass"])
            rebuild.write_bytes(b"different")
            result = check_build_artifacts(
                baseline, binary, elapsed, root / "failed.json", rebuild
            )
            self.assertFalse(result["overall_pass"])

    def test_conan_lock_sbom_contains_scannable_purl(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            lockfile = root / "conan.lock"
            atomic_json(
                lockfile,
                {
                    "version": "0.5",
                    "requires": ["fmt/11.2.0#recipe-revision"],
                },
            )
            output = root / "dependencies.spdx.json"
            result = conan_lock_to_spdx(lockfile, output)
            self.assertEqual(result["dependency_count"], 1)
            sbom = json.loads(output.read_text(encoding="utf-8"))
            reference = sbom["packages"][0]["externalRefs"][0]
            self.assertEqual(reference["referenceLocator"], "pkg:conan/fmt@11.2.0")

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
            with patch("foundation.scaffold.shutil.which", return_value=None):
                result = initialize_project("order-service", "1.2.3", output)
            self.assertTrue(result["overall_pass"])
            manifest = load_manifest(output / "foundation.toml")
            self.assertEqual(manifest.name, "order-service")
            self.assertIn(
                "order_service\n    VERSION 1.2.3",
                (output / "CMakeLists.txt").read_text(),
            )
            self.assertFalse(result["source_formatted"])
            self.assertIn(
                "set_target_properties(\n"
                "    order_service PROPERTIES RUNTIME_OUTPUT_DIRECTORY",
                (output / "CMakeLists.txt").read_text(),
            )
            self.assertFalse((output / "build").exists())
            self.assertTrue((output / ".clang-format").is_file())
            self.assertTrue((output / ".clang-tidy").is_file())
            self.assertTrue((output / ".gitignore").is_file())
            self.assertTrue((output / ".github/dependabot.yml").is_file())
            self.assertTrue((output / "README.md").is_file())
            self.assertTrue((output / ".iwyu.imp").is_file())
            self.assertTrue((output / "quality/baseline.json").is_file())
            self.assertTrue((output / "ruff.toml").is_file())
            self.assertTrue((output / "scripts/install_quality_tools.py").is_file())
            self.assertTrue((output / "deploy/order-service.service").is_file())
            self.assertTrue(
                (output / "include/order_service/request_parser.h").is_file()
            )
            workflow = (output / ".github/workflows/ci.yml").read_text(encoding="utf-8")
            self.assertIn("@v0.4.0", workflow)
            self.assertNotIn("@v1.2.3", workflow)
            operations_workflow = (
                output / ".github/workflows/operations.yml"
            ).read_text(encoding="utf-8")
            self.assertNotIn("self-hosted", operations_workflow)
            quality_workflow = (output / ".github/workflows/quality.yml").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                "coverage-profile: conan/profiles/linux-gcc-x64", quality_workflow
            )
            dependabot = (output / ".github/dependabot.yml").read_text(encoding="utf-8")
            self.assertIn('directory: "/deploy"', dependabot)
            self.assertIn('"version-update:semver-minor"', dependabot)
            generated_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in output.rglob("*")
                if path.is_file()
            )
            self.assertNotIn("hello", generated_text.lower())

    def test_reusable_workflows_separate_conan_environment_and_profiles(self) -> None:
        ci = Path(".github/workflows/reusable-cpp-ci.yml").read_text(encoding="utf-8")
        self.assertIn(
            "env:\n      CONAN_HOME: ${{ github.workspace }}/.conan2\n    steps:",
            ci,
        )
        quality = Path(".github/workflows/reusable-quality.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("coverage-profile:", quality)
        self.assertIn(
            '--profile:host "${{ inputs.conan-profile }}"',
            quality,
        )
        self.assertIn(
            '--profile:host "${{ inputs.coverage-profile }}"',
            quality,
        )

    def test_doctor_reports_contract_and_optional_tool_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            output = Path(name) / "doctor-service"
            with patch("foundation.scaffold.shutil.which", return_value=None):
                initialize_project("doctor-service", "1.2.3", output)

            def available(tool: str) -> str | None:
                return f"/usr/bin/{tool}" if tool in {"git", "cmake"} else None

            with patch("foundation.doctor.shutil.which", side_effect=available):
                result = run_doctor(output, Path("foundation.toml"))
            self.assertTrue(result["overall_pass"])
            self.assertEqual(result["counts"]["fail"], 0)
            self.assertGreater(result["counts"]["warn"], 0)
            statuses = {item["name"]: item["status"] for item in result["checks"]}
            self.assertEqual(statuses["foundation-version"], "pass")
            self.assertEqual(statuses["tool:conan"], "warn")

            with patch("foundation.doctor.shutil.which", side_effect=available):
                strict = run_doctor(output, Path("foundation.toml"), strict_tools=True)
            self.assertFalse(strict["overall_pass"])
            strict_statuses = {
                item["name"]: item["status"] for item in strict["checks"]
            }
            self.assertEqual(strict_statuses["tool:conan"], "fail")

    def test_template_diff_detects_foundation_owned_drift(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            output = Path(name) / "drift-service"
            with patch("foundation.scaffold.shutil.which", return_value=None):
                initialize_project("drift-service", "1.2.3", output)
            with patch("foundation.scaffold.shutil.which", return_value=None):
                clean = compare_template(output, Path("foundation.toml"))
            self.assertTrue(clean["overall_pass"])

            workflow = output / ".github/workflows/ci.yml"
            workflow.write_text(
                workflow.read_text(encoding="utf-8") + "\n# consumer schedule\n",
                encoding="utf-8",
            )
            with patch("foundation.scaffold.shutil.which", return_value=None):
                consumer_owned = compare_template(output, Path("foundation.toml"))
            self.assertTrue(consumer_owned["overall_pass"])

            (output / ".clang-format").write_text("BasedOnStyle: LLVM\n")
            with patch("foundation.scaffold.shutil.which", return_value=None):
                changed = compare_template(output, Path("foundation.toml"))
            self.assertFalse(changed["overall_pass"])
            self.assertIn(
                {"path": ".clang-format", "status": "modified"},
                changed["changes"],
            )

    def test_branch_protection_bootstrap_supports_single_maintainer(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "scripts/bootstrap_github.py",
                "--repository",
                "example/project",
                "--required-check",
                "cpp-ci / gcc",
                "--required-check",
                "cpp-ci / clang",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        policy = json.loads(result.stdout)
        self.assertEqual(
            policy["required_status_checks"]["contexts"],
            ["cpp-ci / gcc", "cpp-ci / clang"],
        )
        reviews = policy["required_pull_request_reviews"]
        self.assertEqual(reviews["required_approving_review_count"], 0)
        self.assertFalse(reviews["require_last_push_approval"])

    def test_pypi_workflow_separates_verification_and_oidc_publish(self) -> None:
        workflow = Path(".github/workflows/publish-pypi.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("default: false", workflow)
        self.assertIn("needs: prepare", workflow)
        self.assertIn("name: pypi", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("permissions: {}", workflow)
        self.assertIn(
            "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33",
            workflow,
        )
        self.assertIn("skip-existing: false", workflow)
        self.assertNotIn("password:", workflow)
        self.assertEqual(workflow.count("actions/checkout@"), 1)


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

    def test_dirty_source_tree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "source"
            root.mkdir()
            manifest_path = make_project(root)
            with manifest_path.open("a", encoding="utf-8") as stream:
                stream.write("\n")
            with self.assertRaises(FoundationError):
                package_release(load_manifest(manifest_path), Path(name) / "dist")

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

            report_path = root / "operations.md"
            report = render_operations_report(
                root / "soak.json", root / "perf.json", report_path
            )
            self.assertTrue(report["overall_pass"])
            self.assertEqual(report["metrics"]["sample_count"], 5)
            markdown = report_path.read_text(encoding="utf-8")
            self.assertIn("**Result: PASS**", markdown)
            self.assertIn("200,000.000 ops/s", markdown)

            invalid_soak = json.loads((root / "soak.json").read_text())
            invalid_soak["sample_count"] = 99
            atomic_json(root / "invalid-soak.json", invalid_soak)
            with self.assertRaises(FoundationError):
                render_operations_report(
                    root / "invalid-soak.json",
                    root / "perf.json",
                    root / "invalid.md",
                )


if __name__ == "__main__":
    unittest.main()
