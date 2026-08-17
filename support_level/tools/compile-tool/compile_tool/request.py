from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any

from .common import (
    ENV_NAME_RE,
    ToolError,
    is_within,
    load_yaml,
    mapping_value,
    normalize_hash,
    reject_unknown_keys,
    require_within,
    resolve_absolute,
    text_value,
)
from .commands import validate_compile_commands
from .execution import (
    component_execution,
    materialize_component_workspace,
    validate_component_workdirs,
)
from .guards import normalize_parameters, validate_guard_commands
from .manifest import load_manifest, topological_order
from .planner import record_successful_unit


def _normalize_step(
    raw_value: Any,
    label: str,
    *,
    case_root: Path | None,
    allow_missing_within: Path | None = None,
) -> dict[str, Any]:
    step = mapping_value(raw_value, label)
    reject_unknown_keys(step, {"name", "cwd", "env", "command"}, label)
    name = text_value(step.get("name"), f"{label}.name")
    cwd = resolve_absolute(step.get("cwd"), f"{label}.cwd")
    missing_allowed = (
        allow_missing_within is not None
        and is_within(cwd, allow_missing_within)
    )
    if not cwd.is_dir() and not missing_allowed:
        raise ToolError(f"{label}.cwd is not an existing directory: {cwd}")
    if case_root is not None:
        require_within(cwd, case_root, f"{label}.cwd")
    env_raw = mapping_value(step.get("env") or {}, f"{label}.env")
    env: dict[str, str] = {}
    for key, value in env_raw.items():
        if not isinstance(key, str) or not ENV_NAME_RE.fullmatch(key):
            raise ToolError(f"{label}.env has invalid variable name: {key!r}")
        if not isinstance(value, (str, int, float)):
            raise ToolError(f"{label}.env.{key} must be a string or number")
        env[key] = str(value)
    return {
        "name": name,
        "cwd": str(cwd.resolve()),
        "env": env,
        "command": text_value(step.get("command"), f"{label}.command"),
    }
def _normalize_v1(root: dict[str, Any]) -> dict[str, Any]:
    reject_unknown_keys(
        root,
        {
            "schema_version",
            "case",
            "parameters",
            "compile",
        },
        "request",
    )
    case = text_value(root.get("case"), "case")
    parameters = normalize_parameters(root.get("parameters"), "parameters")
    compile_raw = mapping_value(root.get("compile"), "compile")
    reject_unknown_keys(compile_raw, {"target", "steps"}, "compile")
    target = text_value(compile_raw.get("target"), "compile.target")
    if target == "flashbin":
        raise ToolError(
            "flashbin requests require schema_version 2 and a bound software assessment"
        )
    steps_raw = compile_raw.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ToolError("compile.steps must be a non-empty list")
    steps = [
        _normalize_step(step, f"compile.steps[{index}]", case_root=None)
        for index, step in enumerate(steps_raw, start=1)
    ]
    return {
        "schema_version": 1,
        "case": case,
        "parameters": parameters,
        "compile": {"target": target, "steps": steps},
    }


