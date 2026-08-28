from __future__ import annotations

from pathlib import Path
import re
import shlex
from typing import Any

from .artifacts import resolve_artifact_inputs, semantic_artifact_inputs
from .common import (
    REF_RE,
    ToolError,
    atomic_write_yaml,
    case_lock,
    hash_data,
    load_yaml,
    mapping_value,
    reject_unknown_keys,
    require_within,
    text_value,
)
from .composition import (
    validate_fixed_asset_contract,
    validate_input_contract,
    validate_make_recipe_m_payloads,
)
from .fingerprints import file_snapshots, toolchain_snapshots
from .guards import SAFE_ID_RE, UNRESOLVED_VALUES
from .manifest import load_manifest
from .planner import assess
from .profiles import PROJECTS_ROOT, load_compile_profile, render_project_manifest
from .request import execute_v2, load_request, render_report
from .sources import execute_acquisition, render_acquisition
from .state import load_state, write_state


CHECKLIST_KIND = "project_compile_checklist"
TEMPLATE_NAME = "COMPILE_CHECKLIST.yaml"
PREPARED_NAME = ".compile-tool-prepared.yaml"
EXPRESSION_RE = re.compile(
    r"\$\{(parameters|tools|tool_prefix)\.([A-Za-z0-9][A-Za-z0-9._-]*)\}"
)


def is_checklist(path: Path) -> bool:
    value = load_yaml(path, "compile input")
    return isinstance(value, dict) and value.get("kind") == CHECKLIST_KIND


def _scalar(value: Any, label: str) -> str:
    if not isinstance(value, (str, int, float, bool)):
        raise ToolError(f"{label} must be a scalar")
    result = str(value).strip()
    if not result:
        raise ToolError(f"{label} must not be empty")
    normalized = " ".join(result.casefold().split())
    if normalized in UNRESOLVED_VALUES or normalized == "tbd":
        raise ToolError(f"{label} must be resolved")
    return result


def _safe_relative(value: Any, label: str) -> str:
    path = Path(text_value(value, label))
    if path.is_absolute() or not path.parts or any(
        part in {"", ".", "..", ".git"} for part in path.parts
    ):
        raise ToolError(f"{label} must be a safe relative path")
    return path.as_posix()


def _case_path(value: Any, label: str, case_root: Path) -> Path:
    raw = Path(text_value(value, label)).expanduser()
    path = raw.resolve(strict=False) if raw.is_absolute() else (case_root / raw).resolve(strict=False)
    require_within(path, case_root, label)
    return path


def _template(project: str) -> dict[str, Any]:
    path = PROJECTS_ROOT / project / TEMPLATE_NAME
    return mapping_value(load_yaml(path, "project compile checklist template"), "project compile checklist template")


def _normalize_parameters(
    raw_value: Any,
    template: dict[str, Any],
) -> dict[str, str]:
    raw = mapping_value(raw_value, "checklist.parameters")
    expected = mapping_value(template.get("parameters"), "template.parameters")
    if set(raw) != set(expected):
        raise ToolError("checklist.parameters keys must exactly match the project template")
    result = {
        key: _scalar(value, f"checklist.parameters.{key}")
        for key, value in raw.items()
    }
    for key, template_value in expected.items():
        if str(template_value).casefold() != "tbd" and result[key] != str(template_value):
            raise ToolError(f"checklist.parameters.{key} is fixed by the project template")
    return result


def _normalize_file_entry(
    raw_value: Any,
    label: str,
    case_root: Path,
) -> dict[str, str]:
    raw = mapping_value(raw_value, label)
    reject_unknown_keys(raw, {"name", "slot", "path", "stage_to"}, label)
    name = text_value(raw.get("name"), f"{label}.name")
    if not SAFE_ID_RE.fullmatch(name):
        raise ToolError(f"{label}.name contains unsafe characters")
    slot = text_value(raw.get("slot"), f"{label}.slot")
    if not SAFE_ID_RE.fullmatch(slot):
        raise ToolError(f"{label}.slot contains unsafe characters")
    path = _case_path(raw.get("path"), f"{label}.path", case_root)
    if not path.is_file():
        raise ToolError(f"{label}.path is not an existing file: {path}")
    return {
        "name": name,
        "slot": slot,
        "path": str(path),
        "stage_to": _safe_relative(raw.get("stage_to"), f"{label}.stage_to"),
    }


