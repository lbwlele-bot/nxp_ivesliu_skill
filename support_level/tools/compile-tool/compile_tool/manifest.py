from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    REF_RE,
    ToolError,
    hash_data,
    load_yaml,
    mapping_value,
    reject_unknown_keys,
    require_within,
    resolve_absolute,
    text_value,
)


IDENTITY_FIELDS = (
    "soc",
    "silicon_revision",
    "chip_package",
    "board",
    "ddr",
    "software_release",
)
UNKNOWN_VALUES = {"unknown", "tbd", "todo", "?"}
NOT_APPLICABLE_VALUES = {"n/a", "na", "not applicable", "not_applicable"}
TOOL_DIR = Path(__file__).resolve().parents[1]
SUPPORT_LEVEL = TOOL_DIR.parent.parent
PROFILE_PATHS = {
    "flashbin": SUPPORT_LEVEL / "compile_targets" / "flashbin" / "DEPENDENCIES.yaml"
}


def normalize_identity(data: Any, label: str = "identity") -> dict[str, str]:
    raw = mapping_value(data, label)
    reject_unknown_keys(raw, set(IDENTITY_FIELDS), label)
    result: dict[str, str] = {}
    for field in IDENTITY_FIELDS:
        value = text_value(raw.get(field), f"{label}.{field}")
        if " ".join(value.lower().split()) in UNKNOWN_VALUES:
            raise ToolError(f"{label}.{field} is unresolved: {value!r}")
        result[field] = value
    return result


def load_profile(target: str) -> dict[str, Any]:
    try:
        path = PROFILE_PATHS[target]
    except KeyError as exc:
        raise ToolError(f"no state profile is available for target {target!r}") from exc
    raw = mapping_value(load_yaml(path, "dependency profile"), "dependency profile")
    reject_unknown_keys(raw, {"schema_version", "target", "components"}, "profile")
    if raw.get("schema_version") != 1 or raw.get("target") != target:
        raise ToolError(f"invalid dependency profile identity: {path}")
    components_raw = mapping_value(raw.get("components"), "profile.components")
    components: dict[str, dict[str, Any]] = {}
    allowed_kinds = {"build", "fixed_input", "package"}
    for component_id, value in components_raw.items():
        if not isinstance(component_id, str) or not component_id:
            raise ToolError("profile component ids must be non-empty strings")
        item = mapping_value(value, f"profile.components.{component_id}")
        reject_unknown_keys(item, {"kind", "depends_on"}, f"profile.components.{component_id}")
        kind = text_value(item.get("kind"), f"profile.components.{component_id}.kind")
        if kind not in allowed_kinds:
            raise ToolError(f"unsupported component kind for {component_id}: {kind}")
        dependencies = item.get("depends_on") or []
        if not isinstance(dependencies, list) or not all(
            isinstance(entry, str) and entry for entry in dependencies
        ):
            raise ToolError(f"profile.components.{component_id}.depends_on must be a string list")
        components[component_id] = {"kind": kind, "depends_on": dependencies}

    for component_id, item in components.items():
        missing = sorted(set(item["depends_on"]) - set(components))
        if missing:
            raise ToolError(
                f"profile component {component_id} has unknown dependencies: {', '.join(missing)}"
            )
    _topological_order(components)
    normalized = {
        "schema_version": 1,
        "target": target,
        "path": str(path.resolve()),
        "components": components,
    }
    normalized["hash"] = hash_data(
        {key: value for key, value in normalized.items() if key not in {"path", "hash"}}
    )
    return normalized