def _normalize_v2(root: dict[str, Any]) -> dict[str, Any]:
    reject_unknown_keys(
        root,
        {
            "schema_version",
            "case",
            "assessment",
            "decision",
            "compile",
        },
        "request",
    )
    case = text_value(root.get("case"), "case")
    assessment_raw = mapping_value(root.get("assessment"), "assessment")
    reject_unknown_keys(assessment_raw, {"manifest", "hash"}, "assessment")
    manifest_path = resolve_absolute(
        assessment_raw.get("manifest"), "assessment.manifest"
    )
    manifest = load_manifest(manifest_path)
    if manifest["case"] != case:
        raise ToolError("request case does not match the compile manifest")
    assessment_hash = normalize_hash(
        text_value(assessment_raw.get("hash"), "assessment.hash"),
        "assessment.hash",
    )
    decision_raw = mapping_value(root.get("decision"), "decision")
    reject_unknown_keys(
        decision_raw,
        {"scope", "reason", "destructive"},
        "decision",
    )
    scope_raw = decision_raw.get("scope")
    if not isinstance(scope_raw, list) or not scope_raw:
        raise ToolError("decision.scope must be a non-empty component list")
    scope: list[str] = []
    for index, value in enumerate(scope_raw, start=1):
        component = text_value(value, f"decision.scope[{index}]")
        if component.casefold() == "all" or component == "*":
            raise ToolError("decision.scope must list explicit components, not all or *")
        scope.append(component)
    if len(scope) != len(set(scope)):
        raise ToolError("decision.scope contains duplicate components")
    reason = text_value(decision_raw.get("reason"), "decision.reason")
    destructive_raw = mapping_value(
        decision_raw.get("destructive") or {},
        "decision.destructive",
    )
    destructive: dict[str, str] = {}
    for component, value in destructive_raw.items():
        if not isinstance(component, str) or not component:
            raise ToolError("decision.destructive keys must be component names")
        destructive[component] = text_value(
            value,
            f"decision.destructive.{component}",
        )
    compile_raw = mapping_value(root.get("compile"), "compile")
    reject_unknown_keys(compile_raw, {"target", "units"}, "compile")
    target = text_value(compile_raw.get("target"), "compile.target")
    if target != manifest["target"]:
        raise ToolError("request target does not match the compile manifest")
    units_raw = compile_raw.get("units")
    if not isinstance(units_raw, list) or not units_raw:
        raise ToolError("compile.units must be a non-empty list")
    units: list[dict[str, Any]] = []
    seen: set[str] = set()
    case_root = Path(manifest["case_root"])
    for index, raw_unit in enumerate(units_raw, start=1):
        label = f"compile.units[{index}]"
        unit = mapping_value(raw_unit, label)
        reject_unknown_keys(unit, {"component", "action", "steps"}, label)
        component = text_value(unit.get("component"), f"{label}.component")
        if component in seen:
            raise ToolError(f"compile.units has duplicate component: {component}")
        seen.add(component)
        action = text_value(unit.get("action"), f"{label}.action")
        if action not in {"rebuild", "repack"}:
            raise ToolError(f"{label}.action must be rebuild or repack")
        if manifest.get("generic") and action != "rebuild":
            raise ToolError(f"{label}.action must be rebuild for a generic target")
        steps_raw = unit.get("steps")
        if not isinstance(steps_raw, list) or not steps_raw:
            raise ToolError(f"{label}.steps must be a non-empty list")
        execution = (
            component_execution(manifest, component)
            if component in manifest["components"]
            else None
        )
        allow_missing_within = (
            Path(execution["workspace"]) if execution is not None else None
        )
        steps = [
            _normalize_step(
                step,
                f"{label}.steps[{step_index}]",
                case_root=case_root,
                allow_missing_within=allow_missing_within,
            )
            for step_index, step in enumerate(steps_raw, start=1)
        ]
        if component in manifest["components"]:
            validate_component_workdirs(manifest, component, steps)
        units.append(
            {
                "component": component,
                "action": action,
                "steps": steps,
            }
        )
    decision = {
        "scope": scope,
        "reason": reason,
        "destructive": destructive,
    }
    _validate_execution_scope(manifest, decision, units)
    validate_guard_commands(units, manifest["parameters"], manifest["guards"])
    validate_compile_commands(units, decision, manifest)
    return {
        "schema_version": 2,
        "case": case,
        "parameters": manifest["parameters"],
        "assessment": {
            "manifest": str(manifest_path),
            "hash": assessment_hash,
        },
        "decision": decision,
        "compile": {"target": target, "units": units},
        "_manifest": manifest,
    }


def normalize_request(data: Any) -> dict[str, Any]:
    root = mapping_value(data, "request")
    version = root.get("schema_version")
    if version == 1:
        return _normalize_v1(root)
    if version == 2:
        return _normalize_v2(root)
    raise ToolError(f"schema_version must be 1 or 2, got {version!r}")


def load_request(path: Path) -> dict[str, Any]:
    return normalize_request(load_yaml(path, "compile request"))


