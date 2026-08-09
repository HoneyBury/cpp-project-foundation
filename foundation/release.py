from __future__ import annotations

import os
import platform as host_platform
import re
import shutil
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
        provenance = build_provenance(manifest, configuration)
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
    for member in members:
        path = Path(member.name)
        if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
            raise FoundationError(f"unsafe release archive member: {member.name}")
        if path.parts:
            roots.add(path.parts[0])
    if len(roots) != 1:
        raise FoundationError(
            "release archive must contain exactly one top-level directory"
        )
    return members


def verify_release(archive: Path, checksum: Path | None = None) -> dict[str, Any]:
    if not archive.is_file():
        raise FoundationError(f"release archive not found: {archive}")
    digest = sha256_file(archive)
    if checksum is not None:
        fields = checksum.read_text(encoding="ascii").strip().split()
        if len(fields) != 2 or fields[0] != digest or fields[1] != archive.name:
            raise FoundationError("release checksum does not match archive")
    with tempfile.TemporaryDirectory(prefix="cpp-foundation-verify-") as temporary_name:
        temporary = Path(temporary_name)
        with tarfile.open(archive, "r:gz") as stream:
            members = _safe_members(stream)
            stream.extractall(temporary, members=members, filter="data")
        roots = list(temporary.iterdir())
        root = roots[0]
        release_manifest = load_json(root / "release-manifest.json")
        errors = []
        for item in release_manifest.get("files", []):
            path = relative_path(root, str(item.get("path", "")), must_exist=True)
            if path.stat().st_size != item.get("size_bytes"):
                errors.append(f"size mismatch: {item.get('path')}")
            if sha256_file(path) != item.get("sha256"):
                errors.append(f"digest mismatch: {item.get('path')}")
        provenance = release_manifest.get("provenance", {})
        if provenance.get("revision_matches_checkout") is not True:
            errors.append(
                "release provenance is not bound to the checked-out candidate"
            )
        if errors:
            raise FoundationError("; ".join(errors))
        return {
            "schema_version": 1,
            "overall_pass": True,
            "archive": str(archive),
            "archive_sha256": digest,
            "project": release_manifest.get("project"),
            "version": release_manifest.get("version"),
            "platform": release_manifest.get("platform"),
            "file_count": len(release_manifest.get("files", [])),
        }


def extract_verified_release(archive: Path, destination: Path) -> Path:
    if destination.exists():
        raise FoundationError(f"destination already exists: {destination}")
    with tarfile.open(archive, "r:gz") as stream:
        members = _safe_members(stream)
        root_name = Path(members[0].name).parts[0]
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.parent / f".{destination.name}.extract-{os.getpid()}"
        shutil.rmtree(temporary, ignore_errors=True)
        temporary.mkdir()
        try:
            stream.extractall(temporary, members=members, filter="data")
            shutil.move(str(temporary / root_name), destination)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
    return destination
