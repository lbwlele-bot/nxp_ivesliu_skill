from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .common import (
    REF_RE,
    ToolError,
    atomic_write_yaml,
    hash_data,
    load_yaml,
    mapping_value,
    reject_unknown_keys,
    require_within,
    resolve_absolute,
    text_value,
)
from .guards import PARAMETER_SOURCES, SAFE_ID_RE, UNRESOLVED_VALUES


TOOL_DIR = Path(__file__).resolve().parents[1]
SUPPORT_LEVEL = TOOL_DIR.parent.parent
PROJECTS_ROOT = SUPPORT_LEVEL / "code_assets" / "projects"
PROFILE_NAME = "COMPILE_PROFILE.yaml"
CHECKLIST_NAME = "COMPILE_CHECKLIST.yaml"
REQUIRED_PLACEHOLDER = "TBD"
CHECKLIST_REFERENCE_RE = re.compile(
    r"\$\{(parameters|tools|tool_prefix)\.([A-Za-z0-9][A-Za-z0-9._-]*)\}"
)


def _safe_id(value: Any, label: str) -> str:
    result = text_value(value, label)
    if not SAFE_ID_RE.fullmatch(result):
        raise ToolError(f"{label} contains unsafe characters: {result!r}")
    return result


def _relative_path(value: Any, label: str) -> Path:
    result = Path(text_value(value, label))
    if result.is_absolute() or not result.parts or ".." in result.parts:
        raise ToolError(f"{label} must be a safe relative path")
    return result


def _normalize_profile_parameters(raw_value: Any, label: str) -> dict[str, dict[str, Any]]:
    raw = mapping_value(raw_value or {}, label)
    result: dict[str, dict[str, Any]] = {}
    for parameter_id, value in raw.items():
        parameter = _safe_id(parameter_id, f"{label} key")
        item_label = f"{label}.{parameter}"
        item = mapping_value(value, item_label)
        reject_unknown_keys(
            item,
            {"source", "required", "default", "allowed", "pattern"},
            item_label,
        )
        source = text_value(item.get("source"), f"{item_label}.source")
        if source not in PARAMETER_SOURCES:
            raise ToolError(
                f"{item_label}.source must be one of: "
                + ", ".join(sorted(PARAMETER_SOURCES))
            )
        required = item.get("required", False)
        if not isinstance(required, bool):
            raise ToolError(f"{item_label}.required must be boolean")
        default = item.get("default")
        if default is not None and not isinstance(default, (str, int, float, bool)):
            raise ToolError(f"{item_label}.default must be a scalar")
        if required and default is not None:
            raise ToolError(f"{item_label} cannot set both required and default")
        allowed_raw = item.get("allowed")
        allowed: list[str] | None = None
        if allowed_raw is not None:
            if not isinstance(allowed_raw, list) or not allowed_raw or not all(
                isinstance(entry, (str, int, float, bool)) for entry in allowed_raw
            ):
                raise ToolError(f"{item_label}.allowed must be a non-empty scalar list")
            allowed = [str(entry) for entry in allowed_raw]
            if len(allowed) != len(set(allowed)):
                raise ToolError(f"{item_label}.allowed contains duplicates")
        pattern = item.get("pattern")
        if pattern is not None:
            pattern = text_value(pattern, f"{item_label}.pattern")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ToolError(f"{item_label}.pattern is invalid: {exc}") from exc
        if allowed is not None and default is not None and str(default) not in allowed:
            raise ToolError(f"{item_label}.default is outside the allowed values")
        if pattern is not None and default is not None and re.fullmatch(pattern, str(default)) is None:
            raise ToolError(f"{item_label}.default does not match its pattern")
        result[parameter] = {
            "source": source,
            "required": required,
            **({"default": str(default)} if default is not None else {}),
            **({"allowed": allowed} if allowed is not None else {}),
            **({"pattern": pattern} if pattern is not None else {}),
        }
    return result


