from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterator

import yaml


TOOL_ROOT = Path(__file__).resolve().parents[1]
SUPPORT_ROOT = Path(__file__).resolve().parents[3]
NXP_ROOT = SUPPORT_ROOT.parent
WORKSPACE_ROOT = NXP_ROOT / "workspace"
WORK_ROOT = SUPPORT_ROOT / "work"

HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class ToolError(ValueError):
    pass


def timestamp_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_yaml(path: Path, label: str) -> Any:
    if not path.is_file():
        raise ToolError(f"{label} not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        raise ToolError(f"cannot read {label} {path}: {exc}") from exc


def mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ToolError(f"{label} must be a mapping")
    return value


def sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ToolError(f"{label} must be a list")
    return value


def text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ToolError(f"{label} must be a string")
    result = value.strip()
    if not result and not allow_empty:
        raise ToolError(f"{label} must not be empty")
    return result


def integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ToolError(f"{label} must be an integer >= {minimum}")
    return value


def identifier(value: Any, label: str) -> str:
    result = text(value, label)
    if not ID_RE.fullmatch(result):
        raise ToolError(
            f"{label} must match {ID_RE.pattern}: {result!r}"
        )
    return result


def reject_unknown(
    value: dict[str, Any], allowed: set[str], label: str
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ToolError(
            f"{label} has unsupported fields: {', '.join(unknown)}"
        )


def require_keys(
    value: dict[str, Any], required: set[str], label: str
) -> None:
    missing = sorted(required - set(value))
    if missing:
        raise ToolError(f"{label} is missing fields: {', '.join(missing)}")


def json_value(value: Any, label: str) -> Any:
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ToolError(f"{label} must contain JSON-compatible values") from exc
    return value


def hash_data(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def resolve_case_root(value: Any) -> Path:
    raw = text(value, "case_root")
    path = Path(raw)
    if not path.is_absolute():
        raise ToolError("case_root must be an absolute path")
    path = path.resolve(strict=False)
    work_root = WORK_ROOT.resolve(strict=False)
    if path.parent != work_root:
        raise ToolError(f"case_root must be a direct child of {work_root}: {path}")
    if not path.is_dir():
        raise ToolError(f"case_root is not a directory: {path}")
    if not (path / "README.md").is_file():
        raise ToolError(f"case README.md not found: {path / 'README.md'}")
    return path


def relative_path(value: Any, label: str) -> str:
    result = text(value, label)
    path = Path(result)
    if path.is_absolute() or ".." in path.parts or result in {".", ""}:
        raise ToolError(f"{label} must be a safe relative path: {result!r}")
    return path.as_posix()


def atomic_write_yaml(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(
        value,
        allow_unicode=True,
        sort_keys=False,
    ).encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def case_lock(case_root: Path) -> Iterator[None]:
    state_dir = case_root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / ".task-tool.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ToolError(
                f"task state is locked by another process: {case_root}"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
