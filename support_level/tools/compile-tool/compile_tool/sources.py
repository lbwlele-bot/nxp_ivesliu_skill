from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import Any

from .common import ToolError, hash_data, normalize_hash, render_argv, run_command


def _git(cwd: Path, *args: str, check: bool = True) -> str:
    result = run_command(["git", *args], cwd=cwd, check=check)
    return result.stdout.decode("utf-8", errors="replace").strip()


def _git_dir(path: Path) -> Path:
    value = _git(path, "rev-parse", "--git-common-dir")
    result = Path(value)
    if not result.is_absolute():
        result = path / result
    return result.resolve()


def _is_git_repo(path: Path) -> bool:
    if not path.is_dir():
        return False
    result = run_command(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == b"true"


def _resolve_ref(repo: Path, ref_kind: str, ref: str, remote: str) -> tuple[str, str] | None:
    candidates: list[str]
    if ref_kind == "tag":
        candidates = [f"refs/tags/{ref}"]
    elif ref_kind == "branch":
        candidates = [f"refs/heads/{ref}", f"refs/remotes/{remote}/{ref}"]
    else:
        candidates = [ref]
    for candidate in candidates:
        result = run_command(
            ["git", "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"],
            cwd=repo,
            check=False,
        )
        if result.returncode == 0:
            return candidate, result.stdout.decode("ascii").strip()
    return None


def _validate_remote(source: dict[str, Any], canonical: Path) -> None:
    remote = source["remote"]
    actual = _git(canonical, "remote", "get-url", remote)
    if actual != source["remote_url"]:
        raise ToolError(
            f"managed source remote mismatch for {canonical}: "
            f"expected {source['remote_url']!r}, got {actual!r}"
        )


def _canonical_is_clean(canonical: Path) -> None:
    status = _git(
        canonical,
        "status",
        "--porcelain=v1",
        "--untracked-files=normal",
    )
    if status:
        raise ToolError(f"canonical repository is not clean: {canonical}")


def _validate_case_provenance(
    case_path: Path,
    canonical: Path,
    expected_remote: str,
) -> None:
    case_common = _git_dir(case_path)
    canonical_common = _git_dir(canonical)
    if case_common == canonical_common:
        return
    remotes = _git(case_path, "remote", "-v")
    canonical_text = str(canonical.resolve())
    if canonical_text in remotes or expected_remote in remotes:
        return
    raise ToolError(
        f"existing case checkout has no verified canonical provenance: {case_path}"
    )


def _operation(
    component: str,
    cwd: Path,
    argv: list[str],
    purpose: str,
) -> dict[str, Any]:
    return {
        "component": component,
        "cwd": str(cwd),
        "argv": argv,
        "purpose": purpose,
    }


def assess_sources(manifest: dict[str, Any]) -> dict[str, Any]:
    operations: list[dict[str, Any]] = []
    resolved: dict[str, dict[str, Any]] = {}
    observations: dict[str, dict[str, Any]] = {}
    for component_id, component in manifest["components"].items():
        if component["status"] != "enabled" or component["kind"] == "fixed_input":
            continue
        source = component["source"]
        if source["kind"] == "local_files":
            missing = [path for path in source["paths"] if not Path(path).is_file()]
            if missing:
                raise ToolError(
                    f"DOWNLOAD_REQUIRED: {component_id} requires unavailable local "
                    "source files; external download is not automatic: "
                    + ", ".join(missing)
                )
            resolved[component_id] = {
                "kind": "local_files",
                "paths": source["paths"],
            }
            continue

        canonical = Path(source["canonical_path"])
        case_path = Path(source["case_path"])
        if not _is_git_repo(canonical):
            raise ToolError(f"managed canonical source is not a Git work tree: {canonical}")
        _validate_remote(source, canonical)

        if case_path.exists():
            if not _is_git_repo(case_path):
                raise ToolError(f"case source path exists but is not a Git work tree: {case_path}")
            _validate_case_provenance(case_path, canonical, source["remote_url"])
            case_ref = _resolve_ref(
                case_path, source["ref_kind"], source["ref"], source["remote"]
            )
            case_head = _git(case_path, "rev-parse", "HEAD")
            if case_ref is None or case_ref[1] != case_head:
                raise ToolError(
                    f"existing case checkout does not match requested ref "
                    f"{source['ref']!r}: {case_path}"
                )
            resolved[component_id] = {
                "kind": "managed_git",
                "canonical_path": str(canonical),
                "case_path": str(case_path),
                "commit": case_head,
                "ref_kind": source["ref_kind"],
                "ref": source["ref"],
            }
            continue

        _canonical_is_clean(canonical)
        canonical_head = _git(canonical, "rev-parse", "HEAD")
        canonical_ref = _resolve_ref(
            canonical, source["ref_kind"], source["ref"], source["remote"]
        )
        observations[component_id] = {
            "canonical_head": canonical_head,
            "remote_url": source["remote_url"],
            "resolved_commit": canonical_ref[1] if canonical_ref else None,
        }
        checkout_ref: str
        if canonical_ref is None:
            if source["ref_kind"] == "tag":
                argv = [
                    "git",
                    "fetch",
                    source["remote"],
                    "tag",
                    source["ref"],
                ]
                checkout_ref = f"refs/tags/{source['ref']}"
            elif source["ref_kind"] == "branch":
                destination = f"refs/remotes/{source['remote']}/{source['ref']}"
                argv = [
                    "git",
                    "fetch",
                    source["remote"],
                    f"refs/heads/{source['ref']}:{destination}",
                ]
                checkout_ref = destination
            else:
                argv = ["git", "fetch", source["remote"], source["ref"]]
                checkout_ref = source["ref"]
            operations.append(
                _operation(component_id, canonical, argv, "获取缺失的目标 ref")
            )
        else:
            checkout_ref = canonical_ref[1]
            if source["update"] == "pull_ff_only":
                current_branch = _git(canonical, "branch", "--show-current")
                if current_branch != source["ref"]:
                    raise ToolError(
                        f"{component_id} pull_ff_only requires canonical branch "
                        f"{source['ref']!r} to be checked out"
                    )
                operations.append(
                    _operation(
                        component_id,
                        canonical,
                        [
                            "git",
                            "pull",
                            "--ff-only",
                            source["remote"],
                            source["ref"],
                        ],
                        "快进更新本地维护分支",
                    )
                )
                checkout_ref = f"refs/heads/{source['ref']}"

        if not case_path.parent.exists():
            operations.append(
                _operation(
                    component_id,
                    Path(manifest["case_root"]),
                    ["mkdir", "-p", str(case_path.parent)],
                    "建立 case 源码父目录",
                )
            )
        operations.append(
            _operation(
                component_id,
                canonical,
                [
                    "git",
                    "worktree",
                    "add",
                    "--detach",
                    str(case_path),
                    checkout_ref,
                ],
                "建立当前 case 的 detached worktree",
            )
        )

    payload = {
        "manifest_hash": manifest["hash"],
        "operations": operations,
        "observations": observations,
    }
    return {
        "status": "ACQUIRE_REQUIRED" if operations else "READY",
        "operations": operations,
        "resolved": resolved,
        "observations": observations,
        "plan_hash": hash_data(payload),
    }


def render_acquisition(manifest: dict[str, Any], result: dict[str, Any]) -> str:
    lines = [
        "[源码准备声明]",
        "",
        f"Case：{manifest['case']}",
        f"编译对象：{manifest['target']}",
    ]
    if not result["operations"]:
        lines.extend(["", "源码状态：本地 checkout 已就绪", "Decision：READY"])
        return "\n".join(lines)
    lines.extend(["", "原始源码准备命令："])
    for index, operation in enumerate(result["operations"], start=1):
        lines.append(f"{index}. {operation['component']}：{operation['purpose']}")
        lines.append(f"   工作目录：{operation['cwd']}")
        lines.append(f"   $ {render_argv(operation['argv'])}")
    lines.extend(
        [
            "",
            f"Acquisition plan hash：{result['plan_hash']}",
            "Decision：ACQUIRE_REQUIRED",
        ]
    )
    return "\n".join(lines)


def execute_acquisition(
    manifest: dict[str, Any],
    supplied_hash: str,
) -> int:
    result = assess_sources(manifest)
    expected = result["plan_hash"]
    if normalize_hash(supplied_hash, "acquisition plan hash") != expected:
        raise ToolError("acquisition plan hash mismatch; run assess again")
    if not result["operations"]:
        raise ToolError("no source acquisition is required")
    print(render_acquisition(manifest, result), flush=True)
    print("\nAcquisition：STARTING", flush=True)
    for operation in result["operations"]:
        cwd = Path(operation["cwd"])
        if operation["argv"][1] in {"pull", "fetch", "worktree"}:
            _canonical_is_clean(cwd)
        process = subprocess_run(operation["argv"], cwd)
        if process != 0:
            return process
    final = assess_sources(manifest)
    if final["operations"]:
        raise ToolError("source acquisition completed but case checkout is still unresolved")
    print("\ncompile-tool: source acquisition completed")
    return 0


def subprocess_run(argv: list[str], cwd: Path) -> int:
    try:
        result = subprocess.run(argv, cwd=cwd, check=False)
    except OSError as exc:
        raise ToolError(f"cannot execute {render_argv(argv)}: {exc}") from exc
    if result.returncode != 0:
        print(
            f"compile-tool: source command failed ({result.returncode}): "
            f"{render_argv(argv)}",
            file=sys.stderr,
        )
    return result.returncode