def _manifest_order(manifest: dict[str, Any]) -> list[str]:
    if manifest.get("generic"):
        return manifest["component_order"]
    enabled = {
        component_id
        for component_id, component in manifest["components"].items()
        if component["status"] == "enabled"
    }
    return topological_order(manifest["profile"], enabled)


def _downstream_closure(
    manifest: dict[str, Any],
    scope: set[str],
) -> set[str]:
    allowed = set(scope)
    changed = True
    while changed:
        changed = False
        for component_id, item in manifest["profile"]["components"].items():
            if component_id in allowed:
                continue
            if any(dependency in allowed for dependency in item["depends_on"]):
                allowed.add(component_id)
                changed = True
    return allowed


def _validate_execution_scope(
    manifest: dict[str, Any],
    decision: dict[str, Any],
    units: list[dict[str, Any]],
) -> None:
    enabled = {
        component_id
        for component_id, component in manifest["components"].items()
        if component["status"] == "enabled"
    }
    scope = set(decision["scope"])
    unknown = sorted(scope - enabled)
    if unknown:
        raise ToolError(
            "decision.scope has unavailable components: " + ", ".join(unknown)
        )
    requested = [unit["component"] for unit in units]
    requested_set = set(requested)
    unknown_units = sorted(requested_set - enabled)
    if unknown_units:
        raise ToolError(
            "compile.units has unavailable components: " + ", ".join(unknown_units)
        )
    allowed = _downstream_closure(manifest, scope)
    unrelated = sorted(requested_set - allowed)
    if unrelated:
        raise ToolError(
            "compile units exceed the declared decision scope: "
            + ", ".join(unrelated)
        )

    executable_scope = {
        component_id
        for component_id in scope
        if manifest["components"][component_id]["kind"] != "fixed_input"
    }
    missing_scope = sorted(executable_scope - requested_set)
    if missing_scope:
        raise ToolError(
            "compile units omit executable decision scope components: "
            + ", ".join(missing_scope)
        )

    order = _manifest_order(manifest)
    expected_order = [
        component_id for component_id in order if component_id in requested_set
    ]
    if requested != expected_order:
        raise ToolError(
            "compile units must follow manifest dependency order: "
            + ", ".join(expected_order)
        )

    for unit in units:
        kind = manifest["components"][unit["component"]]["kind"]
        expected_action = "repack" if kind == "package" else "rebuild"
        if kind == "fixed_input":
            raise ToolError(
                f"fixed input cannot be an executable unit: {unit['component']}"
            )
        if unit["action"] != expected_action:
            raise ToolError(
                f"{unit['component']} action must be {expected_action}"
            )

    if (
        manifest["target"] == "flashbin"
        and any(component != "flashbin" for component in scope)
        and "flashbin" not in requested_set
    ):
        raise ToolError(
            "flashbin upstream decision scope requires a final flashbin repack unit"
        )
    unused_destructive = sorted(set(decision["destructive"]) - requested_set)
    if unused_destructive:
        raise ToolError(
            "decision.destructive references components outside compile.units: "
            + ", ".join(unused_destructive)
        )


def verify_assessment(request: dict[str, Any], assessment: dict[str, Any]) -> None:
    if assessment["status"] == "ACQUIRE_REQUIRED":
        raise ToolError("source acquisition is required before compile prepare")
    if request["assessment"]["hash"] != assessment["assessment_hash"]:
        raise ToolError("assessment hash mismatch; run assess and rebuild the request")


def _report_header(request: dict[str, Any]) -> list[str]:
    lines = [
        "[编译前置声明]",
        "",
        f"Case：{request['case']}",
        f"编译对象：{request['compile']['target']}",
        "",
        "显式构建参数：",
    ]
    if request["parameters"]:
        for parameter, value in request["parameters"].items():
            lines.append(
                f"- {parameter}：{value['value']}（source={value['source']}）"
            )
    else:
        lines.append("- 无")
    return lines


def _render_step(lines: list[str], index: str, step: dict[str, Any]) -> None:
    lines.append(f"{index}. {step['name']}")
    lines.append(f"   工作目录：{step['cwd']}")
    if step["env"]:
        rendered_env = " ".join(
            f"{key}={shlex.quote(value)}" for key, value in step["env"].items()
        )
        lines.append(f"   环境变量：{rendered_env}")
    else:
        lines.append("   环境变量：无")
    lines.append(f"   $ {step['command']}")


