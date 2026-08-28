from __future__ import annotations

from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import tarfile
from typing import Any
import zipfile

import yaml

from .common import (
    REF_RE,
    ToolError,
    atomic_write_yaml,
    case_lock,
    hash_data,
    hash_file,
    load_yaml,
    mapping_value,
    normalize_hash,
    reject_unknown_keys,
    require_within,
    run_command,
    text_value,
)
from .manifest import load_manifest
from .planner import assess
from .request import execute_v2, load_request, render_report
from .sources import execute_acquisition, render_acquisition
from .state import load_state, write_state


CHECKLIST_KIND = "m_freertos_sdk_compile_checklist"
TARGET = "m_freertos_sdk"
TOOL_DIR = Path(__file__).resolve().parents[1]
SUPPORT_LEVEL = TOOL_DIR.parent.parent
TARGET_ROOT = SUPPORT_LEVEL / "compile_targets" / TARGET
TEMPLATE_PATH = TARGET_ROOT / "COMPILE_CHECKLIST.yaml"
CATALOG_PATH = SUPPORT_LEVEL / "release_packages" / TARGET / "PACKAGES.yaml"
PREPARED_NAME = ".compile-tool-prepared.yaml"
REQUEST_NAME = ".compile-tool-request.yaml"


def is_m_sdk_checklist(path: Path) -> bool:
    value = load_yaml(path, "compile input")
    return isinstance(value, dict) and value.get("kind") == CHECKLIST_KIND


def _scalar(value: Any, label: str) -> str:
    result = text_value(value, label)
    if result.casefold() in {"tbd", "unknown", "n/a", "na", "none"}:
        raise ToolError(f"{label} must be resolved")
    return result


def _safe_id(value: Any, label: str) -> str:
    result = _scalar(value, label)
    if not REF_RE.fullmatch(result) or "/" in result:
        raise ToolError(f"{label} contains unsafe characters: {result!r}")
    return result


def _safe_relative(value: Any, label: str) -> str:
    raw = text_value(value, label)
    path = PurePosixPath(raw)
    if path.is_absolute() or not path.parts or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise ToolError(f"{label} must be a safe relative path")
    return path.as_posix()


def _case_path(value: Any, label: str, case_root: Path) -> Path:
    raw = Path(text_value(value, label)).expanduser()
    path = raw.resolve(strict=False) if raw.is_absolute() else (case_root / raw).resolve(strict=False)
    require_within(path, case_root, label)
    return path


def _catalog() -> dict[str, dict[str, Any]]:
    """Load package metadata without probing every archive on disk."""
    root = mapping_value(load_yaml(CATALOG_PATH, "M SDK package catalog"), "M SDK package catalog")
    reject_unknown_keys(root, {"schema_version", "kind", "packages"}, "M SDK package catalog")
    if root.get("schema_version") != 1 or root.get("kind") != "m_freertos_sdk_package_catalog":
        raise ToolError("M SDK package catalog identity is invalid")
    packages = mapping_value(root.get("packages"), "M SDK package catalog.packages")
    result: dict[str, dict[str, Any]] = {}
    for package_id, raw_value in packages.items():
        package = _safe_id(package_id, "M SDK package id")
        label = f"M SDK package catalog.packages.{package}"
        item = mapping_value(raw_value, label)
        reject_unknown_keys(
            item,
            {
                "archive",
                "sha256",
                "sdk_release",
                "soc",
                "boards",
                "compiler_version_contains",
            },
            label,
        )
        archive_relative = _safe_relative(item.get("archive"), f"{label}.archive")
        archive = (CATALOG_PATH.parent / archive_relative).resolve(strict=False)
        require_within(archive, CATALOG_PATH.parent.resolve(), f"{label}.archive")
        expected_hash = normalize_hash(_scalar(item.get("sha256"), f"{label}.sha256"))
        boards_raw = mapping_value(item.get("boards"), f"{label}.boards")
        boards: dict[str, dict[str, str]] = {}
        for board_id, board_value in boards_raw.items():
            board = _safe_id(board_id, f"{label}.boards key")
            board_item = mapping_value(board_value, f"{label}.boards.{board}")
            reject_unknown_keys(board_item, {"core_roles"}, f"{label}.boards.{board}")
            roles_raw = mapping_value(
                board_item.get("core_roles"), f"{label}.boards.{board}.core_roles"
            )
            roles = {
                _safe_id(core, f"{label}.boards.{board}.core_roles key"): _safe_id(
                    role, f"{label}.boards.{board}.core_roles.{core}"
                )
                for core, role in roles_raw.items()
            }
            if not roles:
                raise ToolError(f"{label}.boards.{board}.core_roles must not be empty")
            boards[board] = roles
        result[package] = {
            "id": package,
            "archive": str(archive),
            "sha256": expected_hash,
            "sdk_release": _scalar(item.get("sdk_release"), f"{label}.sdk_release"),
            "soc": _safe_id(item.get("soc"), f"{label}.soc"),
            "boards": boards,
            "compiler_version_contains": (
                _scalar(item.get("compiler_version_contains"), f"{label}.compiler_version_contains")
                if item.get("compiler_version_contains") is not None
                else None
            ),
        }
    return result