def _normalize_artifact_entry(
    raw_value: Any,
    label: str,
    case_root: Path,
) -> dict[str, str]:
    raw = mapping_value(raw_value, label)
    reject_unknown_keys(
        raw,
        {"name", "slot", "checklist", "artifact", "stage_to"},
        label,
    )
    name = text_value(raw.get("name"), f"{label}.name")
    slot = text_value(raw.get("slot"), f"{label}.slot")
    artifact = text_value(raw.get("artifact"), f"{label}.artifact")
    for value, field in ((name, "name"), (slot, "slot"), (artifact, "artifact")):
        if not SAFE_ID_RE.fullmatch(value):
            raise ToolError(f"{label}.{field} contains unsafe characters")
    checklist = _case_path(raw.get("checklist"), f"{label}.checklist", case_root)
    if not checklist.is_file():
        raise ToolError(f"{label}.checklist is not an existing file: {checklist}")
    return {
        "name": name,
        "slot": slot,
        "checklist": str(checklist),
        "artifact": artifact,
        "stage_to": _safe_relative(raw.get("stage_to"), f"{label}.stage_to"),
    }


def _normalize_inputs(
    raw_value: Any,
    case_root: Path,
    profile: dict[str, Any],
) -> dict[str, Any]:
    raw = mapping_value(raw_value, "checklist.inputs")
    reject_unknown_keys(raw, {"artifacts", "files"}, "checklist.inputs")
    artifacts_raw = raw.get("artifacts") or []
    files_raw = raw.get("files") or []
    if not isinstance(artifacts_raw, list) or not isinstance(files_raw, list):
        raise ToolError("checklist artifact inputs and file inputs must be lists")
    artifacts = [
        _normalize_artifact_entry(
            value, f"checklist.inputs.artifacts[{index}]", case_root
        )
        for index, value in enumerate(artifacts_raw, start=1)
    ]
    files = [
        _normalize_file_entry(value, f"checklist.inputs.files[{index}]", case_root)
        for index, value in enumerate(files_raw, start=1)
    ]
    names = [entry["name"] for entry in [*artifacts, *files]]
    if len(names) != len(set(names)):
        raise ToolError("checklist input names must be unique")
    destinations = [entry["stage_to"] for entry in [*artifacts, *files]]
    if len(destinations) != len(set(destinations)):
        raise ToolError("checklist input stage_to paths must be unique")
    unknown_artifact_slots = sorted(
        {entry["slot"] for entry in artifacts} - set(profile["artifact_inputs"])
    )
    if unknown_artifact_slots:
        raise ToolError(
            "checklist artifact inputs use unknown slots: "
            + ", ".join(unknown_artifact_slots)
        )
    unknown_file_slots = sorted(
        {entry["slot"] for entry in files} - set(profile["file_inputs"])
    )
    if unknown_file_slots:
        raise ToolError(
            "checklist file inputs use unknown slots: "
            + ", ".join(unknown_file_slots)
        )
    return {"artifacts": artifacts, "files": files}


