from __future__ import annotations

import hashlib
import json
import os
import platform as host_platform
import re
import shutil
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO
from urllib.parse import quote

from . import __version__
from .common import FoundationError, atomic_json, load_json, relative_path, sha256_file
from .manifest import FoundationManifest
from .provenance import build_provenance


def _copy_release_input(source: Path, root: Path, relative: Path) -> None:
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, symlinks=False)
    elif source.is_file():
        shutil.copy2(source, destination)
    else:
        raise FoundationError(f"release input does not exist: {source}")


def _inventory(root: Path, *, excluded: set[str] | None = None) -> list[dict[str, Any]]:
    ignored = excluded or set()
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in ignored:
            continue
        files.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "executable": bool(path.stat().st_mode & 0o111),
            }
        )
    return files


def _inventory_digest(files: list[dict[str, Any]]) -> str:
    encoded = json.dumps(
        files, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _native_platform_name() -> str:
    systems = {"darwin": "macos", "linux": "linux", "windows": "windows"}
    architectures = {
        "amd64": "x64",
        "x86_64": "x64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }
    system = systems.get(host_platform.system().lower(), host_platform.system().lower())
    machine = architectures.get(
        host_platform.machine().lower(), host_platform.machine().lower()
    )
    return f"{system}-{machine}"


def _conan_dependencies(manifest: FoundationManifest) -> list[dict[str, str]]:
    lockfile = manifest.root / str(manifest.build["lockfile"])
    lock = load_json(lockfile)
    dependencies = []
    for reference in lock.get("requires", []):
        pinned = str(reference).split("%", maxsplit=1)[0]
        coordinate, _, revision = pinned.partition("#")
        name_version = coordinate.split("@", maxsplit=1)[0]
        name, separator, version = name_version.partition("/")
        if not separator:
            raise FoundationError(f"invalid Conan lock reference: {reference}")
        identifier = re.sub(r"[^A-Za-z0-9.-]", "-", f"{name}-{version}")
        dependencies.append(
            {
                "name": name,
                "version": version,
                "revision": revision or "unversioned",
                "spdx_id": f"SPDXRef-Conan-{identifier}",
            }
        )
    return dependencies


def _spdx(
    manifest: FoundationManifest,
    files: list[dict[str, Any]],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    namespace = (
        f"https://spdx.org/spdxdocs/{manifest.name}-{manifest.version}-"
        f"{provenance['candidate_revision'][:12]}-"
        f"{provenance['conan_lockfile_sha256'][:12]}"
    )
    dependencies = _conan_dependencies(manifest)
    application = {
        "name": manifest.name,
        "SPDXID": "SPDXRef-Package",
        "versionInfo": manifest.version,
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": True,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION",
        "copyrightText": "NOASSERTION",
    }
    dependency_packages = [
        {
            "name": dependency["name"],
            "SPDXID": dependency["spdx_id"],
            "versionInfo": dependency["version"],
            "sourceInfo": f"Conan recipe revision: {dependency['revision']}",
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "copyrightText": "NOASSERTION",
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": (
                        f"pkg:conan/{quote(dependency['name'])}@"
                        f"{quote(dependency['version'])}"
                    ),
                }
            ],
        }
        for dependency in dependencies
    ]
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{manifest.name}-{manifest.version}",
        "documentNamespace": namespace,
        "creationInfo": {
            "created": datetime.now(UTC)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "creators": [f"Tool: cpp-project-foundation-{__version__}"],
        },
        "documentDescribes": ["SPDXRef-Package"],
        "packages": [application, *dependency_packages],
        "files": [
            {
                "fileName": f"./{item['path']}",
                "SPDXID": f"SPDXRef-File-{index}",
                "checksums": [{"algorithm": "SHA256", "checksumValue": item["sha256"]}],
                "licenseConcluded": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
            for index, item in enumerate(files, start=1)
        ],
        "relationships": [
            {
                "spdxElementId": "SPDXRef-Package",
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": dependency["spdx_id"],
            }
            for dependency in dependencies
        ],
    }


