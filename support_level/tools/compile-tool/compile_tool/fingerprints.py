from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any

from .common import ToolError, hash_data, hash_file, render_argv, run_command


def _stat_payload(path: Path) -> dict[str, int]:
    try:
        info = path.stat()
    except OSError as exc:
        raise ToolError(f"cannot stat {path}: {exc}") from exc
    return {
        "size": info.st_size,
        "inode": info.st_ino,
        "mtime_ns": info.st_mtime_ns,
        "ctime_ns": info.st_ctime_ns,
    }


def file_snapshot(
    path: Path,
    previous: dict[str, Any] | None = None,
    *,
    require_nonempty: bool,
) -> dict[str, Any]:
    if not path.is_file():
        raise ToolError(f"required file is missing: {path}")
    stat = _stat_payload(path)
    if require_nonempty and stat["size"] == 0:
        raise ToolError(f"required output is empty: {path}")
    if (
        previous
        and previous.get("path") == str(path)
        and previous.get("stat") == stat
        and isinstance(previous.get("sha256"), str)
    ):
        digest = previous["sha256"]
    else:
        digest = hash_file(path)
    return {"path": str(path), "stat": stat, "sha256": digest}


def file_snapshots(
    paths: list[str],
    previous: list[dict[str, Any]] | None = None,
    *,
    require_nonempty: bool,
) -> list[dict[str, Any]]:
    previous_by_path = {
        entry["path"]: entry
        for entry in (previous or [])
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    }
    return [
        file_snapshot(
            Path(path),
            previous_by_path.get(path),
            require_nonempty=require_nonempty,
        )
        for path in paths
    ]


def optional_output_snapshots(
    paths: list[str],
    previous: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    previous_by_path = {
        entry["path"]: entry
        for entry in (previous or [])
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    }
    snapshots: list[dict[str, Any]] = []
    invalid: list[str] = []
    for value in paths:
        path = Path(value)
        if not path.is_file():
            invalid.append(f"output missing: {path}")
            continue
        try:
            snapshot = file_snapshot(
                path,
                previous_by_path.get(value),
                require_nonempty=True,
            )
        except ToolError as exc:
            invalid.append(str(exc))
            continue
        snapshots.append(snapshot)
    return snapshots, invalid


def _stream_hash(argv: list[str], cwd: Path) -> str:
    digest = hashlib.sha256()
    with tempfile.TemporaryFile() as stderr_handle:
        try:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=stderr_handle,
            )
        except OSError as exc:
            raise ToolError(f"cannot run {render_argv(argv)}: {exc}") from exc
        if process.stdout is None:
            raise ToolError(f"cannot capture output from {render_argv(argv)}")
        for block in iter(lambda: process.stdout.read(1024 * 1024), b""):
            digest.update(block)
        result = process.wait()
        stderr_handle.seek(0)
        stderr = stderr_handle.read()
    if result != 0:
        raise ToolError(
            f"command failed ({result}) in {cwd}: {render_argv(argv)}: "
            f"{stderr.decode('utf-8', errors='replace').strip()}"
        )
    return "sha256:" + digest.hexdigest()


def _untracked_snapshots(repo: Path) -> list[dict[str, Any]]:
    result = run_command(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=repo,
    )
    raw_paths = [entry for entry in result.stdout.split(b"\0") if entry]
    snapshots: list[dict[str, Any]] = []
    for raw_path in sorted(raw_paths):
        relative = os.fsdecode(raw_path)
        path = repo / relative
        if path.is_symlink():
            target = os.readlink(path)
            snapshots.append(
                {
                    "path": relative,
                    "kind": "symlink",
                    "sha256": hash_data({"target": target}),
                }
            )
        elif path.is_file():
            snapshots.append(
                {
                    "path": relative,
                    "kind": "file",
                    "size": path.stat().st_size,
                    "sha256": hash_file(path),
                }
            )
        else:
            raise ToolError(f"unsupported untracked source entry: {path}")
    return snapshots


def git_source_snapshot(repo: Path) -> dict[str, Any]:
    head = run_command(["git", "rev-parse", "HEAD"], cwd=repo).stdout.decode(
        "ascii"
    ).strip()
    tracked_diff = _stream_hash(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--"],
        repo,
    )
    return {
        "kind": "managed_git",
        "path": str(repo),
        "commit": head,
        "tracked_diff_sha256": tracked_diff,
        "untracked": _untracked_snapshots(repo),
    }


def source_snapshot(
    source: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if source["kind"] == "managed_git":
        result = git_source_snapshot(Path(source["case_path"]))
        result.update(
            {
                "canonical_path": source["canonical_path"],
                "ref_kind": source["ref_kind"],
                "ref": source["ref"],
                "remote_url": source["remote_url"],
            }
        )
        return result
    previous_files = (previous or {}).get("files")
    return {
        "kind": "local_files",
        "files": file_snapshots(
            source["paths"],
            previous_files,
            require_nonempty=False,
        ),
    }


def configuration_snapshot(
    configuration: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "values": configuration["values"],
        "files": file_snapshots(
            configuration["files"],
            (previous or {}).get("files"),
            require_nonempty=False,
        )
        if configuration["files"]
        else [],
    }


def toolchain_snapshots(toolchains: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for toolchain in toolchains:
        executable = Path(toolchain["executable"])
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ToolError(f"toolchain executable is unavailable: {executable}")
        command = [str(executable), *toolchain["version_args"]]
        process = run_command(command, cwd=executable.parent, timeout=15)
        version_output = (process.stdout + process.stderr).decode(
            "utf-8", errors="replace"
        )
        result.append(
            {
                "executable": str(executable.resolve()),
                "version_args": toolchain["version_args"],
                "version_sha256": hash_data({"output": version_output}),
                "version_output": version_output.strip(),
            }
        )
    return result


def content_identity(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"path": entry["path"], "sha256": entry["sha256"]} for entry in entries]
