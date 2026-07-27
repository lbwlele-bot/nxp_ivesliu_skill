from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from typing import Any, Iterator, Sequence

import yaml


HASH_RE = re.compile(r"^(?:sha256:)?([0-9a-fA-F]{64})$")
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/+@{}~-]*$")
MAX_COMMAND_OUTPUT = 64 * 1024


class ToolError(ValueError):
    pass


def text_value(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ToolError(f"{label} must be a string")
    result = value.strip()
    if not result:
        raise ToolError(f"{label} must not be empty")
    return result


def mapping_value(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ToolError(f"{label} must be a mapping")
    return value


def reject_unknown_keys(
    data: dict[str, Any], allowed: set[str], label: str
) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ToolError(f"{label} has unsupported fields: {', '.join(unknown)}")


def load_yaml(path: Path, label: str) -> Any:
    if not path.is_file():
        raise ToolError(f"{label} not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        raise ToolError(f"cannot read {label} {path}: {exc}") from exc


def canonical_json(data: Any) -> bytes:
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def hash_data(data: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(data)).hexdigest()


def hash_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ToolError(f"cannot hash file {path}: {exc}") from exc
    return "sha256:" + digest.hexdigest()


def normalize_hash(value: str, label: str = "hash") -> str:
    match = HASH_RE.fullmatch(value.strip())
    if not match:
        raise ToolError(
            f"{label} must be a SHA-256 hex digest, with optional sha256: prefix"
        )
    return "sha256:" + match.group(1).lower()


def resolve_absolute(path_value: Any, label: str) -> Path:
    value = text_value(path_value, label)
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ToolError(f"{label} must be an absolute path")
    return path.resolve(strict=False)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def require_within(path: Path, root: Path, label: str) -> None:
    if not is_within(path, root):
        raise ToolError(f"{label} must be inside {root}: {path}")


def run_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    check: bool = True,
    timeout: int = 30,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            list(argv),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolError(f"cannot run {render_argv(argv)} in {cwd}: {exc}") from exc
    if len(result.stdout) > MAX_COMMAND_OUTPUT or len(result.stderr) > MAX_COMMAND_OUTPUT:
        raise ToolError(f"command output exceeds {MAX_COMMAND_OUTPUT} bytes")
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).decode(
            "utf-8", errors="replace"
        ).strip()
        raise ToolError(
            f"command failed ({result.returncode}) in {cwd}: "
            f"{render_argv(argv)}{': ' + detail if detail else ''}"
        )
    return result


def render_argv(argv: Sequence[str]) -> str:
    return " ".join(shlex.quote(str(item)) for item in argv)


def atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
    ).encode("utf-8")
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def case_lock(case_root: Path) -> Iterator[None]:
    state_dir = case_root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / ".compile-tool.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ToolError(f"compile state is locked by another process: {case_root}") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
