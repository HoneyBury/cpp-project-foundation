from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .common import FoundationError, atomic_json, load_json
from .deployment import DeploymentManager
from .evidence import package_evidence, record_evidence, verify_evidence
from .manifest import export_environment, load_manifest
from .operations import (
    aggregate_canary,
    create_backup,
    restore_backup,
    run_canary,
    run_performance,
    run_soak,
    verify_backup,
)
from .provenance import build_provenance
from .quality import run_quality
from .release import package_release, verify_release
from .sbom import conan_lock_to_spdx
from .scaffold import initialize_project


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))


def _manifest(args: argparse.Namespace):
    return load_manifest(Path(args.manifest))


def _datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _manager(args: argparse.Namespace) -> DeploymentManager:
    return DeploymentManager(Path(args.root), Path(args.state_root))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cpp-foundation")
    parser.add_argument("--manifest", default="foundation.toml")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--name", required=True)
    init.add_argument("--version", default="0.1.0")
    init.add_argument("--output", type=Path, required=True)

    sub.add_parser("validate")
    export = sub.add_parser("export-env")
    export.add_argument("--github-env", type=Path, required=True)
    provenance = sub.add_parser("provenance")
    provenance.add_argument("--configuration", default="Release")
    provenance.add_argument("--output", type=Path)

    package = sub.add_parser("package")
    package.add_argument("--output-dir", type=Path, default=Path("dist"))
    package.add_argument("--configuration", default="Release")
    package.add_argument(
        "--platform",
        help="target platform label; defaults to the native host platform",
    )
    verify = sub.add_parser("verify-release")
    verify.add_argument("--archive", type=Path, required=True)
    verify.add_argument("--checksum", type=Path)

    deploy = sub.add_parser("deploy")
    deploy.add_argument("--root", type=Path, required=True)
    deploy.add_argument("--state-root", type=Path, required=True)
    deploy_sub = deploy.add_subparsers(dest="deploy_command", required=True)
    install = deploy_sub.add_parser("install")
    install.add_argument("--archive", type=Path, required=True)
    install.add_argument("--checksum", type=Path)
    for name in ("activate", "upgrade"):
        child = deploy_sub.add_parser(name)
        child.add_argument("--deployment-id", required=True)
    deploy_sub.add_parser("rollback")
    deploy_sub.add_parser("status")
    deploy_sub.add_parser("verify")

    evidence = sub.add_parser("evidence")
    evidence.add_argument("--root", type=Path, required=True)
    evidence_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    record = evidence_sub.add_parser("record")
    record.add_argument("--kind", required=True)
    record.add_argument("--record-id", required=True)
    record.add_argument("--summary", type=Path, action="append", required=True)
    record.add_argument("--attributes-json", type=Path)
    evidence_sub.add_parser("verify")
    evidence_package = evidence_sub.add_parser("package")
    evidence_package.add_argument("--output", type=Path, required=True)

    backup = sub.add_parser("backup")
    backup_sub = backup.add_subparsers(dest="backup_command", required=True)
    backup_create = backup_sub.add_parser("create")
    backup_create.add_argument("--source", type=Path, required=True)
    backup_create.add_argument("--output", type=Path, required=True)
    backup_create.add_argument("--age-recipient", default="")
    backup_create.add_argument("--allow-plaintext", action="store_true")
    backup_verify = backup_sub.add_parser("verify")
    backup_verify.add_argument("--archive", type=Path, required=True)
    backup_verify.add_argument("--summary", type=Path, required=True)
    backup_verify.add_argument("--age-identity", type=Path)
    backup_restore = backup_sub.add_parser("restore")
    backup_restore.add_argument("--archive", type=Path, required=True)
    backup_restore.add_argument("--summary", type=Path, required=True)
    backup_restore.add_argument("--destination", type=Path, required=True)
    backup_restore.add_argument("--age-identity", type=Path)

    canary = sub.add_parser("canary")
    canary_sub = canary.add_subparsers(dest="canary_command", required=True)
    canary_run = canary_sub.add_parser("run")
    canary_run.add_argument("--evidence-root", type=Path, required=True)
    canary_run.add_argument("--candidate", required=True)
    canary_run.add_argument("--timeout", type=float, default=60.0)
    canary_aggregate = canary_sub.add_parser("aggregate")
    canary_aggregate.add_argument("--evidence-root", type=Path, required=True)
    canary_aggregate.add_argument("--candidate", required=True)
    canary_aggregate.add_argument("--end", type=_datetime, required=True)
    canary_aggregate.add_argument("--minutes", type=int, required=True)
    canary_aggregate.add_argument("--output", type=Path)

    soak = sub.add_parser("soak")
    soak.add_argument("--duration-seconds", type=float, required=True)
    soak.add_argument("--interval-seconds", type=float, default=30.0)
    soak.add_argument("--output", type=Path, required=True)
    perf = sub.add_parser("perf")
    perf.add_argument("--repetitions", type=int, default=3)
    perf.add_argument("--minimum-ops-per-second", type=float, required=True)
    perf.add_argument("--maximum-p99-ms", type=float, required=True)
    perf.add_argument("--output", type=Path, required=True)
    quality = sub.add_parser("quality")
    quality.add_argument("--root", type=Path, default=Path("."))
    quality.add_argument("--mode", choices=("fast", "deep"), default="fast")
    quality.add_argument("--fix", action="store_true")
    dependency_sbom = sub.add_parser("dependency-sbom")
    dependency_sbom.add_argument("--lockfile", type=Path, required=True)
    dependency_sbom.add_argument("--output", type=Path, required=True)
    return parser


