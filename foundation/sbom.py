from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from .common import FoundationError


def _dependency(reference: str) -> dict[str, str]:
    pinned = reference.split("%", maxsplit=1)[0]
    coordinate, _, revision = pinned.partition("#")
    name_version = coordinate.split("@", maxsplit=1)[0]
    name, separator, version = name_version.partition("/")
    if not separator or not revision:
        raise FoundationError(f"Conan dependency is not revision-pinned: {reference}")
    identifier = re.sub(r"[^A-Za-z0-9.-]", "-", f"{name}-{version}")
    return {"name": name, "version": version, "revision": revision, "id": identifier}


def conan_lock_to_spdx(lockfile: Path, output: Path) -> dict[str, object]:
    lock_bytes = lockfile.read_bytes()
    lock = json.loads(lock_bytes)
    lock_digest = hashlib.sha256(lock_bytes).hexdigest()
    dependencies = [_dependency(str(value)) for value in lock.get("requires", [])]
    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "conan-locked-dependencies",
        "documentNamespace": f"https://spdx.org/spdxdocs/conan-lock-{lock_digest}",
        "creationInfo": {
            "created": datetime.now(UTC)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "creators": ["Tool: cpp-project-foundation-conan-lock-to-spdx"],
        },
        "packages": [
            {
                "name": item["name"],
                "SPDXID": f"SPDXRef-Conan-{item['id']}",
                "versionInfo": item["version"],
                "sourceInfo": f"Conan recipe revision: {item['revision']}",
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
                            f"pkg:conan/{quote(item['name'])}@{quote(item['version'])}"
                        ),
                    }
                ],
            }
            for item in dependencies
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "schema_version": 1,
        "overall_pass": True,
        "dependency_count": len(dependencies),
        "output": str(output),
    }
