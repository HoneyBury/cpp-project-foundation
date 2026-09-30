from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from foundation import cli
from foundation.common import FoundationError
from foundation.quality import _run, _tool, run_quality


def parsed(*arguments: str):
    return cli.build_parser().parse_args(list(arguments))


class CliDispatchTests(unittest.TestCase):
    def test_project_and_release_commands_dispatch(self) -> None:
        manifest = SimpleNamespace(name="sample")
        result = {"overall_pass": True}
        with (
            patch.object(cli, "_manifest", return_value=manifest),
            patch.object(cli, "initialize_project", return_value=result) as initialize,
            patch.object(cli, "run_doctor", return_value=result) as doctor,
            patch.object(cli, "compare_template", return_value=result) as template,
            patch.object(cli, "export_environment") as export,
            patch.object(cli, "build_provenance", return_value=result) as provenance,
            patch.object(cli, "package_release", return_value=result) as package,
            patch.object(cli, "verify_release", return_value=result) as verify,
            patch.object(cli, "atomic_json") as atomic,
        ):
            self.assertIs(
                cli.execute(
                    parsed("init", "--name", "sample", "--output", "generated")
                ),
                result,
            )
            initialize.assert_called_once()
            self.assertTrue(cli.execute(parsed("validate"))["overall_pass"])
            self.assertIs(cli.execute(parsed("doctor")), result)
            self.assertIs(cli.execute(parsed("template-diff")), result)
            self.assertTrue(
                cli.execute(parsed("export-env", "--github-env", "environment"))[
                    "overall_pass"
                ]
            )
            export.assert_called_once()
            self.assertIs(
                cli.execute(parsed("provenance", "--output", "provenance.json")),
                result,
            )
            provenance.assert_called_once()
            atomic.assert_called_once()
            self.assertIs(cli.execute(parsed("package")), result)
            package.assert_called_once()
            self.assertIs(
                cli.execute(parsed("verify-release", "--archive", "release.tar.gz")),
                result,
            )
            verify.assert_called_once()
            doctor.assert_called_once()
            template.assert_called_once()

    def test_deployment_evidence_and_backup_commands_dispatch(self) -> None:
        result = {"overall_pass": True}
        manager = MagicMock()
        manager.locked.return_value.__enter__.return_value = None
        for method in ("install", "deploy", "upgrade", "rollback", "status", "verify"):
            getattr(manager, method).return_value = result
        with patch.object(cli, "_manager", return_value=manager):
            common = ("deploy", "--root", "opt", "--state-root", "state")
            self.assertIs(
                cli.execute(
                    parsed(
                        *common,
                        "install",
                        "--archive",
                        "release.tar.gz",
                        "--checksum",
                        "release.tar.gz.sha256",
                    )
                ),
                result,
            )
            for command in ("activate", "upgrade"):
                self.assertIs(
                    cli.execute(parsed(*common, command, "--deployment-id", "v1")),
                    result,
                )
            for command in ("rollback", "status", "verify"):
                self.assertIs(cli.execute(parsed(*common, command)), result)

        with (
            patch.object(cli, "record_evidence", return_value=result),
            patch.object(cli, "verify_evidence", return_value=result),
            patch.object(cli, "package_evidence", return_value=result),
            patch.object(cli, "create_backup", return_value=result),
            patch.object(cli, "verify_backup", return_value=result),
            patch.object(cli, "restore_backup", return_value=result),
            patch.object(cli, "load_json", return_value={"owner": "test"}),
        ):
            self.assertIs(
                cli.execute(
                    parsed(
                        "evidence",
                        "--root",
                        "evidence",
                        "record",
                        "--kind",
                        "daily",
                        "--record-id",
                        "one",
                        "--summary",
                        "summary.json",
                        "--attributes-json",
                        "attributes.json",
                    )
                ),
                result,
            )
            self.assertIs(
                cli.execute(parsed("evidence", "--root", "evidence", "verify")),
                result,
            )
            self.assertIs(
                cli.execute(
                    parsed(
                        "evidence",
                        "--root",
                        "evidence",
                        "package",
                        "--output",
                        "evidence.tar.gz",
                    )
                ),
                result,
            )
            self.assertIs(
                cli.execute(
                    parsed(
                        "backup",
                        "create",
                        "--source",
                        "data",
                        "--output",
                        "backup.tar.gz",
                        "--allow-plaintext",
                    )
                ),
                result,
            )
            self.assertIs(
                cli.execute(
                    parsed(
                        "backup",
                        "verify",
                        "--archive",
                        "backup.tar.gz",
                        "--summary",
                        "backup.json",
                    )
                ),
                result,
            )
            self.assertIs(
                cli.execute(
                    parsed(
                        "backup",
                        "restore",
                        "--archive",
                        "backup.tar.gz",
                        "--summary",
                        "backup.json",
                        "--destination",
                        "restored",
                    )
                ),
                result,
            )

    def test_operations_quality_and_sbom_commands_dispatch(self) -> None:
        result = {"overall_pass": True}
        manifest = SimpleNamespace(name="sample")
        with (
            patch.object(cli, "_manifest", return_value=manifest),
            patch.object(cli, "run_canary", return_value=result),
            patch.object(cli, "aggregate_canary", return_value=result),
            patch.object(cli, "run_soak", return_value=result),
            patch.object(cli, "run_performance", return_value=result),
            patch.object(cli, "render_operations_report", return_value=result),
            patch.object(cli, "run_quality", return_value=result),
            patch.object(cli, "conan_lock_to_spdx", return_value=result),
            patch.object(cli, "atomic_json"),
        ):
            self.assertIs(
                cli.execute(
                    parsed(
                        "canary",
                        "run",
                        "--evidence-root",
                        "evidence",
                        "--candidate",
                        "candidate",
                    )
                ),
                result,
            )
            self.assertIs(
                cli.execute(
                    parsed(
                        "canary",
                        "aggregate",
                        "--evidence-root",
                        "evidence",
                        "--candidate",
                        "candidate",
                        "--end",
                        "2026-09-30T12:00:00Z",
                        "--minutes",
                        "5",
                        "--output",
                        "canary.json",
                    )
                ),
                result,
            )
            self.assertIs(
                cli.execute(
                    parsed(
                        "soak",
                        "--duration-seconds",
                        "1",
                        "--output",
                        "soak.json",
                    )
                ),
                result,
            )
            self.assertIs(
                cli.execute(
                    parsed(
                        "perf",
                        "--minimum-ops-per-second",
                        "1",
                        "--maximum-p99-ms",
                        "1",
                        "--output",
                        "perf.json",
                    )
                ),
                result,
            )
            self.assertIs(
                cli.execute(
                    parsed(
                        "report",
                        "operations",
                        "--soak",
                        "soak.json",
                        "--performance",
                        "perf.json",
                        "--output",
                        "operations.md",
                    )
                ),
                result,
            )
            self.assertIs(cli.execute(parsed("quality")), result)
            self.assertIs(
                cli.execute(
                    parsed(
                        "dependency-sbom",
                        "--lockfile",
                        "conan.lock",
                        "--output",
                        "dependencies.json",
                    )
                ),
                result,
            )

    def test_main_exit_codes_and_datetime_validation(self) -> None:
        with (
            patch.object(cli, "execute", return_value={"overall_pass": False}),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(cli.main(["validate"]), 1)
        with patch.object(cli, "execute", side_effect=FoundationError("invalid")):
            error = io.StringIO()
            with redirect_stderr(error):
                self.assertEqual(cli.main(["validate"]), 1)
            self.assertIn("cpp-foundation: FAIL: invalid", error.getvalue())
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parsed(
                "canary",
                "aggregate",
                "--evidence-root",
                "evidence",
                "--candidate",
                "candidate",
                "--end",
                "2026-09-30T12:00:00",
                "--minutes",
                "5",
            )


class QualityTests(unittest.TestCase):
    def test_quality_modes_and_fix_commands(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            files = {
                "src/main.cpp": "int main() { return 0; }\n",
                "tool.py": "print('ok')\n",
                "verify.sh": "#!/bin/sh\ntrue\n",
                ".github/workflows/ci.yml": "name: ci\n",
                "CMakeLists.txt": "cmake_minimum_required(VERSION 3.21)\n",
                "deploy/Dockerfile": "FROM scratch\n",
                "README.md": "# Test\n",
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            commands: list[list[str]] = []
            with (
                patch("foundation.quality._tool", side_effect=lambda *names: names[0]),
                patch(
                    "foundation.quality._run",
                    side_effect=lambda command, _root: commands.append(command),
                ),
            ):
                result = run_quality(root, mode="deep", fix=True)
            self.assertTrue(result["overall_pass"])
            self.assertEqual(
                result["checks"],
                [
                    "clang-format",
                    "ruff",
                    "shellcheck",
                    "actionlint",
                    "cmake-format",
                    "markdownlint",
                    "hadolint",
                ],
            )
            self.assertTrue(any("--fix" in command for command in commands))
            self.assertTrue(any("-i" in command for command in commands))
        with self.assertRaisesRegex(FoundationError, "unsupported quality mode"):
            run_quality(Path("."), mode="invalid")

    def test_tool_and_failed_command_errors(self) -> None:
        with (
            patch("foundation.quality.shutil.which", return_value=None),
            self.assertRaisesRegex(FoundationError, "required quality tool"),
        ):
            _tool("missing")
        completed = SimpleNamespace(returncode=2)
        with (
            patch("foundation.quality.subprocess.run", return_value=completed),
            self.assertRaisesRegex(FoundationError, "quality command failed"),
        ):
            _run(["false"], Path("."))


if __name__ == "__main__":
    unittest.main()