def _package_required(
    package_id: str,
    *,
    archive: Path | None,
    sdk_release: str | None,
) -> ToolError:
    location = str(archive) if archive is not None else "当前 case 的 inputs/sdk/ 目录"
    release = sdk_release or "请按目标板和软件栈确认"
    return ToolError(
        "STATUS: USER_INPUT_REQUIRED\n"
        "INPUT: NXP MCUX SDK package\n"
        f"PACKAGE: {package_id}\n"
        f"SDK_RELEASE: {release}\n"
        f"EXPECTED_LOCATION: {location}\n"
        "ACTION: 请用户登录 NXP 下载对应官方 SDK；AI 不自动登录或下载。"
    )


def _resolve_package(
    sdk: dict[str, Any],
    case_root: Path,
) -> dict[str, Any]:
    reject_unknown_keys(
        sdk,
        {"package", "archive", "sdk_release", "trust_reason", "compiler"},
        "M SDK checklist.sdk",
    )
    package_id = _safe_id(sdk.get("package"), "M SDK checklist.sdk.package")
    catalog = _catalog()
    known = catalog.get(package_id)
    archive_value = sdk.get("archive")

    if archive_value is None:
        if known is None:
            raise _package_required(package_id, archive=None, sdk_release=None)
        archive = Path(known["archive"])
        if not archive.is_file():
            raise _package_required(
                package_id,
                archive=archive,
                sdk_release=known["sdk_release"],
            )
        actual_hash = hash_file(archive)
        if actual_hash != known["sha256"]:
            raise ToolError(
                f"M SDK package hash mismatch for registered package {package_id}: expected "
                f"{known['sha256']}, got {actual_hash}; place the user-provided package "
                "in the current case and set sdk.archive plus sdk.trust_reason"
            )
        if sdk.get("sdk_release") is not None and str(sdk["sdk_release"]) != known["sdk_release"]:
            raise ToolError("M SDK checklist.sdk.sdk_release conflicts with the known package")
        if sdk.get("trust_reason") is not None:
            raise ToolError("M SDK checklist.sdk.trust_reason is only for a case-provided package")
        return {**known, "assurance": "catalog_verified"}

    archive = _case_path(archive_value, "M SDK checklist.sdk.archive", case_root)
    release = (
        _scalar(sdk.get("sdk_release"), "M SDK checklist.sdk.sdk_release")
        if sdk.get("sdk_release") is not None
        else known["sdk_release"] if known is not None else None
    )
    if not archive.is_file():
        raise _package_required(package_id, archive=archive, sdk_release=release)
    if release is None:
        raise ToolError(
            "M SDK checklist.sdk.sdk_release is required for an unregistered user-provided package"
        )
    trust_reason = (
        _scalar(sdk.get("trust_reason"), "M SDK checklist.sdk.trust_reason")
        if sdk.get("trust_reason") is not None
        else None
    )
    actual_hash = hash_file(archive)
    catalog_match = known is not None and actual_hash == known["sha256"]
    if known is not None and release != known["sdk_release"]:
        raise ToolError("M SDK checklist.sdk.sdk_release conflicts with the known package")
    if not catalog_match and trust_reason is None:
        raise ToolError(
            "M SDK checklist.sdk.trust_reason is required when the case-provided package "
            "does not match a known catalog hash"
        )
    return {
        "id": package_id,
        "archive": str(archive),
        "sha256": actual_hash,
        "sdk_release": release,
        "soc": known["soc"] if known is not None else None,
        "boards": known["boards"] if catalog_match else {},
        "compiler_version_contains": (
            known["compiler_version_contains"] if known is not None else None
        ),
        "assurance": "catalog_verified" if catalog_match else "user_attested",
        "trust_reason": trust_reason,
    }


def select_backend(sdk_release: str) -> str:
    if re.fullmatch(r"2[.][0-9]+[.][0-9]+", sdk_release):
        return "legacy"
    match = re.fullmatch(r"([0-9]{2})[.]([0-9]{2})[.][0-9]+", sdk_release)
    if not match:
        raise ToolError(f"unsupported M SDK release format: {sdk_release}")
    yymm = int(match.group(1)) * 100 + int(match.group(2))
    if yymm <= 2509:
        return "legacy"
    if yymm >= 2512:
        return "west"
    raise ToolError(
        f"M SDK release {sdk_release} is in the unsupported 2510/2511 transition gap"
    )


