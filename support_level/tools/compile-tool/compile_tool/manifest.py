from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    REF_RE,
    ToolError,
    hash_data,
    is_within,
    load_yaml,
    mapping_value,
    reject_unknown_keys,
    require_within,
    resolve_absolute,
    text_value,
)
from .commands import validate_command_policy_parameters
from .guards import (
    normalize_parameters,
    select_command_policies,
    select_execution_policies,
    select_guards,
    validate_guard_parameters,
)


TOOL_DIR = Path(__file__).resolve().parents[1]
SUPPORT_LEVEL = TOOL_DIR.parent.parent
PROFILE_PATHS = {
    "flashbin": SUPPORT_LEVEL / "compile_targets" / "flashbin" / "DEPENDENCIES.yaml"
}


def _managed_git_component_sources(
    component: dict[str, Any],
    sources: dict[str, dict[str, Any]] | None,
) -> list[tuple[str | None, dict[str, Any]]]:
    if "source" in component:
        source = component["source"]
        return [(None, source)] if source["kind"] == "managed_git" else []
    assert sources is not None
    return [
        (source_id, sources[source_id])
        for source_id in component["sources"]
        if sources[source_id]["kind"] == "managed_git"
    ]


def _apply_execution_policies(
    *,
    case_root: Path,
    target: str,
    components: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]] | None,
    policies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    for policy in policies:
        component_id = policy["component"]
        component = components[component_id]
        candidates = _managed_git_component_sources(component, sources)
        if not candidates:
            continue
        if len(candidates) != 1:
            raise ToolError(
                f"execution policy {policy['id']} requires exactly one managed_git "
                f"source for {target}/{component_id}"
            )
        if "execution" in component:
            raise ToolError(
                f"multiple execution policies apply to {target}/{component_id}"
            )
        source_id, source = candidates[0]
        workspace = (
            case_root
            / "build"
            / ".compile-tool"
            / target
            / component_id
            / "source"
        ).resolve(strict=False)
        require_within(
            workspace,
            case_root,
            f"execution policy {policy['id']} workspace",
        )
        source_path = Path(source["case_path"]).resolve(strict=False)
        if is_within(workspace, source_path) or is_within(source_path, workspace):
            raise ToolError(
                f"execution policy {policy['id']} workspace must be separate from "
                f"the managed source: {source_path}"
            )
        component["execution"] = {
            "mode": policy["mode"],
            "contract_version": 1,
            "workspace": str(workspace),
            "source_id": source_id,
            "source": source,
            "policy_id": policy["id"],
            "policy_path": policy["policy_path"],
        }
        active.append({**policy, "workspace": str(workspace)})
    return active


def _apply_guard_parameters(
    components: dict[str, dict[str, Any]],
    parameters: dict[str, dict[str, str]],
    guards: list[dict[str, Any]],
) -> None:
    for guard in guards:
        parameter = parameters[guard["parameter"]]
        values = components[guard["component"]]["configuration"]["values"]
        prefix = f"compile_tool_guard.{guard['parameter']}"
        values[f"{prefix}.value"] = parameter["value"]
        values[f"{prefix}.source"] = parameter["source"]


def _apply_command_policy_parameters(
    components: dict[str, dict[str, Any]],
    parameters: dict[str, dict[str, str]],
    policies: list[dict[str, Any]],
) -> None:
    for policy in policies:
        parameter = parameters[policy["parameter"]]
        values = components[policy["component"]]["configuration"]["values"]
        prefix = f"compile_tool_policy.{policy['parameter']}"
        values[f"{prefix}.value"] = parameter["value"]
        values[f"{prefix}.source"] = parameter["source"]


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


