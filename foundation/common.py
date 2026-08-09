from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class FoundationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any, *, create_only: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if create_only and path.exists():
        raise FoundationError(f"refusing to replace create-only record: {path}")
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FoundationError(f"cannot read JSON {path}: {exc}") from exc


def relative_path(root: Path, value: str, *, must_exist: bool = False) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise FoundationError(f"path must remain relative to the project: {value}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise FoundationError(f"path escapes project root: {value}") from exc
    if must_exist and not resolved.exists():
        raise FoundationError(f"required path does not exist: {value}")
    return resolved


def run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: float = 300.0,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    if not command:
        raise FoundationError("command cannot be empty")
    completed = subprocess.run(
        command,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise FoundationError(
            f"command failed ({completed.returncode}): {' '.join(command)}: {detail}"
        )
    return completed
