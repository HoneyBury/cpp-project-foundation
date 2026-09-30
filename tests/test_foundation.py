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
from foundation.cli import build_parser
from foundation.common import FoundationError, atomic_json, sha256_file
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
    def test_cli_parser_exposes_contract_commands(self) -> None:
        parser = build_parser()
        for command in ("validate", "doctor", "package", "quality"):
            parsed = parser.parse_args([command])
            self.assertEqual(parsed.command, command)

    def test_bootstrap_script_rejects_unsupported_python(self) -> None:
        script = Path("scripts/bootstrap_dev.py").read_text(encoding="utf-8")
        self.assertIn("Python 3.11 or newer", script)
        quality_script = Path("scripts/install_quality_tools.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Node.js 22 or newer", quality_script)

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

    def test_conan_lock_sbom_rejects_invalid_reference(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            lockfile = root / "conan.lock"
            atomic_json(lockfile, {"version": "0.5", "requires": ["invalid"]})
            with self.assertRaises(FoundationError):
                conan_lock_to_spdx(lockfile, root / "dependencies.spdx.json")

    def test_reference_manifest_is_valid(self) -> None:
        manifest = load_manifest(Path("examples/hello-service/foundation.toml"))
        self.assertEqual(manifest.name, "hello-service")
        self.assertEqual(manifest.build["target"], "hello_service")

    def test_repository_template_passes_its_own_diagnostics(self) -> None:
        root = Path("examples/hello-service")
        doctor = run_doctor(root, Path("foundation.toml"))
        self.assertTrue(doctor["overall_pass"])
        comparison = compare_template(root, Path("foundation.toml"))
        self.assertTrue(comparison["overall_pass"])

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

    def test_manifest_rejects_invalid_container_types_and_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            manifest_path = make_project(root)
            original = manifest_path.read_text(encoding="utf-8")
            invalid_documents = (
                original.replace(
                    '[release]\nexecutables = ["build/release/bin/sample-service"]',
                    '[release]\nexecutables = ["build/release/bin/sample-service"]\n'
                    'include = "deploy"',
                ),
                original.replace(
                    'lockfile = "conan/locks/release.lock"',
                    'lockfile = "conan/locks/release.lock"\nfuzz_targets = "fuzz"',
                ),
                original.replace(
                    '[project]\nname = "sample-service"',
                    '[project]\nname = "sample-service"\nunsupported = true',
                ),
                original.replace(
                    "[operations]",
                    "[operations]\nhook_timeout_seconds = 0",
                ),
                original + '\n[observability]\nhealth_url = "file:///tmp/health"\n',
            )
            for document in invalid_documents:
                with self.subTest(document=document):
                    manifest_path.write_text(document, encoding="utf-8")
                    with self.assertRaises(FoundationError):
                        load_manifest(manifest_path)

    def test_scaffold_creates_independent_project(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            output = Path(name) / "order-service"
            with patch("foundation.scaffold.shutil.which", return_value=None):
                result = initialize_project("order-service", "1.2.3", output)
            self.assertTrue(result["overall_pass"])
            manifest = load_manifest(output / "foundation.toml")
            self.assertEqual(manifest.name, "order-service")
            self.assertIn("LICENSE", manifest.release["include"])
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
            self.assertIn(
                "namespace service = order_service;",
                (output / "src/main.cpp").read_text(),
            )
            self.assertIn(
                "namespace service = order_service;",
                (output / "tests/request_parser_test.cpp").read_text(),
            )
            self.assertFalse((output / "build").exists())
            self.assertTrue((output / ".clang-format").is_file())
            self.assertTrue((output / ".clang-tidy").is_file())
            self.assertTrue((output / ".gitignore").is_file())
            self.assertTrue((output / ".github/dependabot.yml").is_file())
            self.assertTrue((output / ".github/CODEOWNERS").is_file())
            self.assertTrue((output / ".github/pull_request_template.md").is_file())
            self.assertTrue((output / "README.md").is_file())
            self.assertTrue((output / "CONTRIBUTING.md").is_file())
            self.assertTrue((output / "SECURITY.md").is_file())
            self.assertTrue((output / "LICENSE").is_file())
            self.assertTrue((output / "CMakePresets.json").is_file())
            self.assertTrue((output / ".iwyu.imp").is_file())
            self.assertTrue((output / "quality/baseline.json").is_file())
            self.assertTrue((output / "ruff.toml").is_file())
            self.assertTrue((output / "scripts/bootstrap_dev.py").is_file())
            self.assertTrue((output / "scripts/bootstrap_github.py").is_file())
            self.assertTrue((output / "scripts/install_quality_tools.py").is_file())
            self.assertTrue((output / "deploy/order-service.service").is_file())
            self.assertTrue(
                (output / "include/order_service/request_parser.h").is_file()
            )
            workflow = (output / ".github/workflows/ci.yml").read_text(encoding="utf-8")
            self.assertIn("@v0.7.0", workflow)
            self.assertNotIn("@v1.2.3", workflow)
            self.assertIn("\n  push:\n", workflow)
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

    def test_scaffold_rejects_unsafe_names_and_validates_semver(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for project_name in ("class", "bad-", "bad--name", "UPPER"):
                with (
                    self.subTest(project_name=project_name),
                    self.assertRaises(FoundationError),
                ):
                    initialize_project(project_name, "1.0.0", root / project_name)
            with patch("foundation.scaffold.shutil.which", return_value=None):
                initialize_project(
                    "valid-service",
                    "1.0.0-rc.1+build.2",
                    root / "valid-service",
                )
            generated = root / "valid-service"
            self.assertIn(
                "VERSION 1.0.0",
                (generated / "CMakeLists.txt").read_text(encoding="utf-8"),
            )
            self.assertIn(
                'version = "1.0.0-rc.1+build.2"',
                (generated / "foundation.toml").read_text(encoding="utf-8"),
            )
            with self.assertRaises(FoundationError):
                initialize_project("invalid-version", "1.0.0-..", root / "invalid")

    def test_scaffold_supports_explicit_license_choices(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for license_name in ("MIT", "Apache-2.0", "proprietary"):
                with self.subTest(license_name=license_name):
                    output = root / license_name
                    with patch("foundation.scaffold.shutil.which", return_value=None):
                        result = initialize_project(
                            "license-service",
                            "1.0.0",
                            output,
                            license_name=license_name,
                        )
                    self.assertEqual(result["license"], license_name)
                    self.assertTrue((output / "LICENSE").is_file())
                    self.assertIn(
                        "license-service",
                        (output / "LICENSE").read_text(encoding="utf-8"),
                    )
            output = root / "none"
            with patch("foundation.scaffold.shutil.which", return_value=None):
                initialize_project(
                    "license-service", "1.0.0", output, license_name="none"
                )
            self.assertFalse((output / "LICENSE").exists())
            manifest = load_manifest(output / "foundation.toml")
            self.assertNotIn("LICENSE", manifest.release["include"])

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

            (output / "quality/baseline.json").unlink()
            with patch("foundation.doctor.shutil.which", side_effect=available):
                missing_asset = run_doctor(output, Path("foundation.toml"))
            self.assertFalse(missing_asset["overall_pass"])

    def test_doctor_optionally_probes_observability_endpoints(self) -> None:
        class Response:
            def __init__(self, body: bytes):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *unused):
                return False

            def getcode(self) -> int:
                return 200

            def read(self, unused_limit: int) -> bytes:
                return self.body

        with tempfile.TemporaryDirectory() as name:
            output = Path(name) / "doctor-service"
            with patch("foundation.scaffold.shutil.which", return_value=None):
                initialize_project("doctor-service", "1.2.3", output)
            with patch(
                "foundation.doctor.urlopen",
                side_effect=(Response(b"ok"), Response(b"metric 1\n")),
            ) as probe:
                result = run_doctor(
                    output,
                    Path("foundation.toml"),
                    probe_observability=True,
                    probe_timeout=2.0,
                )
            statuses = {item["name"]: item["status"] for item in result["checks"]}
            self.assertEqual(statuses["observability:health"], "pass")
            self.assertEqual(statuses["observability:metrics"], "pass")
            self.assertEqual(probe.call_count, 2)

            with patch(
                "foundation.doctor.urlopen",
                side_effect=(Response(b"ok"), Response(b"")),
            ):
                failed = run_doctor(
                    output, Path("foundation.toml"), probe_observability=True
                )
            self.assertFalse(failed["overall_pass"])

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
                workflow_drift = compare_template(output, Path("foundation.toml"))
            self.assertFalse(workflow_drift["overall_pass"])
            self.assertIn(
                {"path": ".github/workflows/ci.yml", "status": "modified"},
                workflow_drift["changes"],
            )

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
            self.assertRegex(result["payload_sha256"], r"^[0-9a-f]{64}$")

    def test_embedded_sbom_semantics_are_verified(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, _ = self.package(root, "1.0.0")
            unpacked = root / "unpacked"
            with tarfile.open(archive, "r:gz") as stream:
                stream.extractall(unpacked, filter="data")
            release_root = next(unpacked.iterdir())
            sbom_path = release_root / "sbom.spdx.json"
            sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
            sbom["packages"][0]["versionInfo"] = "9.9.9"
            atomic_json(sbom_path, sbom)
            manifest_path = release_root / "release-manifest.json"
            release_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            sbom_record = next(
                item
                for item in release_manifest["files"]
                if item["path"] == "sbom.spdx.json"
            )
            sbom_record["size_bytes"] = sbom_path.stat().st_size
            sbom_record["sha256"] = sha256_file(sbom_path)
            atomic_json(manifest_path, release_manifest)
            tampered = root / "tampered-sbom.tar.gz"
            with tarfile.open(tampered, "w:gz") as stream:
                stream.add(release_root, arcname=release_root.name)
            checksum = root / "tampered-sbom.tar.gz.sha256"
            checksum.write_text(
                f"{sha256_file(tampered)}  {tampered.name}\n", encoding="ascii"
            )
            with self.assertRaisesRegex(FoundationError, "SBOM package identity"):
                verify_release(tampered, checksum)

    def test_release_verifier_accepts_pre_payload_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, _ = self.package(root, "1.0.0")
            unpacked = root / "unpacked"
            with tarfile.open(archive, "r:gz") as stream:
                stream.extractall(unpacked, filter="data")
            release_root = next(unpacked.iterdir())
            manifest_path = release_root / "release-manifest.json"
            release_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            release_manifest.pop("payload")
            atomic_json(manifest_path, release_manifest)
            legacy = root / "legacy.tar.gz"
            with tarfile.open(legacy, "w:gz") as stream:
                stream.add(release_root, arcname=release_root.name)
            checksum = root / "legacy.tar.gz.sha256"
            checksum.write_text(
                f"{sha256_file(legacy)}  {legacy.name}\n", encoding="ascii"
            )
            self.assertIsNone(verify_release(legacy, checksum)["payload_sha256"])

    def test_checksum_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            archive, checksum = self.package(Path(name), "1.0.0")
            with archive.open("ab") as stream:
                stream.write(b"tamper")
            with self.assertRaises(FoundationError):
                verify_release(archive, checksum)

    def test_unlisted_archive_payload_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, _ = self.package(root, "1.0.0")
            unpacked = root / "unpacked"
            with tarfile.open(archive, "r:gz") as stream:
                stream.extractall(unpacked, filter="data")
            release_root = next(unpacked.iterdir())
            write(release_root / "unexpected-payload", "not inventoried\n")
            tampered = root / "tampered.tar.gz"
            with tarfile.open(tampered, "w:gz") as stream:
                stream.add(release_root, arcname=release_root.name)
            checksum = root / "tampered.tar.gz.sha256"
            checksum.write_text(
                f"{sha256_file(tampered)}  {tampered.name}\n", encoding="ascii"
            )
            with self.assertRaisesRegex(FoundationError, "unexpected file"):
                verify_release(tampered, checksum)

    def test_duplicate_archive_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, _ = self.package(root, "1.0.0")
            unpacked = root / "unpacked"
            with tarfile.open(archive, "r:gz") as stream:
                stream.extractall(unpacked, filter="data")
            release_root = next(unpacked.iterdir())
            duplicate = root / "duplicate.tar.gz"
            with tarfile.open(duplicate, "w:gz") as stream:
                stream.add(release_root, arcname=release_root.name)
                payload = release_root / "foundation.toml"
                stream.add(payload, arcname=f"{release_root.name}/foundation.toml")
            with self.assertRaisesRegex(FoundationError, "duplicate release"):
                verify_release(duplicate)

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

    def test_deployment_install_requires_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            parent = Path(name)
            archive, _ = self.package(parent, "1.0.0")
            manager = DeploymentManager(parent / "opt", parent / "state")
            with self.assertRaisesRegex(FoundationError, "requires a release checksum"):
                manager.install(archive)

    def test_interrupted_deployment_requires_explicit_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            parent = Path(name)
            first_archive, first_checksum = self.package(parent, "1.0.0")
            second_archive, second_checksum = self.package(parent, "1.1.0")
            manager = DeploymentManager(parent / "opt", parent / "state")
            first = manager.install(first_archive, first_checksum)
            manager.deploy(first["deployment_id"])
            second = manager.install(second_archive, second_checksum)
            _, transaction = manager._transaction(
                "upgrade",
                {
                    "candidate": second["deployment_id"],
                    "from_current": first["deployment_id"],
                    "from_previous": None,
                },
            )
            manager._atomic_link(
                manager.current,
                manager.deployments / second["deployment_id"],
            )

            self.assertFalse(manager.status()["overall_pass"])
            with self.assertRaisesRegex(FoundationError, "deploy recover"):
                manager.deploy(first["deployment_id"])
            with self.assertRaisesRegex(FoundationError, "deploy recover"):
                manager.deploy(second["deployment_id"])
            recovered = manager.recover()
            self.assertEqual(recovered["transaction_id"], transaction["transaction_id"])
            self.assertEqual(recovered["status"], "recovered")
            self.assertEqual(manager.status()["current"], first["deployment_id"])
            self.assertTrue(manager.status()["overall_pass"])

            manager._transaction(
                "upgrade",
                {
                    "candidate": second["deployment_id"],
                    "from_current": first["deployment_id"],
                    "from_previous": None,
                },
            )
            failed_hook = {
                "hook": "deactivate",
                "status": "failed",
                "returncode": -1,
            }
            passed_hook = {
                "hook": "activate",
                "status": "skipped",
                "returncode": 0,
            }
            with (
                patch.object(
                    manager,
                    "_run_deployment_recovery_hook",
                    side_effect=(failed_hook, passed_hook),
                ),
                self.assertRaisesRegex(FoundationError, "deactivate hook returned"),
            ):
                manager.recover()
            self.assertFalse(manager.status()["overall_pass"])
            self.assertEqual(manager.recover()["status"], "recovered")
            self.assertTrue(manager.status()["overall_pass"])


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

    def test_evidence_rejects_corruption_escape_and_links(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            summary = root / "summary.json"
            atomic_json(summary, {"overall_pass": True})
            evidence = root / "evidence"
            record = record_evidence(
                evidence,
                kind="daily",
                record_id="one",
                summaries=[summary],
            )
            snapshot = evidence / record["summaries"][0]["snapshot"]
            snapshot.write_text("corrupt\n", encoding="utf-8")
            self.assertFalse(verify_evidence(evidence)["overall_pass"])
            with self.assertRaisesRegex(FoundationError, "existing evidence snapshot"):
                record_evidence(
                    evidence,
                    kind="daily",
                    record_id="two",
                    summaries=[summary],
                )

            snapshot.write_bytes(summary.read_bytes())
            record_path = evidence / "records/daily/one.json"
            document = json.loads(record_path.read_text(encoding="utf-8"))
            document["summaries"][0]["snapshot"] = "../../summary.json"
            atomic_json(record_path, document)
            self.assertFalse(verify_evidence(evidence)["overall_pass"])

            document["summaries"][0]["snapshot"] = str(snapshot.relative_to(evidence))
            atomic_json(record_path, document)
            (evidence / "unexpected-link").symlink_to(summary)
            with self.assertRaisesRegex(FoundationError, "evidence tree is not valid"):
                package_evidence(evidence, root / "evidence.tar.gz")

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