class _Archive:
    def __init__(self, path: Path):
        self.path = path
        self._zip = zipfile.is_zipfile(path)
        try:
            if self._zip:
                with zipfile.ZipFile(path) as archive:
                    raw_names = archive.namelist()
            else:
                with tarfile.open(path, "r:*") as archive:
                    raw_names = archive.getnames()
        except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
            raise ToolError(f"cannot inspect M SDK archive {path}: {exc}") from exc
        self.names: set[str] = set()
        for raw in raw_names:
            candidate = PurePosixPath(raw)
            if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
                raise ToolError(f"M SDK archive contains unsafe member: {raw}")
            self.names.add(candidate.as_posix().rstrip("/"))

    def exists(self, member: str) -> bool:
        return _safe_relative(member, "archive member") in self.names

    def read_text(self, member: str) -> str:
        safe_member = _safe_relative(member, "archive member")
        if safe_member not in self.names:
            raise ToolError(f"M SDK archive member is unavailable: {safe_member}")
        try:
            if self._zip:
                with zipfile.ZipFile(self.path) as archive:
                    payload = archive.read(safe_member)
            else:
                with tarfile.open(self.path, "r:*") as archive:
                    entry = archive.getmember(safe_member)
                    if not entry.isfile():
                        raise ToolError(f"M SDK archive member is not a file: {safe_member}")
                    stream = archive.extractfile(entry)
                    if stream is None:
                        raise ToolError(f"cannot read M SDK archive member: {safe_member}")
                    payload = stream.read()
        except (OSError, KeyError, tarfile.TarError, zipfile.BadZipFile) as exc:
            raise ToolError(f"cannot read M SDK archive member {safe_member}: {exc}") from exc
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError(f"M SDK archive member is not UTF-8 text: {safe_member}") from exc


def _validate_backend_layout(archive: _Archive, backend: str) -> None:
    west_markers = {
        ".west/config",
        "manifests/west.yml",
        "mcuxsdk/scripts/west_commands/build.py",
        "mcuxsdk/scripts/west_commands.yml",
    }
    if backend == "west":
        missing = sorted(marker for marker in west_markers if not archive.exists(marker))
        if missing:
            raise ToolError(
                "M SDK release selects West backend but package layout is missing: "
                + ", ".join(missing)
            )
    elif any(archive.exists(marker) for marker in west_markers):
        raise ToolError("M SDK release selects legacy backend but package has a West layout")


def _legacy_layout(
    archive: _Archive,
    board: str,
    core: str,
    application: str,
    configuration: str,
) -> dict[str, str]:
    roots = [
        f"boards/{board}/{application}/{core}/armgcc",
        f"boards/{board}/{application}/armgcc",
    ]
    root = next(
        (candidate for candidate in roots if archive.exists(f"{candidate}/build_{configuration}.sh")),
        None,
    )
    if root is None:
        raise ToolError(
            "legacy M SDK build script is unavailable: "
            + " or ".join(f"{candidate}/build_{configuration}.sh" for candidate in roots)
        )
    cmake_member = f"{root}/CMakeLists.txt"
    cmake_text = archive.read_text(cmake_member)
    elf_match = re.search(
        r"set\s*\(\s*MCUX_SDK_PROJECT_NAME\s+([^\s\)]+[.]elf)\s*\)",
        cmake_text,
        re.IGNORECASE,
    )
    bin_matches = re.findall(r"[/}]([A-Za-z0-9_.+-]+[.]bin)\b", cmake_text)
    if elf_match is None or not bin_matches:
        raise ToolError(f"cannot resolve ELF/BIN outputs from {cmake_member}")
    return {
        "project_root": root,
        "script": f"{root}/build_{configuration}.sh",
        "elf_relative": f"{root}/{configuration}/{elf_match.group(1)}",
        "bin_relative": f"{root}/{configuration}/{bin_matches[-1]}",
    }


def _modern_layout(
    archive: _Archive,
    board: str,
    core: str,
    application: str,
    configuration: str,
) -> dict[str, str]:
    example_member = f"mcuxsdk/examples/{application}/example.yml"
    example = mapping_value(
        yaml.safe_load(archive.read_text(example_member)),
        f"M SDK {example_member}",
    )
    board_selector = f"{board}@{core}"
    supported = False
    for value in example.values():
        if not isinstance(value, dict):
            continue
        boards = value.get("boards")
        if not isinstance(boards, dict):
            continue
        variants = boards.get(board_selector)
        if isinstance(variants, list) and f"+armgcc@{configuration}" in variants:
            supported = True
            break
    if not supported:
        raise ToolError(
            f"West M SDK example does not support {board_selector} armgcc/{configuration}: "
            f"{example_member}"
        )
    cmake_member = f"mcuxsdk/examples/{application}/CMakeLists.txt"
    cmake_text = archive.read_text(cmake_member)
    project_match = re.search(r"project\s*\(\s*([A-Za-z0-9_.+-]+)", cmake_text, re.IGNORECASE)
    if project_match is None:
        raise ToolError(f"cannot resolve West project output name from {cmake_member}")
    base_project_name = project_match.group(1)
    return {
        "source_relative": f"mcuxsdk/examples/{application}",
        # MCUX appends core_id_suffix_name (for example _cm7 or _cm7_core1)
        # to the CMake project name for board@core builds.
        "project_name": f"{base_project_name}_{core}",
        "board_selector": board_selector,
        "build_board": board,
        "core_id": core,
    }