def _normalize_profile_tools(
    raw_value: Any, label: str, support_level: Path
) -> list[dict[str, Any]]:
    raw = raw_value or []
    if not isinstance(raw, list) or not raw:
        raise ToolError(f"{label} must be a non-empty list")
    result: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, value in enumerate(raw, start=1):
        item_label = f"{label}[{index}]"
        item = mapping_value(value, item_label)
        reject_unknown_keys(item, {"name", "path", "version_args"}, item_label)
        name = _safe_id(item.get("name"), f"{item_label}.name")
        if name in names:
            raise ToolError(f"{label} has duplicate tool name: {name}")
        names.add(name)
        raw_path = Path(text_value(item.get("path"), f"{item_label}.path"))
        if raw_path.is_absolute():
            executable = raw_path.resolve(strict=False)
            stored_path = str(raw_path)
        else:
            relative = _relative_path(item.get("path"), f"{item_label}.path")
            executable = (support_level / relative).resolve(strict=False)
            require_within(executable, support_level, f"{item_label}.path")
            stored_path = relative.as_posix()
        version_args = item.get("version_args", ["--version"])
        if not isinstance(version_args, list) or not all(
            isinstance(arg, str) for arg in version_args
        ):
            raise ToolError(f"{item_label}.version_args must be a string list")
        result.append(
            {
                "name": name,
                "path": stored_path,
                "executable": str(executable),
                "version_args": version_args,
            }
        )
    return result