def _topological_order(components: dict[str, dict[str, Any]]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    result: list[str] = []

    def visit(component_id: str) -> None:
        if component_id in visiting:
            raise ToolError(f"dependency profile contains a cycle at {component_id}")
        if component_id in visited:
            return
        visiting.add(component_id)
        for dependency in components[component_id]["depends_on"]:
            visit(dependency)
        visiting.remove(component_id)
        visited.add(component_id)
        result.append(component_id)

    for component_id in components:
        visit(component_id)
    return result


def topological_order(profile: dict[str, Any], enabled: set[str]) -> list[str]:
    return [
        component_id
        for component_id in _topological_order(profile["components"])
        if component_id in enabled
    ]


def _normalize_paths(values: Any, label: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ToolError(f"{label} must be a non-empty path list")
    result: list[str] = []
    for index, value in enumerate(values, start=1):
        result.append(str(resolve_absolute(value, f"{label}[{index}]")))
    if len(result) != len(set(result)):
        raise ToolError(f"{label} contains duplicate paths")
    return result


def _normalize_source(
    raw_value: Any, label: str, case_root: Path
) -> dict[str, Any]:
    raw = mapping_value(raw_value, label)
    kind = text_value(raw.get("kind"), f"{label}.kind")
    if kind == "managed_git":
        reject_unknown_keys(
            raw,
            {
                "kind",
                "canonical_path",
                "case_path",
                "ref_kind",
                "ref",
                "remote",
                "remote_url",
                "update",
            },
            label,
        )
        canonical = resolve_absolute(raw.get("canonical_path"), f"{label}.canonical_path")
        case_path = resolve_absolute(raw.get("case_path"), f"{label}.case_path")
        require_within(case_path, case_root, f"{label}.case_path")
        if not canonical.is_dir():
            raise ToolError(f"{label}.canonical_path is not a directory: {canonical}")
        if "support_level" not in canonical.parts or "code_assets" not in canonical.parts:
            raise ToolError(f"{label}.canonical_path is not under support_level/code_assets")
        ref_kind = text_value(raw.get("ref_kind"), f"{label}.ref_kind")
        if ref_kind not in {"branch", "tag", "commit"}:
            raise ToolError(f"{label}.ref_kind must be branch, tag, or commit")
        ref = text_value(raw.get("ref"), f"{label}.ref")
        if ref.startswith("-") or not REF_RE.fullmatch(ref):
            raise ToolError(f"{label}.ref contains unsafe characters: {ref!r}")
        remote = text_value(raw.get("remote") or "origin", f"{label}.remote")
        if remote.startswith("-") or not REF_RE.fullmatch(remote):
            raise ToolError(f"{label}.remote contains unsafe characters: {remote!r}")
        update = text_value(raw.get("update") or "if_missing", f"{label}.update")
        if update not in {"if_missing", "pull_ff_only"}:
            raise ToolError(f"{label}.update must be if_missing or pull_ff_only")
        if update == "pull_ff_only" and ref_kind != "branch":
            raise ToolError(f"{label}.update=pull_ff_only requires ref_kind=branch")
        return {
            "kind": kind,
            "canonical_path": str(canonical),
            "case_path": str(case_path),
            "ref_kind": ref_kind,
            "ref": ref,
            "remote": remote,
            "remote_url": text_value(raw.get("remote_url"), f"{label}.remote_url"),
            "update": update,
        }
    if kind == "local_files":
        reject_unknown_keys(raw, {"kind", "paths"}, label)
        return {"kind": kind, "paths": _normalize_paths(raw.get("paths"), f"{label}.paths")}
    raise ToolError(f"{label}.kind must be managed_git or local_files")


def _normalize_configuration(
    raw_value: Any, label: str
) -> dict[str, Any]:
    raw = mapping_value(raw_value or {}, label)
    reject_unknown_keys(raw, {"values", "files"}, label)
    values = mapping_value(raw.get("values") or {}, f"{label}.values")
    normalized_values: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not key:
            raise ToolError(f"{label}.values keys must be non-empty strings")
        if not isinstance(value, (str, int, float, bool)):
            raise ToolError(f"{label}.values.{key} must be a scalar")
        normalized_values[key] = str(value)
    files_raw = raw.get("files") or []
    if not isinstance(files_raw, list):
        raise ToolError(f"{label}.files must be a path list")
    files = [
        str(resolve_absolute(value, f"{label}.files[{index}]"))
        for index, value in enumerate(files_raw, start=1)
    ]
    if len(files) != len(set(files)):
        raise ToolError(f"{label}.files contains duplicate paths")
    return {"values": normalized_values, "files": files}


def _normalize_toolchains(raw_value: Any, label: str) -> list[dict[str, Any]]:
    raw = raw_value or []
    if not isinstance(raw, list):
        raise ToolError(f"{label} must be a list")
    result: list[dict[str, Any]] = []
    for index, value in enumerate(raw, start=1):
        item_label = f"{label}[{index}]"
        item = mapping_value(value, item_label)
        reject_unknown_keys(item, {"executable", "version_args"}, item_label)
        executable = resolve_absolute(item.get("executable"), f"{item_label}.executable")
        args = item.get("version_args") or ["--version"]
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ToolError(f"{item_label}.version_args must be a string list")
        result.append({"executable": str(executable), "version_args": args})
    return result


def load_manifest(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve(strict=False)
    raw = mapping_value(load_yaml(path, "compile manifest"), "compile manifest")
    reject_unknown_keys(
        raw,
        {
            "schema_version",
            "case",
            "case_root",
            "target",
            "identity",
            "identity_notes",
            "components",
        },
        "manifest",
    )
    if raw.get("schema_version") != 1:
        raise ToolError("compile manifest schema_version must be 1")
    case = text_value(raw.get("case"), "manifest.case")
    case_root = resolve_absolute(raw.get("case_root"), "manifest.case_root")
    if not case_root.is_dir():
        raise ToolError(f"manifest.case_root is not an existing directory: {case_root}")
    if case_root.name != case:
        raise ToolError("manifest.case must match the case_root directory name")
    expected_path = case_root / "records" / "compile-manifest.yaml"
    if path != expected_path.resolve(strict=False):
        raise ToolError(f"compile manifest must be stored at {expected_path}")
    target = text_value(raw.get("target"), "manifest.target")
    if target != "flashbin":
        raise ToolError("software state schema v1 only supports target flashbin")
    identity = normalize_identity(raw.get("identity"), "manifest.identity")
    notes_raw = mapping_value(raw.get("identity_notes") or {}, "manifest.identity_notes")
    reject_unknown_keys(notes_raw, set(IDENTITY_FIELDS), "manifest.identity_notes")
    identity_notes = {
        field: text_value(value, f"manifest.identity_notes.{field}")
        for field, value in notes_raw.items()
    }
    for field, value in identity.items():
        if " ".join(value.lower().split()) in NOT_APPLICABLE_VALUES:
            if field not in identity_notes:
                raise ToolError(
                    f"manifest.identity.{field} is N/A but "
                    f"manifest.identity_notes.{field} has no reason"
                )
    profile = load_profile(target)
    components_raw = mapping_value(raw.get("components"), "manifest.components")
    expected_components = set(profile["components"])
    if set(components_raw) != expected_components:
        missing = sorted(expected_components - set(components_raw))
        extra = sorted(set(components_raw) - expected_components)
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if extra:
            details.append("unsupported: " + ", ".join(extra))
        raise ToolError("manifest.components must cover the profile (" + "; ".join(details) + ")")

    components: dict[str, dict[str, Any]] = {}
    for component_id, profile_item in profile["components"].items():
        label = f"manifest.components.{component_id}"
        item = mapping_value(components_raw[component_id], label)
        status = text_value(item.get("status"), f"{label}.status")
        if status == "not_applicable":
            reject_unknown_keys(item, {"status", "reason"}, label)
            components[component_id] = {
                "status": status,
                "reason": text_value(item.get("reason"), f"{label}.reason"),
                "kind": profile_item["kind"],
            }
            continue
        if status != "enabled":
            raise ToolError(f"{label}.status must be enabled or not_applicable")
        kind = profile_item["kind"]
        if kind == "fixed_input":
            reject_unknown_keys(item, {"status", "inputs"}, label)
            components[component_id] = {
                "status": status,
                "kind": kind,
                "inputs": _normalize_paths(item.get("inputs"), f"{label}.inputs"),
            }
            continue
        reject_unknown_keys(
            item,
            {"status", "source", "configuration", "toolchains", "outputs"},
            label,
        )
        toolchains = _normalize_toolchains(
            item.get("toolchains"), f"{label}.toolchains"
        )
        if kind == "build" and not toolchains:
            raise ToolError(f"{label}.toolchains must declare at least one toolchain")
        components[component_id] = {
            "status": status,
            "kind": kind,
            "source": _normalize_source(item.get("source"), f"{label}.source", case_root),
            "configuration": _normalize_configuration(
                item.get("configuration"), f"{label}.configuration"
            ),
            "toolchains": toolchains,
            "outputs": _normalize_paths(item.get("outputs"), f"{label}.outputs"),
        }
        for output in components[component_id]["outputs"]:
            require_within(Path(output), case_root, f"{label}.outputs")

    if components["flashbin"]["status"] != "enabled":
        raise ToolError("manifest.components.flashbin must be enabled")
    normalized = {
        "schema_version": 1,
        "path": str(path),
        "case": case,
        "case_root": str(case_root),
        "target": target,
        "identity": identity,
        "identity_notes": identity_notes,
        "profile": profile,
        "components": components,
    }
    normalized["hash"] = hash_data(
        {key: value for key, value in normalized.items() if key not in {"path", "hash"}}
    )
    return normalized