def _normalize_artifacts(
    raw_value: Any,
    label: str,
    *,
    provenance_kind: str,
    archive: _Archive,
    case_root: Path,
) -> dict[str, dict[str, str]]:
    raw = mapping_value(raw_value, label)
    if not raw or not set(raw).issubset({"elf", "bin"}):
        raise ToolError(f"{label} must contain one or both of elf/bin")
    result: dict[str, dict[str, str]] = {}
    for artifact_format, value in raw.items():
        item_label = f"{label}.{artifact_format}"
        item = mapping_value(value, item_label)
        if provenance_kind == "vendor_package":
            reject_unknown_keys(item, {"member"}, item_label)
            member = _safe_relative(item.get("member"), f"{item_label}.member")
            if not archive.exists(member):
                raise ToolError(f"vendor package member is unavailable: {member}")
            if not member.casefold().endswith(f".{artifact_format}"):
                raise ToolError(f"{item_label}.member extension does not match {artifact_format}")
            result[artifact_format] = {"member": member}
        else:
            reject_unknown_keys(item, {"path", "sha256"}, item_label)
            path = _case_path(item.get("path"), f"{item_label}.path", case_root)
            if not path.is_file():
                raise ToolError(f"user supplied artifact is unavailable: {path}")
            expected = normalize_hash(_scalar(item.get("sha256"), f"{item_label}.sha256"))
            actual = hash_file(path)
            if actual != expected:
                raise ToolError(
                    f"user supplied artifact hash mismatch for {path}: expected {expected}, got {actual}"
                )
            result[artifact_format] = {"path": str(path), "sha256": expected}
    return result


