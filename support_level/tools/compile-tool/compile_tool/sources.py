from __future__ import annotations

from pathlib import Path
import posixpath
import stat
import subprocess
import sys
import tarfile
from typing import Any
import zipfile

from .common import (
    ToolError,
    atomic_write_yaml,
    hash_data,
    hash_file,
    load_yaml,
    mapping_value,
    normalize_hash,
    render_argv,
    run_command,
)


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
    *,
    kind: str = "command",
    marker: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "component": component,
        "cwd": str(cwd),
        "argv": argv,
        "purpose": purpose,
        "kind": kind,
    }
    if marker is not None:
        result["marker"] = marker
    return result


def _iter_sources(manifest: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    if manifest["schema_version"] == 1:
        entries: list[tuple[str, dict[str, Any]]] = []
        for component_id, component in manifest["components"].items():
            if component["status"] != "enabled" or component["kind"] == "fixed_input":
                continue
            entries.append((component_id, component["source"]))
        return entries

    entries = []
    for source_id, source in manifest["sources"].items():
        if source["kind"] != "managed_git_set":
            entries.append((source_id, source))
            continue
        for repository in source["repositories"]:
            member = {key: value for key, value in repository.items() if key != "name"}
            entries.append((f"{source_id}/{repository['name']}", member))
    return entries


def _safe_archive_name(name: str, label: str) -> None:
    normalized = posixpath.normpath(name.replace("\\", "/"))
    if name.startswith(("/", "\\")) or normalized == ".." or normalized.startswith("../"):
        raise ToolError(f"unsafe archive path in {label}: {name!r}")


def _safe_link_target(member_name: str, target: str, label: str) -> None:
    if target.startswith(("/", "\\")):
        raise ToolError(f"unsafe absolute archive link in {label}: {target!r}")
    resolved = posixpath.normpath(
        posixpath.join(posixpath.dirname(member_name), target.replace("\\", "/"))
    )
    if resolved == ".." or resolved.startswith("../"):
        raise ToolError(f"archive link escapes extraction root in {label}: {target!r}")


def _archive_kind(path: Path) -> str:
    lower = path.name.lower()
    if lower.endswith(".zip"):
        return "zip"
    if lower.endswith((".tar.gz", ".tgz")):
        return "tar_gz"
    if lower.endswith(".tar"):
        return "tar"
    raise ToolError(f"unsupported release archive format: {path}")


def _preflight_archive(path: Path) -> str:
    kind = _archive_kind(path)
    try:
        if kind.startswith("tar"):
            with tarfile.open(path, "r:*") as archive:
                for member in archive.getmembers():
                    _safe_archive_name(member.name, str(path))
                    if member.isdev():
                        raise ToolError(
                            f"archive contains a device node: {member.name}"
                        )
                    if member.issym() or member.islnk():
                        _safe_link_target(
                            member.name, member.linkname, f"{path}:{member.name}"
                        )
        else:
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    _safe_archive_name(member.filename, str(path))
                    mode = member.external_attr >> 16
                    if stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
                        raise ToolError(
                            f"archive contains a device node: {member.filename}"
                        )
                    if stat.S_ISLNK(mode):
                        target = archive.read(member).decode(
                            "utf-8", errors="surrogateescape"
                        )
                        _safe_link_target(
                            member.filename,
                            target,
                            f"{path}:{member.filename}",
                        )
    except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        raise ToolError(f"cannot inspect release archive {path}: {exc}") from exc
    return kind


def _archive_marker_path(case_path: Path) -> Path:
    return case_path / ".compile-tool-source.yaml"


def _archive_stat(path: Path) -> dict[str, int]:
    try:
        info = path.stat()
    except OSError as exc:
        raise ToolError(f"cannot stat release archive {path}: {exc}") from exc
    return {
        "size": info.st_size,
        "inode": info.st_ino,
        "mtime_ns": info.st_mtime_ns,
        "ctime_ns": info.st_ctime_ns,
    }


def _archive_identity(
    source: dict[str, Any],
    cached: dict[str, Any] | None = None,
) -> dict[str, Any]:
    archive_path = Path(source["archive_path"])
    if not archive_path.is_file():
        raise ToolError(
            "DOWNLOAD_REQUIRED: local release archive is unavailable; "
            f"provide the exact package: {archive_path}"
        )
    archive_stat = _archive_stat(archive_path)
    digest = (
        cached["sha256"]
        if cached
        and cached.get("archive_path") == str(archive_path)
        and cached.get("archive_stat") == archive_stat
        and isinstance(cached.get("sha256"), str)
        else hash_file(archive_path)
    )
    return {
        "archive_path": str(archive_path),
        "archive_stat": archive_stat,
        "sha256": digest,
    }


def _assess_archive(
    source_id: str,
    source: dict[str, Any],
    manifest: dict[str, Any],
    operations: list[dict[str, Any]],
    resolved: dict[str, dict[str, Any]],
    observations: dict[str, dict[str, Any]],
) -> None:
    archive_path = Path(source["archive_path"])
    case_path = Path(source["case_path"])
    marker_path = _archive_marker_path(case_path)
    marker: dict[str, Any] | None = None
    if marker_path.is_file():
        marker = mapping_value(
            load_yaml(marker_path, "release archive marker"),
            "release archive marker",
        )
    identity = _archive_identity(source, marker)
    observations[source_id] = identity
    if case_path.exists():
        if not case_path.is_dir() or not marker_path.is_file():
            raise ToolError(
                f"existing archive case path has no compile-tool provenance: {case_path}"
            )
        assert marker is not None
        if marker != {"schema_version": 1, **identity}:
            raise ToolError(
                f"release archive provenance differs from the requested package: {case_path}"
            )
        resolved[source_id] = {
            "kind": "release_archive",
            "case_path": str(case_path),
            **identity,
        }
        return

    archive_kind = _preflight_archive(archive_path)
    operations.append(
        _operation(
            source_id,
            Path(manifest["case_root"]),
            ["mkdir", "-p", str(case_path)],
            "建立 SDK 解包目录",
        )
    )
    if archive_kind == "zip":
        argv = ["unzip", "-q", str(archive_path), "-d", str(case_path)]
    elif archive_kind == "tar_gz":
        argv = [
            "tar",
            "--extract",
            "--gzip",
            "--file",
            str(archive_path),
            "--directory",
            str(case_path),
            "--no-same-owner",
            "--no-same-permissions",
        ]
    else:
        argv = [
            "tar",
            "--extract",
            "--file",
            str(archive_path),
            "--directory",
            str(case_path),
            "--no-same-owner",
            "--no-same-permissions",
        ]
    operations.append(
        _operation(
            source_id,
            Path(manifest["case_root"]),
            argv,
            "解压本地 release package",
            kind="archive_extract",
            marker={
                "path": str(marker_path),
                "data": {"schema_version": 1, **identity},
            },
        )
    )


def _assess_git(
    source_id: str,
    source: dict[str, Any],
    manifest: dict[str, Any],
    operations: list[dict[str, Any]],
    resolved: dict[str, dict[str, Any]],
    observations: dict[str, dict[str, Any]],
) -> None:
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
        resolved[source_id] = {
            "kind": "managed_git",
            "canonical_path": str(canonical),
            "case_path": str(case_path),
            "commit": case_head,
            "ref_kind": source["ref_kind"],
            "ref": source["ref"],
        }
        return

    _canonical_is_clean(canonical)
    canonical_head = _git(canonical, "rev-parse", "HEAD")
    canonical_ref = _resolve_ref(
        canonical, source["ref_kind"], source["ref"], source["remote"]
    )
    observations[source_id] = {
        "canonical_head": canonical_head,
        "remote_url": source["remote_url"],
        "resolved_commit": canonical_ref[1] if canonical_ref else None,
    }
    checkout_ref: str
    if canonical_ref is None:
        if source["ref_kind"] == "tag":
            argv = ["git", "fetch", source["remote"], "tag", source["ref"]]
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
            _operation(
                source_id,
                canonical,
                argv,
                "获取缺失的目标 ref",
                kind="git",
            )
        )
    else:
        checkout_ref = canonical_ref[1]
        if source["update"] == "pull_ff_only":
            current_branch = _git(canonical, "branch", "--show-current")
            if current_branch != source["ref"]:
                raise ToolError(
                    f"{source_id} pull_ff_only requires canonical branch "
                    f"{source['ref']!r} to be checked out"
                )
            operations.append(
                _operation(
                    source_id,
                    canonical,
                    [
                        "git",
                        "pull",
                        "--ff-only",
                        source["remote"],
                        source["ref"],
                    ],
                    "快进更新本地维护分支",
                    kind="git",
                )
            )
            checkout_ref = f"refs/heads/{source['ref']}"

    if not case_path.parent.exists():
        operations.append(
            _operation(
                source_id,
                Path(manifest["case_root"]),
                ["mkdir", "-p", str(case_path.parent)],
                "建立 case 源码父目录",
            )
        )
    operations.append(
        _operation(
            source_id,
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
            kind="git",
        )
    )


def assess_sources(manifest: dict[str, Any]) -> dict[str, Any]:
    operations: list[dict[str, Any]] = []
    resolved: dict[str, dict[str, Any]] = {}
    observations: dict[str, dict[str, Any]] = {}
    for source_id, source in _iter_sources(manifest):
        if source["kind"] == "local_files":
            missing = [path for path in source["paths"] if not Path(path).is_file()]
            if missing:
                raise ToolError(
                    f"DOWNLOAD_REQUIRED: {source_id} requires unavailable local "
                    "source files; external download is not automatic: "
                    + ", ".join(missing)
                )
            resolved[source_id] = {
                "kind": "local_files",
                "paths": source["paths"],
            }
        elif source["kind"] == "release_archive":
            _assess_archive(
                source_id,
                source,
                manifest,
                operations,
                resolved,
                observations,
            )
        else:
            _assess_git(
                source_id,
                source,
                manifest,
                operations,
                resolved,
                observations,
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
        if operation["kind"] == "git":
            _canonical_is_clean(cwd)
        process = subprocess_run(operation["argv"], cwd)
        if process != 0:
            return process
        if operation["kind"] == "archive_extract":
            marker = operation["marker"]
            atomic_write_yaml(Path(marker["path"]), marker["data"])
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