def _normalize_profile_outputs(
    raw_value: Any,
    label: str,
    parameters: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    raw = mapping_value(raw_value, label)
    if not raw:
        raise ToolError(f"{label} must not be empty")
    result: dict[str, dict[str, Any]] = {}
    for artifact_id, value in raw.items():
        artifact = _safe_id(artifact_id, f"{label} key")
        item_label = f"{label}.{artifact}"
        item = mapping_value(value, item_label)
        reject_unknown_keys(
            item,
            {"type", "path", "identity_parameters"},
            item_label,
        )
        identity_parameters = item.get("identity_parameters") or []
        if not isinstance(identity_parameters, list) or not all(
            isinstance(entry, str) and entry for entry in identity_parameters
        ):
            raise ToolError(f"{item_label}.identity_parameters must be a string list")
        if len(identity_parameters) != len(set(identity_parameters)):
            raise ToolError(f"{item_label}.identity_parameters contains duplicates")
        missing = sorted(set(identity_parameters) - set(parameters))
        if missing:
            raise ToolError(
                f"{item_label}.identity_parameters has unknown parameters: "
                + ", ".join(missing)
            )
        result[artifact] = {
            "type": text_value(item.get("type"), f"{item_label}.type"),
            "path": _relative_path(item.get("path"), f"{item_label}.path").as_posix(),
            "identity_parameters": identity_parameters,
        }
    return result


def _normalize_artifact_slots(
    raw_value: Any,
    label: str,
    parameters: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    raw = mapping_value(raw_value or {}, label)
    result: dict[str, dict[str, Any]] = {}
    for slot_id, value in raw.items():
        slot = _safe_id(slot_id, f"{label} key")
        item_label = f"{label}.{slot}"
        item = mapping_value(value, item_label)
        reject_unknown_keys(
            item,
            {"type", "multiple", "required_when", "parameter_matches"},
            item_label,
        )
        multiple = item.get("multiple", False)
        if not isinstance(multiple, bool):
            raise ToolError(f"{item_label}.multiple must be boolean")
        required_when_raw = item.get("required_when")
        required_when = None
        if required_when_raw is not None:
            condition_label = f"{item_label}.required_when"
            condition = mapping_value(required_when_raw, condition_label)
            reject_unknown_keys(condition, {"parameter", "equals"}, condition_label)
            parameter = text_value(
                condition.get("parameter"), f"{condition_label}.parameter"
            )
            if parameter not in parameters:
                raise ToolError(
                    f"{condition_label}.parameter is unknown: {parameter}"
                )
            required_when = {
                "parameter": parameter,
                "equals": text_value(condition.get("equals"), f"{condition_label}.equals"),
            }
        matches_raw = mapping_value(
            item.get("parameter_matches") or {},
            f"{item_label}.parameter_matches",
        )
        matches: dict[str, str] = {}
        for producer_key, consumer_parameter in matches_raw.items():
            producer = _safe_id(
                producer_key, f"{item_label}.parameter_matches key"
            )
            consumer = text_value(
                consumer_parameter,
                f"{item_label}.parameter_matches.{producer}",
            )
            if consumer not in parameters:
                raise ToolError(
                    f"{item_label}.parameter_matches references unknown consumer "
                    f"parameter: {consumer}"
                )
            matches[producer] = consumer
        result[slot] = {
            "type": text_value(item.get("type"), f"{item_label}.type"),
            "multiple": multiple,
            "required_when": required_when,
            "parameter_matches": matches,
        }
    return result


def _normalize_file_slots(raw_value: Any, label: str) -> dict[str, dict[str, Any]]:
    raw = mapping_value(raw_value or {}, label)
    result: dict[str, dict[str, Any]] = {}
    for slot_id, value in raw.items():
        slot = _safe_id(slot_id, f"{label} key")
        item_label = f"{label}.{slot}"
        item = mapping_value(value, item_label)
        reject_unknown_keys(item, {"multiple"}, item_label)
        multiple = item.get("multiple", False)
        if not isinstance(multiple, bool):
            raise ToolError(f"{item_label}.multiple must be boolean")
        result[slot] = {"multiple": multiple}
    return result


def _checklist_template_references(
    value: str,
    label: str,
    parameters: dict[str, dict[str, Any]],
    tools: list[dict[str, Any]],
) -> None:
    tool_names = {tool["name"] for tool in tools}
    for match in CHECKLIST_REFERENCE_RE.finditer(value):
        kind, name = match.groups()
        if kind == "parameters" and name not in parameters:
            raise ToolError(f"{label} references unknown parameter: {name}")
        if kind in {"tools", "tool_prefix"} and name not in tool_names:
            raise ToolError(f"{label} references unknown tool: {name}")
    if "${" in CHECKLIST_REFERENCE_RE.sub("", value):
        raise ToolError(f"{label} contains an unsupported checklist expression")


def _normalize_checklist_condition(
    raw_value: Any,
    label: str,
    parameters: dict[str, dict[str, Any]],
) -> dict[str, str]:
    raw = mapping_value(raw_value, label)
    reject_unknown_keys(raw, {"parameter", "equals"}, label)
    parameter = text_value(raw.get("parameter"), f"{label}.parameter")
    if parameter not in parameters:
        raise ToolError(f"{label}.parameter is unknown: {parameter}")
    return {
        "parameter": parameter,
        "equals": text_value(raw.get("equals"), f"{label}.equals"),
    }


def _normalize_checklist_token(
    raw_value: Any,
    label: str,
    parameters: dict[str, dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    if isinstance(raw_value, str):
        value = raw_value
        omit_when = None
    else:
        raw = mapping_value(raw_value, label)
        reject_unknown_keys(raw, {"value", "omit_when"}, label)
        value = text_value(raw.get("value"), f"{label}.value")
        omit_when = (
            _normalize_checklist_condition(
                raw.get("omit_when"), f"{label}.omit_when", parameters
            )
            if raw.get("omit_when") is not None
            else None
        )
    if not value:
        raise ToolError(f"{label} must not be empty")
    _checklist_template_references(value, label, parameters, tools)
    return {"value": value, "omit_when": omit_when}


def _normalize_checklist_build(
    raw_value: Any,
    label: str,
    parameters: dict[str, dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    raw = mapping_value(raw_value, label)
    reject_unknown_keys(raw, {"mode", "env", "steps"}, label)
    mode = text_value(raw.get("mode"), f"{label}.mode")
    if mode != "isolated_git":
        raise ToolError(f"{label}.mode must be isolated_git")
    env_raw = mapping_value(raw.get("env") or {}, f"{label}.env")
    env: dict[str, str] = {}
    for name, value in env_raw.items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ToolError(f"{label}.env has an invalid variable name: {name!r}")
        rendered = text_value(value, f"{label}.env.{name}")
        _checklist_template_references(
            rendered, f"{label}.env.{name}", parameters, tools
        )
        env[name] = rendered
    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ToolError(f"{label}.steps must be a non-empty list")
    steps: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, value in enumerate(steps_raw, start=1):
        step_label = f"{label}.steps[{index}]"
        step = mapping_value(value, step_label)
        reject_unknown_keys(step, {"name", "command"}, step_label)
        name = _safe_id(step.get("name"), f"{step_label}.name")
        if name in names:
            raise ToolError(f"{label}.steps has duplicate name: {name}")
        names.add(name)
        command_raw = step.get("command")
        if not isinstance(command_raw, list) or not command_raw:
            raise ToolError(f"{step_label}.command must be a non-empty token list")
        steps.append(
            {
                "name": name,
                "command": [
                    _normalize_checklist_token(
                        token,
                        f"{step_label}.command[{token_index}]",
                        parameters,
                        tools,
                    )
                    for token_index, token in enumerate(command_raw, start=1)
                ],
            }
        )
    return {"mode": mode, "env": env, "steps": steps}


def _normalize_input_contract(
    raw_value: Any,
    label: str,
    parameters: dict[str, dict[str, Any]],
    support_level: Path,
) -> dict[str, Any] | None:
    if raw_value is None:
        return None
    raw = mapping_value(raw_value, label)
    reject_unknown_keys(raw, {"path", "selectors"}, label)
    relative = _relative_path(raw.get("path"), f"{label}.path")
    path = (support_level / relative).resolve(strict=False)
    require_within(path, support_level, f"{label}.path")
    if not path.is_file():
        raise ToolError(f"{label}.path is not an existing file: {path}")
    selectors = raw.get("selectors")
    if not isinstance(selectors, list) or not selectors or not all(
        isinstance(entry, str) and entry for entry in selectors
    ):
        raise ToolError(f"{label}.selectors must be a non-empty parameter list")
    if len(selectors) != len(set(selectors)):
        raise ToolError(f"{label}.selectors contains duplicates")
    unknown = sorted(set(selectors) - set(parameters))
    if unknown:
        raise ToolError(
            f"{label}.selectors references unknown parameters: " + ", ".join(unknown)
        )
    contract = mapping_value(load_yaml(path, label), label)
    return {
        "path": str(path),
        "selectors": selectors,
        "hash": hash_data(contract),
    }


def _normalize_make_recipe_inputs(
    raw_value: Any,
    label: str,
    parameters: dict[str, dict[str, Any]],
    artifact_inputs: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if raw_value is None:
        return None
    raw = mapping_value(raw_value, label)
    reject_unknown_keys(
        raw,
        {
            "soc_parameter",
            "recipe_parameter",
            "m_payload_slot",
            "soc_identity_overrides",
        },
        label,
    )
    soc_parameter = _safe_id(raw.get("soc_parameter"), f"{label}.soc_parameter")
    recipe_parameter = _safe_id(
        raw.get("recipe_parameter"), f"{label}.recipe_parameter"
    )
    for parameter in (soc_parameter, recipe_parameter):
        if parameter not in parameters:
            raise ToolError(f"{label} references unknown parameter: {parameter}")
    slot = _safe_id(raw.get("m_payload_slot"), f"{label}.m_payload_slot")
    if slot not in artifact_inputs:
        raise ToolError(f"{label}.m_payload_slot references unknown artifact slot: {slot}")
    overrides_raw = mapping_value(
        raw.get("soc_identity_overrides") or {},
        f"{label}.soc_identity_overrides",
    )
    overrides = {
        _safe_id(name, f"{label}.soc_identity_overrides key"): _safe_id(
            value, f"{label}.soc_identity_overrides.{name}"
        )
        for name, value in overrides_raw.items()
    }
    return {
        "soc_parameter": soc_parameter,
        "recipe_parameter": recipe_parameter,
        "m_payload_slot": slot,
        "soc_identity_overrides": overrides,
    }


def profile_path(project: str) -> Path:
    project_id = _safe_id(project, "project")
    return (PROJECTS_ROOT / project_id / PROFILE_NAME).resolve(strict=False)


def has_project_checklist(project: str) -> bool:
    if not SAFE_ID_RE.fullmatch(project):
        return False
    if project == "m_freertos_sdk":
        return (
            SUPPORT_LEVEL
            / "compile_targets"
            / project
            / CHECKLIST_NAME
        ).is_file()
    root = PROJECTS_ROOT / project
    return (root / PROFILE_NAME).is_file() and (root / CHECKLIST_NAME).is_file()


def load_compile_profile(project_or_path: str | Path) -> dict[str, Any]:
    candidate = Path(project_or_path)
    path = (
        candidate.expanduser().resolve(strict=False)
        if candidate.is_absolute() or candidate.name == PROFILE_NAME
        else profile_path(str(project_or_path))
    )
    if not path.is_file():
        raise ToolError(f"compile profile does not exist: {path}")
    project_root = path.parent
    projects_root = project_root.parent
    if (
        projects_root.name != "projects"
        or projects_root.parent.name != "code_assets"
        or projects_root.parent.parent.name != "support_level"
    ):
        raise ToolError(
            "compile profile must be directly below "
            "support_level/code_assets/projects/<project>"
        )
    support_level = projects_root.parent.parent
    raw = mapping_value(load_yaml(path, "compile profile"), "compile profile")
    reject_unknown_keys(
        raw,
        {
            "schema_version",
            "id",
            "type",
            "target",
            "component",
            "action",
            "source",
            "parameters",
            "configuration_parameters",
            "tools",
            "watched_inputs",
            "outputs",
            "artifact_inputs",
            "file_inputs",
            "checklist_build",
            "input_contract",
            "fixed_asset_contract",
            "make_recipe_inputs",
        },
        "compile profile",
    )
    if raw.get("schema_version") != 1:
        raise ToolError("compile profile schema_version must be 1")
    if raw.get("type") != "project_compile":
        raise ToolError("compile profile type must be project_compile")
    profile_id = _safe_id(raw.get("id"), "compile profile.id")
    if project_root.name != profile_id:
        raise ToolError("compile profile.id must match its project directory name")
    target = _safe_id(raw.get("target"), "compile profile.target")
    component = _safe_id(raw.get("component"), "compile profile.component")
    if target != profile_id or component != profile_id:
        raise ToolError("project compile profile target and component must match id")
    action = text_value(raw.get("action", "rebuild"), "compile profile.action")
    if action not in {"rebuild", "repack"}:
        raise ToolError("compile profile.action must be rebuild or repack")
    parameters = _normalize_profile_parameters(
        raw.get("parameters"), "compile profile.parameters"
    )
    configuration_parameters = raw.get("configuration_parameters") or []
    if not isinstance(configuration_parameters, list) or not all(
        isinstance(entry, str) and entry for entry in configuration_parameters
    ):
        raise ToolError("compile profile.configuration_parameters must be a string list")
    if len(configuration_parameters) != len(set(configuration_parameters)):
        raise ToolError("compile profile.configuration_parameters contains duplicates")
    missing_configuration = sorted(set(configuration_parameters) - set(parameters))
    if missing_configuration:
        raise ToolError(
            "compile profile.configuration_parameters has unknown parameters: "
            + ", ".join(missing_configuration)
        )
    source_raw = mapping_value(raw.get("source"), "compile profile.source")
    reject_unknown_keys(
        source_raw,
        {
            "id",
            "path",
            "case_path",
            "ref_kind",
            "remote",
            "remote_url",
            "update",
        },
        "compile profile.source",
    )
    source_id = _safe_id(source_raw.get("id"), "compile profile.source.id")
    source_relative = _relative_path(
        source_raw.get("path"), "compile profile.source.path"
    )
    canonical = (project_root / source_relative).resolve(strict=False)
    require_within(canonical, project_root, "compile profile.source.path")
    case_relative = _relative_path(
        source_raw.get("case_path"), "compile profile.source.case_path"
    )
    ref_kind = text_value(
        source_raw.get("ref_kind", "tag"), "compile profile.source.ref_kind"
    )
    if ref_kind not in {"branch", "tag", "commit"}:
        raise ToolError("compile profile.source.ref_kind must be branch, tag, or commit")
    update = text_value(
        source_raw.get("update", "if_missing"), "compile profile.source.update"
    )
    if update not in {"if_missing", "pull_ff_only"}:
        raise ToolError("compile profile.source.update must be if_missing or pull_ff_only")
    if update == "pull_ff_only" and ref_kind != "branch":
        raise ToolError("compile profile source pull_ff_only requires ref_kind=branch")
    watched_inputs_raw = raw.get("watched_inputs") or []
    if not isinstance(watched_inputs_raw, list):
        raise ToolError("compile profile.watched_inputs must be a path list")
    watched_inputs = [
        _relative_path(value, f"compile profile.watched_inputs[{index}]").as_posix()
        for index, value in enumerate(watched_inputs_raw, start=1)
    ]
    tools = _normalize_profile_tools(
        raw.get("tools"), "compile profile.tools", support_level
    )
    outputs = _normalize_profile_outputs(
        raw.get("outputs"), "compile profile.outputs", parameters
    )
    artifact_inputs = _normalize_artifact_slots(
        raw.get("artifact_inputs"), "compile profile.artifact_inputs", parameters
    )
    file_inputs = _normalize_file_slots(
        raw.get("file_inputs"), "compile profile.file_inputs"
    )
    checklist_build = (
        _normalize_checklist_build(
            raw.get("checklist_build"),
            "compile profile.checklist_build",
            parameters,
            tools,
        )
        if raw.get("checklist_build") is not None
        else None
    )
    input_contract = _normalize_input_contract(
        raw.get("input_contract"),
        "compile profile.input_contract",
        parameters,
        support_level,
    )
    fixed_asset_contract = _normalize_input_contract(
        raw.get("fixed_asset_contract"),
        "compile profile.fixed_asset_contract",
        parameters,
        support_level,
    )
    make_recipe_inputs = _normalize_make_recipe_inputs(
        raw.get("make_recipe_inputs"),
        "compile profile.make_recipe_inputs",
        parameters,
        artifact_inputs,
    )
    normalized = {
        "schema_version": 1,
        "path": str(path),
        "id": profile_id,
        "type": "project_compile",
        "target": target,
        "component": component,
        "action": action,
        "source": {
            "id": source_id,
            "canonical_path": str(canonical),
            "case_path": case_relative.as_posix(),
            "ref_kind": ref_kind,
            "remote": text_value(
                source_raw.get("remote", "origin"), "compile profile.source.remote"
            ),
            "remote_url": text_value(
                source_raw.get("remote_url"), "compile profile.source.remote_url"
            ),
            "update": update,
        },
        "parameters": parameters,
        "configuration_parameters": configuration_parameters,
        "tools": tools,
        "watched_inputs": watched_inputs,
        "outputs": outputs,
        "artifact_inputs": artifact_inputs,
        "file_inputs": file_inputs,
        "checklist_build": checklist_build,
        "input_contract": input_contract,
        "fixed_asset_contract": fixed_asset_contract,
        "make_recipe_inputs": make_recipe_inputs,
    }
    normalized["hash"] = hash_data(
        {key: value for key, value in normalized.items() if key not in {"path", "hash"}}
    )
    return normalized


def _parse_parameter_overrides(
    values: list[str], profile: dict[str, Any]
) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise ToolError(f"--set must use NAME=VALUE: {raw!r}")
        name, value = raw.split("=", 1)
        if name not in profile["parameters"]:
            raise ToolError(f"--set references unknown profile parameter: {name}")
        if not value:
            raise ToolError(f"--set value must not be empty: {name}")
        result[name] = value
    return result


def render_project_manifest(
    profile: dict[str, Any],
    case_root: Path,
    *,
    ref: str | None = None,
    parameter_values: list[str] | None = None,
) -> tuple[Path, dict[str, Any]]:
    case_root = case_root.expanduser().resolve(strict=False)
    if not case_root.is_dir():
        raise ToolError(f"case root is not an existing directory: {case_root}")
    case = case_root.name
    overrides = _parse_parameter_overrides(parameter_values or [], profile)
    parameters: dict[str, dict[str, str]] = {}
    for parameter_id, definition in profile["parameters"].items():
        value = overrides.get(parameter_id)
        if value is None:
            value = definition.get("default", REQUIRED_PLACEHOLDER)
        parameters[parameter_id] = {
            "value": value,
            "source": definition["source"],
        }
    source = profile["source"]
    source_ref = ref or REQUIRED_PLACEHOLDER
    if source_ref.startswith("-") or not REF_RE.fullmatch(source_ref):
        raise ToolError(f"source ref contains unsafe characters: {source_ref!r}")
    case_source = (case_root / source["case_path"]).resolve(strict=False)
    require_within(case_source, case_root, "profile case source path")
    output_entries = {
        artifact_id: {
            **definition,
            "path": str((case_root / definition["path"]).resolve(strict=False)),
        }
        for artifact_id, definition in profile["outputs"].items()
    }
    for artifact_id, definition in output_entries.items():
        require_within(
            Path(definition["path"]), case_root, f"profile output {artifact_id}"
        )
    watched_inputs = [
        str((case_root / relative).resolve(strict=False))
        for relative in profile["watched_inputs"]
    ]
    component_id = profile["component"]
    source_id = source["id"]
    raw = {
        "schema_version": 2,
        "case": case,
        "case_root": str(case_root),
        "target": profile["target"],
        "project_profile": {
            "path": profile["path"],
            "hash": profile["hash"],
        },
        "parameters": parameters,
        "sources": {
            source_id: {
                "kind": "managed_git",
                "canonical_path": source["canonical_path"],
                "case_path": str(case_source),
                "ref_kind": source["ref_kind"],
                "ref": source_ref,
                "remote": source["remote"],
                "remote_url": source["remote_url"],
                "update": source["update"],
            }
        },
        "artifact_inputs": {},
        "file_inputs": {},
        "components": {
            component_id: {
                "sources": [source_id],
                "configuration": {"values": {}, "files": []},
                "tools": [
                    {
                        "name": tool["name"],
                        "executable": tool["executable"],
                        "version_args": tool["version_args"],
                    }
                    for tool in profile["tools"]
                ],
                "watched_inputs": watched_inputs,
                "outputs": [
                    definition["path"] for definition in output_entries.values()
                ],
                "depends_on": [],
            }
        },
        "exports": {
            artifact_id: {
                "component": component_id,
                "type": definition["type"],
                "path": definition["path"],
                "identity_parameters": definition["identity_parameters"],
            }
            for artifact_id, definition in output_entries.items()
        },
    }
    path = (
        case_root
        / "records"
        / "compile"
        / profile["target"]
        / "manifest.yaml"
    )
    return path, raw


def initialize_project_manifest(
    project: str,
    case_root: Path,
    *,
    ref: str | None = None,
    parameter_values: list[str] | None = None,
) -> Path:
    profile = load_compile_profile(project)
    path, raw = render_project_manifest(
        profile,
        case_root,
        ref=ref,
        parameter_values=parameter_values,
    )
    if path.exists():
        raise ToolError(f"compile manifest already exists: {path}")
    atomic_write_yaml(path, raw)
    return path


def normalize_project_profile_reference(
    raw_value: Any,
    *,
    target: str,
) -> dict[str, Any] | None:
    if raw_value is None:
        return None
    raw = mapping_value(raw_value, "manifest.project_profile")
    reject_unknown_keys(raw, {"path", "hash"}, "manifest.project_profile")
    path = resolve_absolute(raw.get("path"), "manifest.project_profile.path")
    profile = load_compile_profile(path)
    supplied_hash = text_value(raw.get("hash"), "manifest.project_profile.hash")
    if supplied_hash != profile["hash"]:
        raise ToolError(
            "project compile profile hash mismatch; regenerate the case manifest"
        )
    if profile["target"] != target:
        raise ToolError("project compile profile target does not match manifest target")
    return profile


def apply_project_profile_constraints(
    profile: dict[str, Any],
    *,
    case_root: Path,
    parameters: dict[str, dict[str, str]],
    sources: dict[str, dict[str, Any]],
    components: dict[str, dict[str, Any]],
    artifact_inputs: dict[str, dict[str, Any]],
    file_inputs: dict[str, dict[str, Any]],
    exports: dict[str, dict[str, Any]],
) -> None:
    missing_parameters = sorted(set(profile["parameters"]) - set(parameters))
    if missing_parameters:
        raise ToolError(
            "project manifest is missing profile parameters: "
            + ", ".join(missing_parameters)
        )
    extra_parameters = sorted(set(parameters) - set(profile["parameters"]))
    if extra_parameters:
        raise ToolError(
            "project manifest has parameters outside its compile profile: "
            + ", ".join(extra_parameters)
        )
    for parameter_id, definition in profile["parameters"].items():
        parameter = parameters[parameter_id]
        if parameter["source"] != definition["source"]:
            raise ToolError(
                f"project parameter {parameter_id} must use "
                f"source={definition['source']}"
            )
        normalized = " ".join(parameter["value"].lower().split())
        if definition["required"] and (
            normalized in UNRESOLVED_VALUES or parameter["value"] == REQUIRED_PLACEHOLDER
        ):
            raise ToolError(f"project parameter {parameter_id} must be resolved")
        if "allowed" in definition and parameter["value"] not in definition["allowed"]:
            raise ToolError(
                f"project parameter {parameter_id} must be one of: "
                + ", ".join(definition["allowed"])
            )
        if "pattern" in definition and re.fullmatch(
            definition["pattern"], parameter["value"]
        ) is None:
            raise ToolError(
                f"project parameter {parameter_id} does not match its required pattern"
            )
    if set(sources) != {profile["source"]["id"]}:
        raise ToolError("project manifest sources must match its compile profile")
    source = sources[profile["source"]["id"]]
    expected_source = profile["source"]
    for field in ("canonical_path", "ref_kind", "remote", "remote_url", "update"):
        if source[field] != expected_source[field]:
            raise ToolError(
                f"project manifest source {field} does not match its compile profile"
            )
    expected_case_source = (case_root / expected_source["case_path"]).resolve(strict=False)
    if Path(source["case_path"]) != expected_case_source:
        raise ToolError("project manifest source case_path does not match its profile")
    if source["ref"] == REQUIRED_PLACEHOLDER:
        raise ToolError("project manifest source ref must be resolved")
    if set(components) != {profile["component"]}:
        raise ToolError("project manifest component must match its compile profile")
    component = components[profile["component"]]
    if component["sources"] != [profile["source"]["id"]]:
        raise ToolError("project component sources do not match its compile profile")
    if component["depends_on"]:
        raise ToolError(
            "project component uses artifact_inputs for cross-project dependencies; "
            "depends_on must remain empty"
        )
    expected_watched_inputs = [
        str((case_root / relative).resolve(strict=False))
        for relative in profile["watched_inputs"]
    ] + [entry["path"] for entry in file_inputs.values()]
    if component["watched_inputs"] != expected_watched_inputs:
        raise ToolError(
            "project component watched_inputs do not match its compile profile"
        )
    if component["configuration"]["files"]:
        raise ToolError(
            "project component configuration files must be declared by the profile "
            "schema before use"
        )
    expected_tools = [
        {
            "name": tool["name"],
            "executable": tool["executable"],
            "version_args": tool["version_args"],
        }
        for tool in profile["tools"]
    ]
    actual_tools = [
        {
            "name": tool["name"],
            "executable": tool["executable"],
            "version_args": tool["version_args"],
        }
        for tool in component["toolchains"]
    ]
    if actual_tools != expected_tools:
        raise ToolError("project component tools do not match its compile profile")
    expected_outputs = {
        artifact_id: str((case_root / definition["path"]).resolve(strict=False))
        for artifact_id, definition in profile["outputs"].items()
    }
    if component["outputs"] != list(expected_outputs.values()):
        raise ToolError("project component outputs do not match its compile profile")
    if set(exports) != set(profile["outputs"]):
        raise ToolError("project manifest exports must match its compile profile")
    for artifact_id, definition in profile["outputs"].items():
        export = exports[artifact_id]
        if (
            export["component"] != profile["component"]
            or export["type"] != definition["type"]
            or export["path"] != expected_outputs[artifact_id]
            or export["identity_parameters"] != definition["identity_parameters"]
        ):
            raise ToolError(
                f"project export {artifact_id} does not match its compile profile"
            )
    selected_by_slot: dict[str, list[str]] = {}
    for input_id, artifact_input in artifact_inputs.items():
        slot = artifact_input["slot"]
        if slot not in profile["artifact_inputs"]:
            raise ToolError(f"project artifact input uses unknown slot: {slot}")
        selected_by_slot.setdefault(slot, []).append(input_id)
    for slot, selected in selected_by_slot.items():
        if len(selected) > 1 and not profile["artifact_inputs"][slot]["multiple"]:
            raise ToolError(f"project artifact input slot {slot} does not allow multiples")
    for slot, contract in profile["artifact_inputs"].items():
        condition = contract["required_when"]
        required = False
        if condition is not None:
            actual = parameters[condition["parameter"]]["value"]
            required = actual.casefold() == condition["equals"].casefold()
        if required and not selected_by_slot.get(slot):
            raise ToolError(
                f"project artifact input slot {slot} is required by current parameters"
            )
    selected_files: dict[str, list[str]] = {}
    for input_id, file_input in file_inputs.items():
        slot = file_input["slot"]
        if slot not in profile["file_inputs"]:
            raise ToolError(f"project file input uses unknown slot: {slot}")
        selected_files.setdefault(slot, []).append(input_id)
    for slot, selected in selected_files.items():
        if len(selected) > 1 and not profile["file_inputs"][slot]["multiple"]:
            raise ToolError(f"project file input slot {slot} does not allow multiples")
    values = component["configuration"]["values"]
    for input_id, file_input in file_inputs.items():
        prefix = f"compile_checklist.file_input.{input_id}"
        values[f"{prefix}.slot"] = file_input["slot"]
        values[f"{prefix}.path"] = file_input["path"]
        values[f"{prefix}.stage_to"] = file_input["stage_to"]
    for parameter_id in profile["configuration_parameters"]:
        parameter = parameters[parameter_id]
        prefix = f"compile_profile.parameter.{parameter_id}"
        values[f"{prefix}.value"] = parameter["value"]
        values[f"{prefix}.source"] = parameter["source"]
    allowed_prefixes = (
        "compile_profile.parameter.",
        "compile_tool_guard.",
        "compile_tool_policy.",
        "compile_checklist.file_input.",
        "compile_checklist.artifact_input.",
    )
    unexpected_configuration = sorted(
        key
        for key in component["configuration"]["values"]
        if not key.startswith(allowed_prefixes)
    )
    if unexpected_configuration:
        raise ToolError(
            "project component has configuration values outside its compile profile: "
            + ", ".join(unexpected_configuration)
        )