def render_report(
    request: dict[str, Any],
    assessment: dict[str, Any] | None = None,
) -> str:
    lines = _report_header(request)
    if request["schema_version"] == 1:
        lines.extend(
            [
                "",
                "软件状态约束：当前 schema v1 请求未启用",
                "",
                "原始编译命令：",
            ]
        )
        for index, step in enumerate(request["compile"]["steps"], start=1):
            _render_step(lines, str(index), step)
    else:
        assert assessment is not None
        lines.extend(
            [
                "",
                f"Assessment hash：{assessment['assessment_hash']}",
                f"状态摘要：{assessment['state_summary']}",
                "",
                "LLM 本轮决策：",
                f"- 直接范围：{', '.join(request['decision']['scope'])}",
                f"- 理由：{request['decision']['reason']}",
                "",
                "实际执行单元：",
            ]
        )
        for unit in request["compile"]["units"]:
            lines.append(f"- {unit['component']} -> {unit['action'].upper()}")
            execution = component_execution(
                request["_manifest"], unit["component"]
            )
            if execution is not None:
                lines.append(
                    f"  执行隔离：{execution['mode']} -> "
                    f"{execution['workspace']}"
                )
        lines.extend(["", "原始编译命令："])
        for unit_index, unit in enumerate(request["compile"]["units"], start=1):
            lines.append(
                f"[{unit_index}] {unit['component']} / {unit['action'].upper()}"
            )
            for step_index, step in enumerate(unit["steps"], start=1):
                _render_step(lines, f"{unit_index}.{step_index}", step)
        if request["decision"]["destructive"]:
            lines.extend(["", "显式 destructive 理由："])
            for component, reason in request["decision"]["destructive"].items():
                lines.append(f"- {component}：{reason}")
    lines.extend(["", "Decision：READY"])
    return "\n".join(lines)


def _execute_step(step: dict[str, Any]) -> int:
    env = os.environ.copy()
    env.update(step["env"])
    result = subprocess.run(
        ["/bin/bash", "-lc", step["command"]],
        cwd=step["cwd"],
        env=env,
        check=False,
    )
    return result.returncode


def execute_v1(request: dict[str, Any]) -> int:
    steps = request["compile"]["steps"]
    for index, step in enumerate(steps, start=1):
        print(f"\n[执行 {index}/{len(steps)}] {step['name']}", flush=True)
        result = _execute_step(step)
        if result != 0:
            print(
                f"compile-tool: step failed with exit code {result}: {step['name']}",
                file=sys.stderr,
            )
            return result
    print("\ncompile-tool: all compile steps completed")
    return 0


def execute_v2(request: dict[str, Any], assessment: dict[str, Any]) -> int:
    manifest = request["_manifest"]
    units = request["compile"]["units"]
    for unit_index, unit in enumerate(units, start=1):
        print(
            f"\n[执行组件 {unit_index}/{len(units)}] "
            f"{unit['component']} / {unit['action'].upper()}",
            flush=True,
        )
        workspace = materialize_component_workspace(
            manifest, unit["component"]
        )
        if workspace is not None:
            print(f"compile-tool: materialized isolated source at {workspace}")
        for step_index, step in enumerate(unit["steps"], start=1):
            if not Path(step["cwd"]).is_dir():
                raise ToolError(
                    f"step cwd is unavailable after workspace materialization: "
                    f"{step['cwd']}"
                )
            print(
                f"[执行命令 {step_index}/{len(unit['steps'])}] {step['name']}",
                flush=True,
            )
            result = _execute_step(step)
            if result != 0:
                print(
                    f"compile-tool: step failed with exit code {result}: {step['name']}",
                    file=sys.stderr,
                )
                return result
        record_successful_unit(
            manifest,
            assessment,
            unit["component"],
        )
        print(f"compile-tool: recorded {unit['component']} state", flush=True)
    print("\ncompile-tool: all compile units completed")
    return 0
