from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from .common import (
    ToolError,
    atomic_write_yaml,
    hash_data,
    is_within,
    load_yaml,
    mapping_value,
    render_argv,
)
from .fingerprints import git_source_snapshot


OWNER_FILE = ".compile-tool-workspace.yaml"


def component_execution(
    manifest: dict[str, Any], component_id: str
) -> dict[str, Any] | None:
    value = manifest["components"][component_id].get("execution")
    return value if isinstance(value, dict) else None


def component_managed_git_roots(
    manifest: dict[str, Any], component_id: str
) -> list[Path]:
    component = manifest["components"][component_id]
    if "source" in component:
        source = component["source"]
        return (
            [Path(source["case_path"]).resolve()]
            if source["kind"] == "managed_git"
            else []
        )

    roots: list[Path] = []
    for source_id in component["sources"]:
        source = manifest["sources"][source_id]
        if source["kind"] == "managed_git":
            roots.append(Path(source["case_path"]).resolve())
        elif source["kind"] == "managed_git_set":
            roots.extend(
                Path(repository["case_path"]).resolve()
                for repository in source["repositories"]
            )
    return roots


def validate_component_workdirs(
    manifest: dict[str, Any],
    component_id: str,
    steps: list[dict[str, Any]],
) -> None:
    execution = component_execution(manifest, component_id)
    if execution is not None:
        workspace = Path(execution["workspace"])
        outside = [
            step["cwd"]
            for step in steps
            if not is_within(Path(step["cwd"]), workspace)
        ]
        if outside:
            raise ToolError(
                f"{manifest['target']}/{component_id} requires isolated_git; "
                f"all step cwd paths must be inside {workspace}: "
                + ", ".join(outside)
            )
        return

    source_roots = component_managed_git_roots(manifest, component_id)
    in_source = [
        step["cwd"]
        for step in steps
        if any(is_within(Path(step["cwd"]), root) for root in source_roots)
    ]
    if in_source:
        raise ToolError(
            f"{manifest['target']}/{component_id} uses a managed Git source as "
            "a writable build cwd without an isolated_git execution policy: "
            + ", ".join(in_source)
        )


def _run_with_input(
    argv: list[str], cwd: Path, payload: bytes | None = None
) -> bytes:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolError(f"cannot run {render_argv(argv)} in {cwd}: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).decode(
            "utf-8", errors="replace"
        ).strip()
        raise ToolError(
            f"command failed ({result.returncode}) in {cwd}: "
            f"{render_argv(argv)}{': ' + detail if detail else ''}"
        )
    return result.stdout


def _safe_untracked_relative(raw_path: bytes) -> Path:
    relative = Path(os.fsdecode(raw_path))
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ToolError(f"unsafe untracked source path: {relative}")
    return relative


def _copy_untracked(source: Path, destination: Path) -> None:
    result = _run_with_input(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        source,
    )
    for raw_path in (entry for entry in result.split(b"\0") if entry):
        relative = _safe_untracked_relative(raw_path)
        source_path = source / relative
        destination_path = destination / relative
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.is_symlink():
            destination_path.symlink_to(os.readlink(source_path))
        elif source_path.is_file():
            shutil.copy2(source_path, destination_path, follow_symlinks=False)
        else:
            raise ToolError(f"unsupported untracked source entry: {source_path}")


def _source_identity(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "commit": snapshot["commit"],
        "tracked_diff_sha256": snapshot["tracked_diff_sha256"],
        "untracked": snapshot["untracked"],
    }


def _owner_payload(
    manifest: dict[str, Any], component_id: str, execution: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "owner": "compile-tool",
        "case": manifest["case"],
        "case_root": manifest["case_root"],
        "target": manifest["target"],
        "component": component_id,
        "workspace": execution["workspace"],
        "policy_id": execution["policy_id"],
    }


def _prepare_owner_root(
    manifest: dict[str, Any], component_id: str, execution: dict[str, Any]
) -> Path:
    workspace = Path(execution["workspace"])
    owner_root = workspace.parent
    if owner_root.is_symlink():
        raise ToolError(f"isolated workspace owner path must not be a symlink: {owner_root}")
    existed = owner_root.exists()
    if existed and not owner_root.is_dir():
        raise ToolError(f"isolated workspace owner path is not a directory: {owner_root}")
    owner_root.mkdir(parents=True, exist_ok=True)
    marker_path = owner_root / OWNER_FILE
    expected = _owner_payload(manifest, component_id, execution)
    if marker_path.exists():
        actual = mapping_value(
            load_yaml(marker_path, "workspace owner marker"),
            "workspace owner marker",
        )
        if actual != expected:
            raise ToolError(f"isolated workspace owner marker mismatch: {marker_path}")
    else:
        entries = list(owner_root.iterdir())
        if existed and entries:
            raise ToolError(
                f"refusing to claim non-empty unowned isolated workspace: {owner_root}"
            )
        atomic_write_yaml(marker_path, expected)
    return owner_root


def materialize_component_workspace(
    manifest: dict[str, Any], component_id: str
) -> Path | None:
    execution = component_execution(manifest, component_id)
    if execution is None:
        return None
    if execution["mode"] != "isolated_git":
        raise ToolError(
            f"unsupported execution mode for {manifest['target']}/{component_id}: "
            f"{execution['mode']}"
        )

    source_spec = execution["source"]
    source = Path(source_spec["case_path"])
    canonical = Path(source_spec["canonical_path"])
    workspace = Path(execution["workspace"])
    owner_root = _prepare_owner_root(manifest, component_id, execution)
    temp_path = Path(tempfile.mkdtemp(prefix=".source.prepare-", dir=owner_root))
    try:
        _run_with_input(
            ["git", "clone", "--shared", "--no-checkout", str(canonical), str(temp_path)],
            owner_root,
        )
        source_snapshot = git_source_snapshot(source)
        _run_with_input(
            ["git", "checkout", "--detach", source_snapshot["commit"]],
            temp_path,
        )
        diff = _run_with_input(
            ["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--"],
            source,
        )
        if diff:
            _run_with_input(
                ["git", "apply", "--binary", "--whitespace=nowarn", "-"],
                temp_path,
                diff,
            )
        _copy_untracked(source, temp_path)
        materialized = git_source_snapshot(temp_path)
        if _source_identity(materialized) != _source_identity(source_snapshot):
            raise ToolError(
                f"isolated workspace does not reproduce the source identity for "
                f"{manifest['target']}/{component_id}"
            )

        if workspace.exists() or workspace.is_symlink():
            if workspace.is_symlink() or not workspace.is_dir():
                raise ToolError(f"isolated workspace is not an owned directory: {workspace}")
            shutil.rmtree(workspace)
        os.replace(temp_path, workspace)
        temp_path = Path()
        return workspace
    finally:
        if temp_path != Path() and temp_path.exists():
            shutil.rmtree(temp_path)


def execution_snapshot(component: dict[str, Any]) -> dict[str, Any] | None:
    execution = component.get("execution")
    if not isinstance(execution, dict):
        return None
    return {
        "mode": execution["mode"],
        "contract_version": execution["contract_version"],
        "policy_id": execution["policy_id"],
        "policy_path": execution["policy_path"],
        "workspace": execution["workspace"],
        "source_identity": hash_data(
            {
                "canonical_path": execution["source"]["canonical_path"],
                "case_path": execution["source"]["case_path"],
                "ref_kind": execution["source"]["ref_kind"],
                "ref": execution["source"]["ref"],
                "remote_url": execution["source"]["remote_url"],
            }
        ),
    }