def normalize_checklist(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve(strict=False)
    raw = mapping_value(load_yaml(path, "project compile checklist"), "project compile checklist")
    reject_unknown_keys(
        raw,
        {
            "schema_version",
            "kind",
            "project",
            "case_root",
            "source",
            "parameters",
            "inputs",
            "toolchain",
            "intent",
            "build",
            "outputs",
        },
        "checklist",
    )
    if raw.get("schema_version") != 1 or raw.get("kind") != CHECKLIST_KIND:
        raise ToolError("project compile checklist identity is invalid")
    project = text_value(raw.get("project"), "checklist.project")
    template = _template(project)
    profile = load_compile_profile(project)
    if profile["checklist_build"] is None:
        raise ToolError(f"project compile profile has no checklist build contract: {project}")
    expected_toolchain = {
        tool["name"]: tool["path"] for tool in profile["tools"]
    }
    if template.get("toolchain") != expected_toolchain:
        raise ToolError("project checklist toolchain does not match its profile")
    for field in (
        "schema_version",
        "kind",
        "project",
        "toolchain",
        "build",
        "outputs",
    ):
        if raw.get(field) != template.get(field):
            raise ToolError(f"checklist.{field} must exactly match the project template")
    if template["build"].get("mode") != profile["checklist_build"]["mode"]:
        raise ToolError("project checklist build mode does not match its profile")
    case_root = Path(text_value(raw.get("case_root"), "checklist.case_root")).expanduser().resolve(strict=False)
    if not case_root.is_dir() or case_root.name in {"", ".", ".."}:
        raise ToolError(f"checklist.case_root is not an existing case directory: {case_root}")
    expected_path = case_root / "records" / "compile" / project / "compile.yaml"
    if path != expected_path.resolve(strict=False):
        raise ToolError(f"project compile checklist must be stored at {expected_path}")
    source = mapping_value(raw.get("source"), "checklist.source")
    reject_unknown_keys(source, {"ref"}, "checklist.source")
    ref = text_value(source.get("ref"), "checklist.source.ref")
    if not REF_RE.fullmatch(ref) or ref.casefold() == "tbd":
        raise ToolError("checklist.source.ref must be an explicit safe ref")
    parameters = _normalize_parameters(raw.get("parameters"), template)
    intent = mapping_value(raw.get("intent"), "checklist.intent")
    reject_unknown_keys(intent, {"action", "reason"}, "checklist.intent")
    action = text_value(intent.get("action"), "checklist.intent.action")
    expected_action = profile["action"]
    if action not in {expected_action, "reuse"}:
        raise ToolError(
            f"checklist.intent.action must be {expected_action} or reuse"
        )
    reason = text_value(intent.get("reason"), "checklist.intent.reason")
    if reason.casefold() == "tbd":
        raise ToolError("checklist.intent.reason must be resolved")
    inputs = _normalize_inputs(raw.get("inputs"), case_root, profile)
    make_recipe_contract = profile.get("make_recipe_inputs")
    validate_input_contract(
        profile["input_contract"],
        parameters,
        inputs,
        dynamic_artifact_slots=(
            {make_recipe_contract["m_payload_slot"]}
            if make_recipe_contract is not None
            else set()
        ),
    )
    make_recipe = validate_make_recipe_m_payloads(
        make_recipe_contract,
        source_root=Path(profile["source"]["canonical_path"]),
        source_ref=ref,
        parameters=parameters,
        inputs=inputs,
    )
    validate_fixed_asset_contract(
        profile["fixed_asset_contract"], parameters, inputs
    )
    return {
        "path": str(path),
        "hash": hash_data(raw),
        "raw": raw,
        "project": project,
        "case_root": str(case_root),
        "case": case_root.name,
        "source_ref": ref,
        "parameters": parameters,
        "intent": {"action": action, "reason": reason},
        "build": profile["checklist_build"],
        "inputs": inputs,
        "outputs": raw["outputs"],
        "profile": profile,
        "make_recipe": make_recipe,
    }


def _expand_path(expression: str, parameters: dict[str, str], label: str) -> str:
    result = expression
    for name, value in parameters.items():
        result = result.replace(f"${{parameters.{name}}}", value)
    if "${" in result:
        raise ToolError(f"{label} has an unresolved template expression: {result}")
    return _safe_relative(result, label)


def _write_generated_manifest(path: Path, raw: dict[str, Any], checklist: dict[str, Any]) -> None:
    if path.exists():
        existing = mapping_value(load_yaml(path, "generated compile manifest"), "generated compile manifest")
        marker = existing.get("project_checklist")
        if not isinstance(marker, dict) or marker.get("path") != checklist["path"]:
            raise ToolError(
                f"refusing to overwrite a manifest not owned by this checklist: {path}"
            )
    atomic_write_yaml(path, raw)


def materialize_checklist_manifest(
    checklist: dict[str, Any],
    *,
    stack: set[str] | None = None,
) -> dict[str, Any]:
    stack = set(stack or set())
    if checklist["path"] in stack:
        raise ToolError("project checklist dependency cycle detected")
    stack.add(checklist["path"])
    profile = checklist["profile"]
    manifest_path, raw = render_project_manifest(
        profile,
        Path(checklist["case_root"]),
        ref=checklist["source_ref"],
        parameter_values=[
            f"{name}={value}" for name, value in checklist["parameters"].items()
        ],
    )
    raw["project_checklist"] = {
        "path": checklist["path"],
        "hash": checklist["hash"],
    }
    file_inputs: dict[str, dict[str, str]] = {}
    for entry in checklist["inputs"]["files"]:
        file_inputs[entry["name"]] = {
            "slot": entry["slot"],
            "path": entry["path"],
            "stage_to": entry["stage_to"],
        }
    raw["file_inputs"] = file_inputs
    raw["components"][checklist["project"]]["watched_inputs"] = [
        entry["path"] for entry in file_inputs.values()
    ]
    artifact_inputs: dict[str, dict[str, str]] = {}
    for entry in checklist["inputs"]["artifacts"]:
        from .public_checklists import (
            materialize_public_manifest,
            normalize_public_checklist,
        )

        producer = normalize_public_checklist(Path(entry["checklist"]))
        if producer["case_root"] != checklist["case_root"]:
            raise ToolError("artifact producer checklist must belong to the same case")
        producer_target = producer.get("project") or producer.get("target")
        if producer_target == checklist["project"]:
            raise ToolError("project checklist cannot consume its own artifact")
        producer_manifest = materialize_public_manifest(producer, stack=stack)
        artifact_inputs[entry["name"]] = {
            "slot": entry["slot"],
            "manifest": producer_manifest["path"],
            "artifact": entry["artifact"],
        }
        raw["components"][checklist["project"]]["configuration"]["values"][
            f"compile_checklist.artifact_input.{entry['name']}.stage_to"
        ] = entry["stage_to"]
    raw["artifact_inputs"] = artifact_inputs
    if checklist.get("make_recipe") is not None:
        recipe = checklist["make_recipe"]
        configuration = raw["components"][checklist["project"]]["configuration"]["values"]
        configuration["compile_checklist.make_recipe.source"] = recipe["source"]
        configuration["compile_checklist.make_recipe.source_hash"] = recipe["source_hash"]
        configuration["compile_checklist.make_recipe.required_m_payloads"] = ",".join(
            recipe["required_m_payloads"]
        )
    _write_generated_manifest(manifest_path, raw, checklist)
    return load_manifest(manifest_path)


def _install_command(source: Path, destination: Path) -> str:
    return "/usr/bin/install -D -m 0644 " + shlex.quote(str(source)) + " " + shlex.quote(str(destination))


def _render_expression(
    expression: str,
    checklist: dict[str, Any],
    component: dict[str, Any],
    label: str,
) -> str:
    tools = {
        tool["name"]: tool["executable"] for tool in component["toolchains"]
    }

    def replace(match: re.Match[str]) -> str:
        kind, name = match.groups()
        if kind == "parameters":
            if name not in checklist["parameters"]:
                raise ToolError(f"{label} references unknown parameter: {name}")
            return checklist["parameters"][name]
        if name not in tools:
            raise ToolError(f"{label} references unknown tool: {name}")
        executable = tools[name]
        if kind == "tools":
            return executable
        if not executable.endswith("gcc"):
            raise ToolError(f"{label} requests a compiler prefix from a non-gcc tool")
        return executable[:-3]

    rendered = EXPRESSION_RE.sub(replace, expression)
    if "${" in rendered:
        raise ToolError(f"{label} has an unresolved checklist expression")
    return rendered


def _profile_build_steps(
    checklist: dict[str, Any],
    component: dict[str, Any],
    workspace: Path,
) -> list[dict[str, Any]]:
    definition = checklist["build"]
    env = {
        name: _render_expression(
            value, checklist, component, f"checklist build env {name}"
        )
        for name, value in definition["env"].items()
    }
    result: list[dict[str, Any]] = []
    for step in definition["steps"]:
        tokens: list[str] = []
        for index, token in enumerate(step["command"], start=1):
            condition = token["omit_when"]
            if condition is not None and checklist["parameters"][
                condition["parameter"]
            ].casefold() == condition["equals"].casefold():
                continue
            tokens.append(
                _render_expression(
                    token["value"],
                    checklist,
                    component,
                    f"checklist build step {step['name']} token {index}",
                )
            )
        if not tokens:
            raise ToolError(f"checklist build step {step['name']} rendered empty")
        result.append(
            {
                "name": step["name"],
                "cwd": str(workspace),
                "env": env,
                "command": shlex.join(tokens),
            }
        )
    return result


def _build_steps(checklist: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    component = manifest["components"][checklist["project"]]
    execution = component.get("execution")
    if not isinstance(execution, dict):
        raise ToolError("checklist project requires an isolated_git execution policy")
    workspace = Path(execution["workspace"])
    steps: list[dict[str, Any]] = []
    artifact_snapshots = resolve_artifact_inputs(manifest)
    for entry in checklist["inputs"]["artifacts"]:
        snapshot = artifact_snapshots[entry["name"]]
        destination = (workspace / entry["stage_to"]).resolve(strict=False)
        require_within(destination, workspace, f"artifact {entry['name']} stage_to")
        steps.append(
            {
                "name": f"stage-{entry['name']}",
                "cwd": str(workspace),
                "env": {},
                "command": _install_command(Path(snapshot["path"]), destination),
            }
        )
    for entry in checklist["inputs"]["files"]:
        destination = (workspace / entry["stage_to"]).resolve(strict=False)
        require_within(destination, workspace, f"file input {entry['name']} stage_to")
        steps.append(
            {
                "name": f"stage-{entry['name']}",
                "cwd": str(workspace),
                "env": {},
                "command": _install_command(Path(entry["path"]), destination),
            }
        )
    steps.extend(_profile_build_steps(checklist, component, workspace))
    for artifact_id, definition in checklist["outputs"].items():
        relative = _expand_path(
            definition["collect_from"],
            checklist["parameters"],
            f"checklist.outputs.{artifact_id}.collect_from",
        )
        source = (workspace / relative).resolve(strict=False)
        require_within(source, workspace, f"output {artifact_id} collect_from")
        destination = Path(manifest["exports"][artifact_id]["path"])
        steps.append(
            {
                "name": f"publish-{artifact_id}",
                "cwd": str(workspace),
                "env": {},
                "command": _install_command(source, destination),
            }
        )
    return steps


def _request_for(
    checklist: dict[str, Any],
    manifest: dict[str, Any],
    assessment_hash: str,
) -> dict[str, Any]:
    request_path = Path(checklist["path"]).parent / ".compile-tool-request.yaml"
    raw = {
        "schema_version": 2,
        "case": checklist["case"],
        "assessment": {"manifest": manifest["path"], "hash": assessment_hash},
        "decision": {
            "scope": [checklist["project"]],
            "reason": checklist["intent"]["reason"],
            "destructive": {},
        },
        "compile": {
            "target": checklist["project"],
            "units": [
                {
                    "component": checklist["project"],
                    "action": manifest["project_profile"]["action"],
                    "steps": _build_steps(checklist, manifest),
                }
            ],
        },
    }
    atomic_write_yaml(request_path, raw)
    return load_request(request_path, allow_project_checklist_request=True)


def _external_identity(manifest: dict[str, Any]) -> str:
    return hash_data(
        {
            "file_inputs": file_snapshots(
                [entry["path"] for entry in manifest.get("file_inputs", {}).values()],
                None,
                require_nonempty=True,
            )
            if manifest.get("file_inputs")
            else [],
            "artifact_inputs": semantic_artifact_inputs(resolve_artifact_inputs(manifest)),
            "tools": toolchain_snapshots(
                manifest["components"][manifest["target"]]["toolchains"]
            ),
        }
    )


def _prepared_path(checklist: dict[str, Any]) -> Path:
    return Path(checklist["path"]).parent / PREPARED_NAME


def _render_checklist_plan(
    checklist: dict[str, Any],
    manifest: dict[str, Any],
    assessment: dict[str, Any],
    request: dict[str, Any],
) -> str:
    lines = [
        "[单清单编译计划]",
        "",
        f"Case：{checklist['case']}",
        f"项目：{checklist['project']}",
        f"清单：{checklist['path']}",
        "",
        "清单参数：",
    ]
    for name, value in checklist["parameters"].items():
        lines.append(f"- {name}：{value}")
    if checklist.get("make_recipe") is not None:
        recipe = checklist["make_recipe"]
        payloads = ", ".join(recipe["required_m_payloads"].values()) or "无"
        lines.extend(
            [
                "",
                f"Recipe 事实源：{recipe['source']}",
                f"M payload：{payloads}",
            ]
        )
    lines.extend(
        [
            "",
            f"本轮意图：{checklist['intent']['action'].upper()}",
            f"理由：{checklist['intent']['reason']}",
        ]
    )
    if assessment["status"] == "ACQUIRE_REQUIRED":
        lines.extend(["", render_acquisition(manifest, assessment["source"])])
        state_summary = "PENDING_SOURCE_ACQUISITION"
    else:
        state_summary = assessment["state_summary"]
    lines.extend(["", f"软件状态：{state_summary}", "", "受控执行步骤："])
    steps = request["compile"]["units"][0]["steps"]
    for index, step in enumerate(steps, start=1):
        lines.append(f"{index}. {step['name']}")
        lines.append(f"   工作目录：{step['cwd']}")
        if step["env"]:
            env = " ".join(f"{key}={shlex.quote(value)}" for key, value in step["env"].items())
            lines.append(f"   环境变量：{env}")
        else:
            lines.append("   环境变量：无")
        lines.append(f"   $ {step['command']}")
    lines.extend(["", "Decision：READY_FOR_RUN"])
    return "\n".join(lines)


def _prepare_normalized_checklist(checklist: dict[str, Any]) -> int:
    manifest = materialize_checklist_manifest(checklist)
    assessment = assess(manifest)
    external_identity = _external_identity(manifest)
    if (
        assessment["status"] == "READY"
        and checklist["intent"]["action"] == "reuse"
        and assessment["state_summary"] != "MATCHED"
    ):
        raise ToolError("checklist requests reuse but observed software state has changes")
    request = _request_for(
        checklist,
        manifest,
        assessment.get("assessment_hash") or "sha256:" + "0" * 64,
    )
    prepared = {
        "schema_version": 1,
        "generated_by": "compile-tool checklist prepare",
        "checklist": checklist["path"],
        "checklist_hash": checklist["hash"],
        "manifest_hash": manifest["hash"],
        "external_identity": external_identity,
        "acquisition_plan_hash": (
            assessment["source"]["plan_hash"]
            if assessment["status"] == "ACQUIRE_REQUIRED"
            else None
        ),
        "assessment_hash": assessment.get("assessment_hash"),
    }
    atomic_write_yaml(_prepared_path(checklist), prepared)
    print(_render_checklist_plan(checklist, manifest, assessment, request))
    return 0


def prepare_checklist(path: Path) -> int:
    checklist = normalize_checklist(path)
    with case_lock(Path(checklist["case_root"])):
        return _prepare_normalized_checklist(checklist)


def _run_normalized_checklist(checklist: dict[str, Any]) -> int:
    prepared = mapping_value(
        load_yaml(_prepared_path(checklist), "prepared checklist record"),
        "prepared checklist record",
    )
    manifest = materialize_checklist_manifest(checklist)
    if (
        prepared.get("checklist") != checklist["path"]
        or prepared.get("checklist_hash") != checklist["hash"]
        or prepared.get("manifest_hash") != manifest["hash"]
    ):
        raise ToolError("checklist changed after prepare; run prepare again")
    if prepared.get("external_identity") != _external_identity(manifest):
        raise ToolError("checklist tools or inputs changed after prepare; run prepare again")
    assessment = assess(manifest)
    if assessment["status"] == "ACQUIRE_REQUIRED":
        if prepared.get("acquisition_plan_hash") != assessment["source"]["plan_hash"]:
            raise ToolError("source acquisition plan changed after prepare; run prepare again")
        result = execute_acquisition(manifest, assessment["source"]["plan_hash"])
        if result != 0:
            return result
        assessment = assess(manifest)
    elif prepared.get("assessment_hash") != assessment.get("assessment_hash"):
        raise ToolError("software state changed after prepare; run prepare again")
    if assessment["status"] != "READY":
        raise ToolError("project checklist source is not ready after acquisition")
    if checklist["intent"]["action"] == "reuse":
        if assessment["state_summary"] != "MATCHED":
            raise ToolError("checklist requests reuse but observed software state has changes")
        state = load_state(manifest)
        write_state(manifest, state)
        print("compile-tool: checklist state matched; reused successful project output")
        return 0
    request = _request_for(checklist, manifest, assessment["assessment_hash"])
    print(render_report(request, assessment), flush=True)
    print("\nExecution：STARTING", flush=True)
    return execute_v2(request, assessment)


def run_checklist(path: Path) -> int:
    checklist = normalize_checklist(path)
    with case_lock(Path(checklist["case_root"])):
        return _run_normalized_checklist(checklist)