def normalize_m_sdk_checklist(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve(strict=False)
    raw = mapping_value(load_yaml(path, "M SDK compile checklist"), "M SDK compile checklist")
    reject_unknown_keys(
        raw,
        {"schema_version", "kind", "target", "case_root", "sdk", "jobs", "intent"},
        "M SDK checklist",
    )
    if (
        raw.get("schema_version") != 1
        or raw.get("kind") != CHECKLIST_KIND
        or raw.get("target") != TARGET
    ):
        raise ToolError("M SDK compile checklist identity is invalid")
    case_root = Path(_scalar(raw.get("case_root"), "M SDK checklist.case_root")).expanduser().resolve(strict=False)
    if not case_root.is_dir():
        raise ToolError(f"M SDK checklist.case_root is not an existing directory: {case_root}")
    expected_path = case_root / "records" / "compile" / TARGET / "compile.yaml"
    if path != expected_path.resolve(strict=False):
        raise ToolError(f"M SDK checklist must be stored at {expected_path}")

    sdk = mapping_value(raw.get("sdk"), "M SDK checklist.sdk")
    package = _resolve_package(sdk, case_root)
    package_id = package["id"]
    backend = select_backend(package["sdk_release"])
    archive = _Archive(Path(package["archive"]))
    _validate_backend_layout(archive, backend)

    compiler = Path(_scalar(sdk.get("compiler"), "M SDK checklist.sdk.compiler")).expanduser().resolve(strict=False)
    if not compiler.is_file() or not compiler.name.endswith("arm-none-eabi-gcc"):
        raise ToolError(f"M SDK compiler must be an arm-none-eabi-gcc executable: {compiler}")
    compiler_output = run_command([str(compiler), "--version"], cwd=case_root).stdout.decode(
        "utf-8", errors="replace"
    )
    constraint = package.get("compiler_version_contains")
    if constraint and constraint not in compiler_output:
        raise ToolError(f"{package_id} requires GCC ARM Embedded {constraint}")

    jobs_raw = mapping_value(raw.get("jobs"), "M SDK checklist.jobs")
    if not jobs_raw:
        raise ToolError("M SDK checklist.jobs must not be empty")
    jobs: dict[str, dict[str, Any]] = {}
    for job_id, value in jobs_raw.items():
        job = _safe_id(job_id, "M SDK job id")
        label = f"M SDK checklist.jobs.{job}"
        item = mapping_value(value, label)
        reject_unknown_keys(
            item,
            {
                "mode",
                "soc",
                "board",
                "core",
                "core_role",
                "application",
                "build_configuration",
                "provenance",
            },
            label,
        )
        mode = _scalar(item.get("mode"), f"{label}.mode")
        if mode not in {"source_build", "prebuilt_import"}:
            raise ToolError(f"{label}.mode must be source_build or prebuilt_import")
        soc = _safe_id(item.get("soc"), f"{label}.soc")
        board = _safe_id(item.get("board"), f"{label}.board")
        core = _safe_id(item.get("core"), f"{label}.core")
        core_role = _safe_id(item.get("core_role"), f"{label}.core_role")
        application = _safe_relative(item.get("application"), f"{label}.application")
        configuration = _safe_id(
            item.get("build_configuration"), f"{label}.build_configuration"
        )
        if package.get("soc") is not None and soc.casefold() != package["soc"].casefold():
            raise ToolError(f"{label}.soc does not match registered package SoC {package['soc']}")
        if package["boards"]:
            if board not in package["boards"]:
                raise ToolError(f"{label}.board is not registered for {package_id}: {board}")
            expected_role = package["boards"][board].get(core)
            if expected_role is None:
                raise ToolError(f"{label}.core is not registered for {package_id}/{board}: {core}")
            if expected_role != core_role:
                raise ToolError(
                    f"{label}.core_role mismatch: {core} is registered as {expected_role}"
                )
        normalized: dict[str, Any] = {
            "id": job,
            "mode": mode,
            "soc": soc,
            "board": board,
            "core": core,
            "core_role": core_role,
            "application": application,
            "build_configuration": configuration,
        }
        if mode == "source_build":
            if item.get("provenance") is not None:
                raise ToolError(f"{label}.provenance is only valid for prebuilt_import")
            normalized["layout"] = (
                _legacy_layout(archive, board, core, application, configuration)
                if backend == "legacy"
                else _modern_layout(archive, board, core, application, configuration)
            )
        else:
            provenance = mapping_value(item.get("provenance"), f"{label}.provenance")
            reject_unknown_keys(
                provenance, {"kind", "trust_reason", "artifacts"}, f"{label}.provenance"
            )
            provenance_kind = _scalar(provenance.get("kind"), f"{label}.provenance.kind")
            if provenance_kind not in {"vendor_package", "user_supplied"}:
                raise ToolError(
                    f"{label}.provenance.kind must be vendor_package or user_supplied"
                )
            trust_reason = None
            if provenance_kind == "vendor_package":
                if provenance.get("trust_reason") is not None:
                    raise ToolError(f"{label}.provenance.trust_reason is only for user_supplied")
            else:
                trust_reason = _scalar(
                    provenance.get("trust_reason"), f"{label}.provenance.trust_reason"
                )
            normalized["provenance"] = {
                "kind": provenance_kind,
                "trust_reason": trust_reason,
                "artifacts": _normalize_artifacts(
                    provenance.get("artifacts"),
                    f"{label}.provenance.artifacts",
                    provenance_kind=provenance_kind,
                    archive=archive,
                    case_root=case_root,
                ),
            }
        jobs[job] = normalized

    intent = mapping_value(raw.get("intent"), "M SDK checklist.intent")
    reject_unknown_keys(intent, {"scope", "reason"}, "M SDK checklist.intent")
    scope_raw = intent.get("scope")
    if not isinstance(scope_raw, list) or not all(isinstance(value, str) for value in scope_raw):
        raise ToolError("M SDK checklist.intent.scope must be a job id list")
    scope = [_safe_id(value, "M SDK checklist.intent.scope entry") for value in scope_raw]
    if len(scope) != len(set(scope)):
        raise ToolError("M SDK checklist.intent.scope contains duplicates")
    unknown_scope = sorted(set(scope) - set(jobs))
    if unknown_scope:
        raise ToolError("M SDK checklist.intent.scope has unknown jobs: " + ", ".join(unknown_scope))
    reason = _scalar(intent.get("reason"), "M SDK checklist.intent.reason")
    return {
        "checklist_kind": CHECKLIST_KIND,
        "path": str(path),
        "hash": hash_data(raw),
        "raw": raw,
        "case_root": str(case_root),
        "case": case_root.name,
        "target": TARGET,
        "package": package,
        "backend": backend,
        "compiler": str(compiler),
        "compiler_root": str(compiler.parent.parent),
        "jobs": jobs,
        "intent": {"scope": scope, "reason": reason},
    }


def _write_manifest(path: Path, raw: dict[str, Any], checklist: dict[str, Any]) -> None:
    if path.exists():
        existing = mapping_value(load_yaml(path, "generated M SDK manifest"), "generated M SDK manifest")
        marker = existing.get("project_checklist")
        if not isinstance(marker, dict) or marker.get("path") != checklist["path"]:
            raise ToolError(f"refusing to overwrite a manifest not owned by the M SDK checklist: {path}")
    atomic_write_yaml(path, raw)


def _job_outputs(case_root: Path, job: str, formats: list[str]) -> dict[str, Path]:
    return {
        artifact_format: case_root / "artifacts" / TARGET / job / f"{job}.{artifact_format}"
        for artifact_format in formats
    }


def materialize_m_sdk_manifest(
    checklist: dict[str, Any], *, stack: set[str] | None = None
) -> dict[str, Any]:
    case_root = Path(checklist["case_root"])
    source_root = case_root / "sources" / TARGET / checklist["package"]["id"]
    uses_package = any(
        job["mode"] == "source_build"
        or job.get("provenance", {}).get("kind") == "vendor_package"
        for job in checklist["jobs"].values()
    )
    sources = (
        {
            "sdk": {
                "kind": "release_archive",
                "archive_path": checklist["package"]["archive"],
                "case_path": str(source_root),
            }
        }
        if uses_package
        else {}
    )
    components: dict[str, dict[str, Any]] = {}
    exports: dict[str, dict[str, Any]] = {}
    for job_id, job in checklist["jobs"].items():
        identity = {
            "soc": job["soc"],
            "board": job["board"],
            "core": job["core"],
            "core_role": job["core_role"],
            "application": job["application"],
            "build_configuration": job["build_configuration"],
            "sdk_release": checklist["package"]["sdk_release"],
            "origin": job["mode"],
        }
        if job["mode"] == "source_build":
            formats = ["elf", "bin"]
            origin = {
                "mode": "source_build",
                "assurance": "locally_built",
                "details": {
                    "package": checklist["package"]["id"],
                    "package_sha256": checklist["package"]["sha256"],
                    "package_assurance": checklist["package"]["assurance"],
                    "backend": checklist["backend"],
                },
            }
            watched_inputs: list[str] = []
            import_contract: list[dict[str, str]] = []
            tools = [
                {"name": "compiler", "executable": checklist["compiler"], "version_args": ["--version"]}
            ]
            if checklist["backend"] == "west":
                west = shutil.which("west")
                if west is None:
                    raise ToolError("West backend requires a west executable in PATH")
                tools.append({"name": "west", "executable": west, "version_args": ["--version"]})
        else:
            provenance = job["provenance"]
            formats = list(provenance["artifacts"])
            assurance = (
                checklist["package"]["assurance"]
                if provenance["kind"] == "vendor_package"
                else "user_attested"
            )
            details = {
                "package": checklist["package"]["id"],
                "package_sha256": checklist["package"]["sha256"],
                "package_assurance": checklist["package"]["assurance"],
                "provenance_kind": provenance["kind"],
            }
            if checklist["package"].get("trust_reason"):
                details["package_trust_reason"] = checklist["package"]["trust_reason"]
            if provenance.get("trust_reason"):
                details["trust_reason"] = provenance["trust_reason"]
            origin = {"mode": "prebuilt_import", "assurance": assurance, "details": details}
            watched_inputs = []
            import_contract = []
            outputs = _job_outputs(case_root, job_id, formats)
            for artifact_format, artifact in provenance["artifacts"].items():
                source = (
                    source_root / artifact["member"]
                    if provenance["kind"] == "vendor_package"
                    else Path(artifact["path"])
                )
                watched_inputs.append(str(source))
                import_contract.append(
                    {"source": str(source), "output": str(outputs[artifact_format])}
                )
            tools = [
                {"name": "install", "executable": "/usr/bin/install", "version_args": ["--version"]}
            ]
        output_paths = _job_outputs(case_root, job_id, formats)
        components[job_id] = {
            "operation": "import" if job["mode"] == "prebuilt_import" else "build",
            "origin": origin,
            **({"import_contract": import_contract} if import_contract else {}),
            "sources": ["sdk"] if uses_package and (
                job["mode"] == "source_build"
                or job.get("provenance", {}).get("kind") == "vendor_package"
            ) else [],
            "configuration": {"values": identity, "files": []},
            "tools": tools,
            "watched_inputs": watched_inputs,
            "outputs": [str(output_paths[artifact_format]) for artifact_format in formats],
            "depends_on": [],
        }
        for artifact_format in formats:
            exports[f"{job_id}.{artifact_format}"] = {
                "component": job_id,
                "type": f"nxp.mcore.{artifact_format}",
                "path": str(output_paths[artifact_format]),
                "identity": identity,
            }
    manifest_path = case_root / "records" / "compile" / TARGET / "manifest.yaml"
    raw = {
        "schema_version": 2,
        "case": checklist["case"],
        "case_root": str(case_root),
        "target": TARGET,
        "project_checklist": {"path": checklist["path"], "hash": checklist["hash"]},
        "parameters": {},
        "sources": sources,
        "components": components,
        "exports": exports,
    }
    _write_manifest(manifest_path, raw, checklist)
    return load_manifest(manifest_path)


def _install_command(source: Path, destination: Path) -> str:
    return "/usr/bin/install -D -m 0644 " + shlex.quote(str(source)) + " " + shlex.quote(str(destination))


def _job_steps(checklist: dict[str, Any], manifest: dict[str, Any], job_id: str) -> list[dict[str, Any]]:
    job = checklist["jobs"][job_id]
    case_root = Path(checklist["case_root"])
    source_root = case_root / "sources" / TARGET / checklist["package"]["id"]
    component = manifest["components"][job_id]
    if job["mode"] == "prebuilt_import":
        return [
            {
                "name": f"import-{Path(contract['output']).suffix.lstrip('.')}",
                "cwd": str(case_root),
                "env": {},
                "command": _install_command(Path(contract["source"]), Path(contract["output"])),
            }
            for contract in component["import_contract"]
        ]

    outputs = {Path(path).suffix.lstrip("."): Path(path) for path in component["outputs"]}
    if checklist["backend"] == "legacy":
        layout = job["layout"]
        script = source_root / layout["script"]
        command = "cd " + shlex.quote(str(script.parent)) + " && /bin/sh " + shlex.quote(f"./{script.name}")
        produced = {
            "elf": source_root / layout["elf_relative"],
            "bin": source_root / layout["bin_relative"],
        }
    else:
        west = next(tool["executable"] for tool in component["toolchains"] if tool["name"] == "west")
        layout = job["layout"]
        build_dir = case_root / "build" / TARGET / job_id
        argv = [
            west,
            "build",
            "-b",
            layout["build_board"],
            "-d",
            str(build_dir),
            "-p",
            "always",
            "--toolchain",
            "armgcc",
            "--config",
            job["build_configuration"],
            str(source_root / layout["source_relative"]),
            f"-Dcore_id={layout['core_id']}",
        ]
        command = "cd " + shlex.quote(str(source_root)) + " && " + shlex.join(argv)
        produced = {
            "elf": build_dir / f"{layout['project_name']}.elf",
            "bin": build_dir / f"{layout['project_name']}.bin",
        }
    steps = [
        {
            "name": f"build-{job_id}",
            "cwd": str(case_root),
            "env": {"ARMGCC_DIR": checklist["compiler_root"]},
            "command": command,
        }
    ]
    for artifact_format in ("elf", "bin"):
        steps.append(
            {
                "name": f"publish-{job_id}-{artifact_format}",
                "cwd": str(case_root),
                "env": {},
                "command": _install_command(produced[artifact_format], outputs[artifact_format]),
            }
        )
    return steps


def _request_for(
    checklist: dict[str, Any], manifest: dict[str, Any], assessment_hash: str
) -> dict[str, Any]:
    scope = checklist["intent"]["scope"]
    request_path = Path(checklist["path"]).parent / REQUEST_NAME
    raw = {
        "schema_version": 2,
        "case": checklist["case"],
        "assessment": {"manifest": manifest["path"], "hash": assessment_hash},
        "decision": {
            "scope": scope,
            "reason": checklist["intent"]["reason"],
            "destructive": {},
        },
        "compile": {
            "target": TARGET,
            "units": [
                {
                    "component": job_id,
                    "action": "import" if checklist["jobs"][job_id]["mode"] == "prebuilt_import" else "rebuild",
                    "steps": _job_steps(checklist, manifest, job_id),
                }
                for job_id in manifest["component_order"]
                if job_id in scope
            ],
        },
    }
    atomic_write_yaml(request_path, raw)
    return load_request(request_path, allow_project_checklist_request=True)


def _unscoped_are_reusable(checklist: dict[str, Any], assessment: dict[str, Any]) -> None:
    scope = set(checklist["intent"]["scope"])
    changed = [
        job_id
        for job_id in checklist["jobs"]
        if job_id not in scope and assessment["observations"][job_id]["action"] != "reuse"
    ]
    if changed:
        raise ToolError(
            "M SDK jobs outside intent.scope do not have reusable successful state: "
            + ", ".join(changed)
        )


def _prepared_path(checklist: dict[str, Any]) -> Path:
    return Path(checklist["path"]).parent / PREPARED_NAME


def _render_plan(
    checklist: dict[str, Any], manifest: dict[str, Any], assessment: dict[str, Any]
) -> str:
    lines = [
        "[M SDK 多任务编译计划]",
        "",
        f"Case：{checklist['case']}",
        f"SDK 包：{checklist['package']['id']}",
        f"SDK 版本：{checklist['package']['sdk_release']}",
        f"受控 backend：{checklist['backend']}",
        f"SDK 包证据：{checklist['package']['assurance']}",
        f"包 SHA-256：{checklist['package']['sha256']}",
        f"编译器：{checklist['compiler']}",
        "",
        "任务及产物：",
    ]
    for job_id, job in checklist["jobs"].items():
        origin = (
            job.get("provenance", {}).get("kind", "locally_built")
            if job["mode"] == "prebuilt_import"
            else "locally_built"
        )
        exports = ", ".join(
            artifact_id
            for artifact_id, export in manifest["exports"].items()
            if export["component"] == job_id
        )
        lines.append(
            f"- {job_id}：{job['mode']} / {job['soc']} / {job['board']} / "
            f"{job['core']}({job['core_role']}) / {origin} -> {exports}"
        )
    lines.extend(
        [
            "",
            "本轮直接范围：" + (", ".join(checklist["intent"]["scope"]) or "无（全部复用）"),
            f"理由：{checklist['intent']['reason']}",
            "软件状态：" + (
                "PENDING_SOURCE_ACQUISITION"
                if assessment["status"] == "ACQUIRE_REQUIRED"
                else assessment["state_summary"]
            ),
        ]
    )
    if assessment["status"] == "ACQUIRE_REQUIRED":
        lines.extend(["", render_acquisition(manifest, assessment["source"])])
    if checklist["intent"]["scope"]:
        request = _request_for(
            checklist,
            manifest,
            assessment.get("assessment_hash") or "sha256:" + "0" * 64,
        )
        lines.extend(["", "受控执行步骤："])
        for unit in request["compile"]["units"]:
            lines.append(f"- {unit['component']} / {unit['action'].upper()}")
            for step in unit["steps"]:
                lines.append(f"  - 工作目录：{step['cwd']}")
                lines.append(
                    "    环境变量："
                    + (" ".join(f"{key}={value}" for key, value in step["env"].items()) or "无")
                )
                lines.append(f"    $ {step['command']}")
    lines.extend(["", "Decision：READY_FOR_RUN"])
    return "\n".join(lines)


def _prepare_normalized(checklist: dict[str, Any]) -> int:
    manifest = materialize_m_sdk_manifest(checklist)
    assessment = assess(manifest)
    scope = set(checklist["intent"]["scope"])
    if assessment["status"] == "ACQUIRE_REQUIRED":
        package_jobs = {
            job_id
            for job_id, job in checklist["jobs"].items()
            if job["mode"] == "source_build"
            or job.get("provenance", {}).get("kind") == "vendor_package"
        }
        missing_scope = sorted(package_jobs - scope)
        if missing_scope:
            raise ToolError(
                "first package acquisition requires every package-backed job in intent.scope: "
                + ", ".join(missing_scope)
            )
    else:
        _unscoped_are_reusable(checklist, assessment)
    if not scope and assessment["status"] != "READY":
        raise ToolError("M SDK reuse requires acquired source and matched state")
    prepared = {
        "schema_version": 1,
        "generated_by": "compile-tool M SDK checklist prepare",
        "checklist": checklist["path"],
        "checklist_hash": checklist["hash"],
        "manifest_hash": manifest["hash"],
        "package_sha256": checklist["package"]["sha256"],
        "acquisition_plan_hash": (
            assessment["source"]["plan_hash"]
            if assessment["status"] == "ACQUIRE_REQUIRED"
            else None
        ),
        "assessment_hash": assessment.get("assessment_hash"),
    }
    atomic_write_yaml(_prepared_path(checklist), prepared)
    print(_render_plan(checklist, manifest, assessment))
    return 0


def prepare_m_sdk_checklist(path: Path) -> int:
    checklist = normalize_m_sdk_checklist(path)
    with case_lock(Path(checklist["case_root"])):
        return _prepare_normalized(checklist)


def _run_normalized(checklist: dict[str, Any]) -> int:
    prepared = mapping_value(
        load_yaml(_prepared_path(checklist), "prepared M SDK checklist record"),
        "prepared M SDK checklist record",
    )
    manifest = materialize_m_sdk_manifest(checklist)
    if (
        prepared.get("checklist") != checklist["path"]
        or prepared.get("checklist_hash") != checklist["hash"]
        or prepared.get("manifest_hash") != manifest["hash"]
        or prepared.get("package_sha256") != checklist["package"]["sha256"]
    ):
        raise ToolError("M SDK checklist or package changed after prepare; run prepare again")
    assessment = assess(manifest)
    if assessment["status"] == "ACQUIRE_REQUIRED":
        if prepared.get("acquisition_plan_hash") != assessment["source"]["plan_hash"]:
            raise ToolError("M SDK source acquisition plan changed after prepare")
        result = execute_acquisition(manifest, assessment["source"]["plan_hash"])
        if result != 0:
            return result
        assessment = assess(manifest)
    elif prepared.get("assessment_hash") != assessment.get("assessment_hash"):
        raise ToolError("M SDK software state changed after prepare; run prepare again")
    if assessment["status"] != "READY":
        raise ToolError("M SDK source is not ready after acquisition")
    _unscoped_are_reusable(checklist, assessment)
    if not checklist["intent"]["scope"]:
        if assessment["state_summary"] != "MATCHED":
            raise ToolError("M SDK checklist requests reuse but state has changes")
        state = load_state(manifest)
        write_state(manifest, state)
        print("compile-tool: M SDK checklist state matched; reused producer outputs")
        return 0
    request = _request_for(checklist, manifest, assessment["assessment_hash"])
    print(render_report(request, assessment), flush=True)
    print("\nExecution：STARTING", flush=True)
    return execute_v2(request, assessment)


def run_m_sdk_checklist(path: Path) -> int:
    checklist = normalize_m_sdk_checklist(path)
    with case_lock(Path(checklist["case_root"])):
        return _run_normalized(checklist)