def _load_v1_manifest(
    path: Path,
    raw: dict[str, Any],
    *,
    validate_guards: bool,
) -> dict[str, Any]:
    reject_unknown_keys(
        raw,
        {
            "schema_version",
            "case",
            "case_root",
            "target",
            "parameters",
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
    parameters = normalize_parameters(raw.get("parameters"), "manifest.parameters")
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
    enabled_components = {
        component_id
        for component_id, component in components.items()
        if component["status"] == "enabled"
    }
    guards = select_guards(target, enabled_components)
    command_policies = select_command_policies(target, enabled_components)
    execution_policies = _apply_execution_policies(
        case_root=case_root,
        target=target,
        components=components,
        sources=None,
        policies=select_execution_policies(target, enabled_components),
    )
    if validate_guards:
        validate_guard_parameters(parameters, guards)
        validate_command_policy_parameters(parameters, command_policies)
        _apply_guard_parameters(components, parameters, guards)
        _apply_command_policy_parameters(components, parameters, command_policies)
    normalized = {
        "schema_version": 1,
        "path": str(path),
        "case": case,
        "case_root": str(case_root),
        "target": target,
        "parameters": parameters,
        "guards": guards,
        "command_policies": command_policies,
        "execution_policies": execution_policies,
        "profile": profile,
        "components": components,
    }
    normalized["hash"] = hash_data(
        {key: value for key, value in normalized.items() if key not in {"path", "hash"}}
    )
    return normalized


def _normalize_git_source_v2(
    raw_value: Any,
    label: str,
    case_root: Path,
) -> dict[str, Any]:
    source = _normalize_source(raw_value, label, case_root)
    if source["kind"] != "managed_git":
        raise ToolError(f"{label} must describe a managed_git repository")
    return source


def _normalize_source_v2(
    raw_value: Any,
    label: str,
    case_root: Path,
) -> dict[str, Any]:
    raw = mapping_value(raw_value, label)
    kind = text_value(raw.get("kind"), f"{label}.kind")
    if kind in {"managed_git", "local_files"}:
        source = _normalize_source(raw, label, case_root)
        if kind == "local_files":
            for index, value in enumerate(source["paths"], start=1):
                require_within(
                    Path(value), case_root, f"{label}.paths[{index}]"
                )
        return source
    if kind == "managed_git_set":
        reject_unknown_keys(raw, {"kind", "repositories"}, label)
        repositories_raw = raw.get("repositories")
        if not isinstance(repositories_raw, list) or not repositories_raw:
            raise ToolError(f"{label}.repositories must be a non-empty list")
        repositories: list[dict[str, Any]] = []
        names: set[str] = set()
        case_paths: set[str] = set()
        for index, value in enumerate(repositories_raw, start=1):
            item_label = f"{label}.repositories[{index}]"
            item = mapping_value(value, item_label)
            name = text_value(item.get("name"), f"{item_label}.name")
            if name in names:
                raise ToolError(f"{label}.repositories has duplicate name: {name}")
            names.add(name)
            repo_data = dict(item)
            repo_data.pop("name", None)
            repo_data["kind"] = "managed_git"
            repository = _normalize_git_source_v2(
                repo_data, item_label, case_root
            )
            if repository["case_path"] in case_paths:
                raise ToolError(
                    f"{label}.repositories has duplicate case_path: "
                    f"{repository['case_path']}"
                )
            case_paths.add(repository["case_path"])
            repositories.append({"name": name, **repository})
        return {"kind": kind, "repositories": repositories}
    if kind == "release_archive":
        reject_unknown_keys(raw, {"kind", "archive_path", "case_path"}, label)
        archive_path = resolve_absolute(
            raw.get("archive_path"), f"{label}.archive_path"
        )
        case_path = resolve_absolute(raw.get("case_path"), f"{label}.case_path")
        require_within(case_path, case_root, f"{label}.case_path")
        if archive_path == case_path or is_within(archive_path, case_root):
            raise ToolError(f"{label}.archive_path must be outside the case")
        return {
            "kind": kind,
            "archive_path": str(archive_path),
            "case_path": str(case_path),
        }
    raise ToolError(
        f"{label}.kind must be managed_git, managed_git_set, "
        "release_archive, or local_files"
    )


def _normalize_tools_v2(raw_value: Any, label: str) -> list[dict[str, Any]]:
    raw = raw_value or []
    if not isinstance(raw, list) or not raw:
        raise ToolError(f"{label} must be a non-empty list")
    result: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, value in enumerate(raw, start=1):
        item_label = f"{label}[{index}]"
        item = mapping_value(value, item_label)
        reject_unknown_keys(
            item, {"name", "executable", "version_args"}, item_label
        )
        name = text_value(item.get("name"), f"{item_label}.name")
        if name in names:
            raise ToolError(f"{label} has duplicate tool name: {name}")
        names.add(name)
        executable = resolve_absolute(
            item.get("executable"), f"{item_label}.executable"
        )
        args = item.get("version_args")
        if args is None:
            args = ["--version"]
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ToolError(f"{item_label}.version_args must be a string list")
        result.append(
            {
                "name": name,
                "executable": str(executable),
                "version_args": args,
            }
        )
    return result


def _normalize_generic_paths(
    raw_value: Any,
    label: str,
    case_root: Path,
    *,
    allow_empty: bool,
) -> list[str]:
    raw = raw_value or []
    if not isinstance(raw, list) or (not raw and not allow_empty):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise ToolError(f"{label} must be {qualifier}")
    result: list[str] = []
    for index, value in enumerate(raw, start=1):
        path = resolve_absolute(value, f"{label}[{index}]")
        require_within(path, case_root, f"{label}[{index}]")
        result.append(str(path))
    if len(result) != len(set(result)):
        raise ToolError(f"{label} contains duplicate paths")
    return result


def _topological_order_generic(
    components: dict[str, dict[str, Any]],
) -> list[str]:
    graph = {
        component_id: {"depends_on": component["depends_on"]}
        for component_id, component in components.items()
    }
    return _topological_order(graph)


def _load_v2_manifest(
    path: Path,
    raw: dict[str, Any],
    *,
    validate_guards: bool,
) -> dict[str, Any]:
    reject_unknown_keys(
        raw,
        {
            "schema_version",
            "case",
            "case_root",
            "target",
            "parameters",
            "sources",
            "components",
        },
        "manifest",
    )
    case = text_value(raw.get("case"), "manifest.case")
    case_root = resolve_absolute(raw.get("case_root"), "manifest.case_root")
    if not case_root.is_dir():
        raise ToolError(f"manifest.case_root is not an existing directory: {case_root}")
    if case_root.name != case:
        raise ToolError("manifest.case must match the case_root directory name")
    target = text_value(raw.get("target"), "manifest.target")
    if not REF_RE.fullmatch(target) or "/" in target:
        raise ToolError(f"manifest.target contains unsafe characters: {target!r}")
    expected_path = case_root / "records" / "compile" / target / "manifest.yaml"
    if path != expected_path.resolve(strict=False):
        raise ToolError(f"compile manifest must be stored at {expected_path}")

    parameters = normalize_parameters(raw.get("parameters"), "manifest.parameters")

    sources_raw = mapping_value(raw.get("sources") or {}, "manifest.sources")
    sources: dict[str, dict[str, Any]] = {}
    for source_id, value in sources_raw.items():
        if not isinstance(source_id, str) or not source_id or "/" in source_id:
            raise ToolError(f"manifest.sources has invalid id: {source_id!r}")
        sources[source_id] = _normalize_source_v2(
            value, f"manifest.sources.{source_id}", case_root
        )

    components_raw = mapping_value(raw.get("components"), "manifest.components")
    if not components_raw:
        raise ToolError("manifest.components must not be empty")
    components: dict[str, dict[str, Any]] = {}
    for component_id, value in components_raw.items():
        if not isinstance(component_id, str) or not component_id or "/" in component_id:
            raise ToolError(f"manifest.components has invalid id: {component_id!r}")
        label = f"manifest.components.{component_id}"
        item = mapping_value(value, label)
        reject_unknown_keys(
            item,
            {
                "sources",
                "configuration",
                "tools",
                "watched_inputs",
                "outputs",
                "depends_on",
            },
            label,
        )
        source_refs = item.get("sources") or []
        if not isinstance(source_refs, list) or not all(
            isinstance(source_id, str) and source_id for source_id in source_refs
        ):
            raise ToolError(f"{label}.sources must be a string list")
        if len(source_refs) != len(set(source_refs)):
            raise ToolError(f"{label}.sources contains duplicates")
        missing_sources = sorted(set(source_refs) - set(sources))
        if missing_sources:
            raise ToolError(
                f"{label}.sources has unknown ids: {', '.join(missing_sources)}"
            )
        dependencies = item.get("depends_on") or []
        if not isinstance(dependencies, list) or not all(
            isinstance(entry, str) and entry for entry in dependencies
        ):
            raise ToolError(f"{label}.depends_on must be a string list")
        if len(dependencies) != len(set(dependencies)):
            raise ToolError(f"{label}.depends_on contains duplicates")
        watched_inputs = _normalize_generic_paths(
            item.get("watched_inputs"),
            f"{label}.watched_inputs",
            case_root,
            allow_empty=True,
        )
        outputs = _normalize_generic_paths(
            item.get("outputs"),
            f"{label}.outputs",
            case_root,
            allow_empty=False,
        )
        for watched in map(Path, watched_inputs):
            for output in map(Path, outputs):
                if watched == output or is_within(output, watched):
                    raise ToolError(
                        f"{label}.outputs must not be inside watched_inputs: {output}"
                    )
        configuration = _normalize_configuration(
            item.get("configuration"), f"{label}.configuration"
        )
        for index, value in enumerate(configuration["files"], start=1):
            require_within(
                Path(value), case_root, f"{label}.configuration.files[{index}]"
            )
        components[component_id] = {
            "status": "enabled",
            "kind": "build",
            "sources": source_refs,
            "configuration": configuration,
            "toolchains": _normalize_tools_v2(item.get("tools"), f"{label}.tools"),
            "watched_inputs": watched_inputs,
            "outputs": outputs,
            "depends_on": dependencies,
        }

    for component_id, component in components.items():
        missing = sorted(set(component["depends_on"]) - set(components))
        if missing:
            raise ToolError(
                f"manifest.components.{component_id}.depends_on has unknown ids: "
                + ", ".join(missing)
            )
        if component_id in component["depends_on"]:
            raise ToolError(f"component {component_id} cannot depend on itself")
    order = _topological_order_generic(components)
    guards = select_guards(target, set(components))
    command_policies = select_command_policies(target, set(components))
    execution_policies = _apply_execution_policies(
        case_root=case_root,
        target=target,
        components=components,
        sources=sources,
        policies=select_execution_policies(target, set(components)),
    )
    if validate_guards:
        validate_guard_parameters(parameters, guards)
        validate_command_policy_parameters(parameters, command_policies)
        _apply_guard_parameters(components, parameters, guards)
        _apply_command_policy_parameters(components, parameters, command_policies)
    profile = {
        "schema_version": 2,
        "target": target,
        "components": {
            component_id: {
                "kind": "build",
                "depends_on": component["depends_on"],
            }
            for component_id, component in components.items()
        },
    }
    profile["hash"] = hash_data(profile)
    normalized = {
        "schema_version": 2,
        "path": str(path),
        "case": case,
        "case_root": str(case_root),
        "target": target,
        "parameters": parameters,
        "guards": guards,
        "command_policies": command_policies,
        "execution_policies": execution_policies,
        "profile": profile,
        "sources": sources,
        "components": components,
        "component_order": order,
        "generic": True,
    }
    normalized["hash"] = hash_data(
        {key: value for key, value in normalized.items() if key not in {"path", "hash"}}
    )
    return normalized


def load_manifest(path: Path, *, validate_guards: bool = True) -> dict[str, Any]:
    path = path.expanduser().resolve(strict=False)
    raw = mapping_value(load_yaml(path, "compile manifest"), "compile manifest")
    version = raw.get("schema_version")
    if version == 1:
        return _load_v1_manifest(path, raw, validate_guards=validate_guards)
    if version == 2:
        return _load_v2_manifest(path, raw, validate_guards=validate_guards)
    raise ToolError(f"compile manifest schema_version must be 1 or 2, got {version!r}")