def execute(args: argparse.Namespace) -> Any:
    if args.command == "init":
        return initialize_project(args.name, args.version, args.output)
    if args.command == "validate":
        manifest = _manifest(args)
        return {"schema_version": 1, "overall_pass": True, "project": manifest.name}
    if args.command == "export-env":
        manifest = _manifest(args)
        export_environment(manifest, args.github_env)
        return {
            "schema_version": 1,
            "overall_pass": True,
            "output": str(args.github_env),
        }
    if args.command == "provenance":
        payload = build_provenance(_manifest(args), args.configuration)
        if args.output:
            atomic_json(args.output, payload)
        return payload
    if args.command == "package":
        return package_release(
            _manifest(args),
            args.output_dir,
            configuration=args.configuration,
            platform_name=args.platform,
        )
    if args.command == "verify-release":
        return verify_release(args.archive, args.checksum)
    if args.command == "deploy":
        manager = _manager(args)
        with manager.locked():
            if args.deploy_command == "install":
                return manager.install(args.archive, args.checksum)
            if args.deploy_command == "activate":
                return manager.deploy(args.deployment_id)
            if args.deploy_command == "upgrade":
                return manager.upgrade(args.deployment_id)
            if args.deploy_command == "rollback":
                return manager.rollback()
            if args.deploy_command == "verify":
                return manager.verify()
            return manager.status()
    if args.command == "evidence":
        if args.evidence_command == "record":
            attributes = load_json(args.attributes_json) if args.attributes_json else {}
            return record_evidence(
                args.root,
                kind=args.kind,
                record_id=args.record_id,
                summaries=args.summary,
                attributes=attributes,
            )
        if args.evidence_command == "verify":
            return verify_evidence(args.root)
        return package_evidence(args.root, args.output)
    if args.command == "backup":
        if args.backup_command == "create":
            return create_backup(
                args.source,
                args.output,
                age_recipient=args.age_recipient,
                allow_plaintext=args.allow_plaintext,
            )
        if args.backup_command == "verify":
            return verify_backup(
                args.archive, args.summary, age_identity=args.age_identity
            )
        return restore_backup(
            args.archive,
            args.summary,
            args.destination,
            age_identity=args.age_identity,
        )
    if args.command == "canary":
        if args.canary_command == "run":
            return run_canary(
                _manifest(args),
                args.evidence_root,
                candidate=args.candidate,
                timeout=args.timeout,
            )
        payload = aggregate_canary(
            args.evidence_root,
            end=args.end,
            duration=timedelta(minutes=args.minutes),
            candidate=args.candidate,
        )
        if args.output:
            atomic_json(args.output, payload)
        return payload
    if args.command == "soak":
        return run_soak(
            _manifest(args),
            args.output,
            duration_seconds=args.duration_seconds,
            interval_seconds=args.interval_seconds,
        )
    if args.command == "perf":
        return run_performance(
            _manifest(args),
            args.output,
            repetitions=args.repetitions,
            minimum_ops_per_second=args.minimum_ops_per_second,
            maximum_p99_ms=args.maximum_p99_ms,
        )
    if args.command == "quality":
        return run_quality(args.root, args.mode, args.fix)
    if args.command == "dependency-sbom":
        return conan_lock_to_spdx(args.lockfile, args.output)
    raise FoundationError(f"unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = execute(args)
        _print(payload)
        return 0 if payload.get("overall_pass", True) else 1
    except (FoundationError, OSError, ValueError) as exc:
        print(f"cpp-foundation: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