def package_release(
    manifest: FoundationManifest,
    output_dir: Path,
    *,
    configuration: str = "Release",
    platform_name: str | None = None,
) -> dict[str, Any]:
    platform_name = platform_name or _native_platform_name()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"{manifest.name}-v{manifest.version}-{platform_name}.tar.gz"
    archive = output_dir / archive_name
    checksum = output_dir / f"{archive_name}.sha256"
    if archive.exists() or checksum.exists():
        raise FoundationError(f"release output already exists: {archive}")
    with tempfile.TemporaryDirectory(
        prefix="cpp-foundation-release-"
    ) as temporary_name:
        temporary = Path(temporary_name)
        release_root = (
            temporary / f"{manifest.name}-v{manifest.version}-{platform_name}"
        )
        release_root.mkdir()
        executable_names: set[str] = set()
        for value in manifest.release["executables"]:
            source = relative_path(manifest.root, value, must_exist=True)
            name = source.name
            if name in executable_names:
                raise FoundationError(f"duplicate release executable name: {name}")
            executable_names.add(name)
            _copy_release_input(source, release_root, Path("bin") / name)
            (release_root / "bin" / name).chmod(source.stat().st_mode | 0o111)
        for value in manifest.release.get("include", []):
            source = relative_path(manifest.root, value, must_exist=True)
            _copy_release_input(source, release_root, Path(value))
        for value in (manifest.build["profile"], manifest.build["lockfile"]):
            source = relative_path(manifest.root, str(value), must_exist=True)
            _copy_release_input(source, release_root, Path(str(value)))
        shutil.copy2(manifest.path, release_root / "foundation.toml")
        payload_files = _inventory(release_root)
        payload = {
            "sha256": _inventory_digest(payload_files),
            "files": [item["path"] for item in payload_files],
        }
        provenance = build_provenance(manifest, configuration)
        if provenance["source_tree_clean"] is not True:
            paths = ", ".join(str(value) for value in provenance["source_tree_status"])
            raise FoundationError(
                f"release packaging requires a clean source tree: {paths}"
            )
        atomic_json(release_root / "provenance.json", provenance)
        files = _inventory(release_root)
        atomic_json(release_root / "sbom.spdx.json", _spdx(manifest, files, provenance))
        files = _inventory(release_root, excluded={"release-manifest.json"})
        release_manifest = {
            "schema_version": 1,
            "project": manifest.name,
            "version": manifest.version,
            "platform": platform_name,
            "configuration": configuration,
            "files": files,
            "payload": payload,
            "provenance": provenance,
        }
        atomic_json(release_root / "release-manifest.json", release_manifest)
        external_sbom = output_dir / f"{archive_name}-sbom.spdx.json"
        external_provenance = output_dir / f"{archive_name}-provenance.json"
        shutil.copy2(release_root / "sbom.spdx.json", external_sbom)
        shutil.copy2(release_root / "provenance.json", external_provenance)
        with tarfile.open(archive, "w:gz", format=tarfile.PAX_FORMAT) as stream:
            stream.add(release_root, arcname=release_root.name, recursive=True)
    digest = sha256_file(archive)
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    return {
        "schema_version": 1,
        "overall_pass": True,
        "archive": str(archive),
        "archive_sha256": digest,
        "checksum": str(checksum),
        "sbom": str(external_sbom),
        "provenance": str(external_provenance),
    }


def _safe_members(stream: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = stream.getmembers()
    roots: set[str] = set()
    names: set[str] = set()
    for member in members:
        path = PurePosixPath(member.name)
        normalized = path.as_posix()
        if (
            not path.parts
            or normalized in {"", "."}
            or path.is_absolute()
            or ".." in path.parts
            or member.issym()
            or member.islnk()
            or not (member.isdir() or member.isfile())
        ):
            raise FoundationError(f"unsafe release archive member: {member.name}")
        if normalized in names:
            raise FoundationError(f"duplicate release archive member: {member.name}")
        names.add(normalized)
        roots.add(path.parts[0])
    if len(roots) != 1:
        raise FoundationError(
            "release archive must contain exactly one top-level directory"
        )
    return members


def _stream_digest(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    stream.seek(0)
    return digest.hexdigest()


def _validate_checksum(archive: Path, checksum: Path | None, digest: str) -> None:
    if checksum is not None:
        fields = checksum.read_text(encoding="ascii").strip().split()
        if len(fields) != 2 or fields[0] != digest or fields[1] != archive.name:
            raise FoundationError("release checksum does not match archive")


def _validate_release_root(root: Path, archive: Path, digest: str) -> dict[str, Any]:
    release_manifest = load_json(root / "release-manifest.json")
    if not isinstance(release_manifest, dict):
        raise FoundationError("release manifest must be a JSON object")
    if release_manifest.get("schema_version") != 1:
        raise FoundationError("release manifest schema_version must be 1")
    allowed_fields = {
        "schema_version",
        "project",
        "version",
        "platform",
        "configuration",
        "files",
        "provenance",
        "payload",
    }
    unknown_fields = sorted(set(release_manifest) - allowed_fields)
    if unknown_fields:
        raise FoundationError(
            "release manifest contains unsupported fields: " + ", ".join(unknown_fields)
        )
    for key in ("project", "version", "platform", "configuration"):
        value = release_manifest.get(key)
        if not isinstance(value, str) or not value.strip():
            raise FoundationError(f"release manifest {key} must be a non-empty string")
    files = release_manifest.get("files")
    if not isinstance(files, list):
        raise FoundationError("release manifest files must be an array")

    expected: dict[str, dict[str, Any]] = {}
    required_fields = {"path", "size_bytes", "sha256", "executable"}
    for item in files:
        if not isinstance(item, dict) or set(item) != required_fields:
            raise FoundationError("release manifest contains an invalid file record")
        relative = item["path"]
        if not isinstance(relative, str) or not relative.strip():
            raise FoundationError("release manifest file path must be non-empty")
        if relative == "release-manifest.json" or relative in expected:
            raise FoundationError(f"duplicate or reserved release path: {relative}")
        if (
            isinstance(item["size_bytes"], bool)
            or not isinstance(item["size_bytes"], int)
            or item["size_bytes"] < 0
            or not isinstance(item["sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is None
            or not isinstance(item["executable"], bool)
        ):
            raise FoundationError(f"invalid release metadata for: {relative}")
        expected[relative] = item

    actual = {
        item["path"]: item
        for item in _inventory(root, excluded={"release-manifest.json"})
    }
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    errors = [*(f"missing file: {value}" for value in missing)]
    errors.extend(f"unexpected file: {value}" for value in unexpected)
    for relative in sorted(set(expected) & set(actual)):
        recorded = expected[relative]
        observed = actual[relative]
        if observed["size_bytes"] != recorded["size_bytes"]:
            errors.append(f"size mismatch: {relative}")
        if observed["sha256"] != recorded["sha256"]:
            errors.append(f"digest mismatch: {relative}")
        if observed["executable"] != recorded["executable"]:
            errors.append(f"executable mode mismatch: {relative}")

    provenance = release_manifest.get("provenance")
    if not isinstance(provenance, dict):
        errors.append("release provenance must be an object")
    else:
        if provenance.get("revision_matches_checkout") is not True:
            errors.append(
                "release provenance is not bound to the checked-out candidate"
            )
        if provenance.get("source_tree_clean") is not True:
            errors.append("release provenance was produced from a dirty source tree")
        try:
            embedded_provenance = load_json(root / "provenance.json")
        except FoundationError as exc:
            errors.append(str(exc))
        else:
            if embedded_provenance != provenance:
                errors.append("embedded provenance does not match release manifest")

    payload = release_manifest.get("payload")
    payload_digest = None
    if payload is not None:
        if not isinstance(payload, dict) or set(payload) != {"files", "sha256"}:
            errors.append("release payload metadata is invalid")
        else:
            payload_paths = payload.get("files")
            payload_digest = payload.get("sha256")
            if (
                not isinstance(payload_paths, list)
                or not payload_paths
                or not all(
                    isinstance(value, str) and value.strip() for value in payload_paths
                )
                or payload_paths != sorted(set(payload_paths))
                or not isinstance(payload_digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", payload_digest) is None
            ):
                errors.append("release payload metadata is invalid")
            else:
                expected_payload_paths = sorted(
                    set(expected) - {"provenance.json", "sbom.spdx.json"}
                )
                if payload_paths != expected_payload_paths:
                    errors.append("release payload inventory is not closed")
                elif not set(payload_paths).issubset(actual):
                    errors.append("release payload inventory references missing files")
                else:
                    observed_payload = [actual[value] for value in payload_paths]
                    if _inventory_digest(observed_payload) != payload_digest:
                        errors.append("release payload digest mismatch")

    try:
        sbom = load_json(root / "sbom.spdx.json")
    except FoundationError as exc:
        errors.append(str(exc))
    else:
        errors.extend(
            _validate_embedded_sbom(
                sbom,
                project=release_manifest["project"],
                version=release_manifest["version"],
                files=actual,
            )
        )
    if errors:
        raise FoundationError("; ".join(errors))
    return {
        "schema_version": 1,
        "overall_pass": True,
        "archive": str(archive),
        "archive_sha256": digest,
        "project": release_manifest["project"],
        "version": release_manifest["version"],
        "platform": release_manifest["platform"],
        "file_count": len(files),
        "payload_sha256": payload_digest,
    }


def _validate_embedded_sbom(
    document: Any,
    *,
    project: str,
    version: str,
    files: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["embedded SBOM must be a JSON object"]
    for key, expected in (
        ("spdxVersion", "SPDX-2.3"),
        ("dataLicense", "CC0-1.0"),
        ("SPDXID", "SPDXRef-DOCUMENT"),
    ):
        if document.get(key) != expected:
            errors.append(f"embedded SBOM {key} must be {expected}")

    packages = document.get("packages")
    application = None
    if isinstance(packages, list):
        application = next(
            (
                item
                for item in packages
                if isinstance(item, dict) and item.get("SPDXID") == "SPDXRef-Package"
            ),
            None,
        )
    if not isinstance(application, dict):
        errors.append("embedded SBOM application package is missing")
    elif (
        application.get("name") != project or application.get("versionInfo") != version
    ):
        errors.append("embedded SBOM package identity does not match the release")

    sbom_files = document.get("files")
    observed: dict[str, str] = {}
    identifiers: set[str] = set()
    if not isinstance(sbom_files, list):
        errors.append("embedded SBOM files must be an array")
    else:
        for item in sbom_files:
            if not isinstance(item, dict):
                errors.append("embedded SBOM contains an invalid file record")
                continue
            name = item.get("fileName")
            identifier = item.get("SPDXID")
            checksums = item.get("checksums")
            if (
                not isinstance(name, str)
                or not name.startswith("./")
                or not isinstance(identifier, str)
                or not identifier
                or name in observed
                or identifier in identifiers
                or not isinstance(checksums, list)
            ):
                errors.append(
                    "embedded SBOM contains duplicate or invalid file metadata"
                )
                continue
            sha256_values = [
                value.get("checksumValue")
                for value in checksums
                if isinstance(value, dict) and value.get("algorithm") == "SHA256"
            ]
            if (
                len(sha256_values) != 1
                or not isinstance(sha256_values[0], str)
                or re.fullmatch(r"[0-9a-f]{64}", sha256_values[0]) is None
            ):
                errors.append(f"embedded SBOM SHA256 is invalid: {name}")
                continue
            observed[name[2:]] = sha256_values[0]
            identifiers.add(identifier)

    expected = {
        name: item["sha256"]
        for name, item in files.items()
        if name not in {"sbom.spdx.json", "release-manifest.json"}
    }
    if observed != expected:
        errors.append("embedded SBOM file inventory does not match the release")
    return errors


def _verify_and_extract(
    archive: Path, checksum: Path | None, destination: Path | None
) -> dict[str, Any]:
    if not archive.is_file():
        raise FoundationError(f"release archive not found: {archive}")
    if destination is not None:
        if destination.exists():
            raise FoundationError(f"destination already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_parent = destination.parent if destination is not None else None
    try:
        with (
            archive.open("rb") as source,
            tempfile.TemporaryDirectory(
                prefix="cpp-foundation-verify-", dir=temporary_parent
            ) as temporary_name,
        ):
            digest = _stream_digest(source)
            _validate_checksum(archive, checksum, digest)
            temporary = Path(temporary_name)
            with tarfile.open(fileobj=source, mode="r:gz") as tar_stream:
                members = _safe_members(tar_stream)
                tar_stream.extractall(temporary, members=members, filter="data")
            roots = list(temporary.iterdir())
            if len(roots) != 1 or not roots[0].is_dir():
                raise FoundationError(
                    "release archive must contain exactly one top-level directory"
                )
            verification = _validate_release_root(roots[0], archive, digest)
            if destination is not None:
                os.replace(roots[0], destination)
            return verification
    except tarfile.TarError as exc:
        raise FoundationError(f"invalid release archive: {exc}") from exc


def verify_release(archive: Path, checksum: Path | None = None) -> dict[str, Any]:
    return _verify_and_extract(archive, checksum, None)


def extract_verified_release(
    archive: Path, destination: Path, checksum: Path
) -> dict[str, Any]:
    return _verify_and_extract(archive, checksum, destination)
