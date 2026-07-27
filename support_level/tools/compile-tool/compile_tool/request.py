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
    hash_data,
    load_yaml,
    mapping_value,
    normalize_hash,
    reject_unknown_keys,
    require_within,
    resolve_absolute,
    text_value,
)
from .manifest import IDENTITY_FIELDS, load_manifest, normalize_identity
from .planner import record_successful_unit


IDENTITY_LABELS = {
    "soc": "SoC",
    "silicon_revision": "Silicon revision",
    "chip_package": "芯片封装",
    "board": "目标板",
    "ddr": "DDR",
    "software_release": "软件版本",
}
NOT_APPLICABLE_VALUES = {"n/a", "na", "not applicable", "not_applicable"}


def _normalize_step(
    raw_value: Any,
    label: str,
    *,
    case_root: Path | None,
) -> dict[str, Any]:
    step = mapping_value(raw_value, label)
    reject_unknown_keys(step, {"name", "cwd", "env", "command"}, label)
    name = text_value(step.get("name"), f"{label}.name")
    cwd = resolve_absolute(step.get("cwd"), f"{label}.cwd")
    if not cwd.is_dir():
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


def _normalize_identity_sections(root: dict[str, Any]) -> tuple[
    dict[str, str], dict[str, str], dict[str, str]
]:
    identity = normalize_identity(root.get("identity"))
    notes_raw = mapping_value(root.get("identity_notes") or {}, "identity_notes")
    effects_raw = mapping_value(root.get("identity_effects"), "identity_effects")
    reject_unknown_keys(notes_raw, set(IDENTITY_FIELDS), "identity_notes")
    reject_unknown_keys(effects_raw, set(IDENTITY_FIELDS), "identity_effects")
    notes: dict[str, str] = {}
    effects: dict[str, str] = {}
    for field in IDENTITY_FIELDS:
        marker = " ".join(identity[field].lower().split())
        if field in notes_raw:
            notes[field] = text_value(notes_raw[field], f"identity_notes.{field}")
        if marker in NOT_APPLICABLE_VALUES and field not in notes:
            raise ToolError(
                f"identity.{field} is N/A but identity_notes.{field} has no reason"
            )
        effects[field] = text_value(
            effects_raw.get(field), f"identity_effects.{field}"
        )
    return identity, notes, effects


def _normalize_v1(root: dict[str, Any]) -> dict[str, Any]:
    reject_unknown_keys(
        root,
        {
            "schema_version",
            "case",
            "identity",
            "identity_notes",
            "identity_effects",
            "compile",
        },
        "request",
    )
    case = text_value(root.get("case"), "case")
    identity, notes, effects = _normalize_identity_sections(root)
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
        "identity": identity,
        "identity_notes": notes,
        "identity_effects": effects,
        "compile": {"target": target, "steps": steps},
    }


def _normalize_v2(root: dict[str, Any]) -> dict[str, Any]:
    reject_unknown_keys(
        root,
        {
            "schema_version",
            "case",
            "identity",
            "identity_notes",
            "identity_effects",
            "assessment",
            "compile",
        },
        "request",
    )
    case = text_value(root.get("case"), "case")
    identity, notes, effects = _normalize_identity_sections(root)
    assessment_raw = mapping_value(root.get("assessment"), "assessment")
    reject_unknown_keys(assessment_raw, {"manifest", "hash"}, "assessment")
    manifest_path = resolve_absolute(
        assessment_raw.get("manifest"), "assessment.manifest"
    )
    manifest = load_manifest(manifest_path)
    if manifest["case"] != case:
        raise ToolError("request case does not match the compile manifest")
    if manifest["identity"] != identity:
        raise ToolError("request identity does not match the compile manifest")
    if manifest["identity_notes"] != notes:
        raise ToolError("request identity notes do not match the compile manifest")
    assessment_hash = normalize_hash(
        text_value(assessment_raw.get("hash"), "assessment.hash"),
        "assessment.hash",
    )
    compile_raw = mapping_value(root.get("compile"), "compile")
    reject_unknown_keys(compile_raw, {"target", "units"}, "compile")
    target = text_value(compile_raw.get("target"), "compile.target")
    if target != "flashbin" or target != manifest["target"]:
        raise ToolError("schema_version 2 currently supports only target flashbin")
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
        steps_raw = unit.get("steps")
        if not isinstance(steps_raw, list) or not steps_raw:
            raise ToolError(f"{label}.steps must be a non-empty list")
        steps = [
            _normalize_step(
                step,
                f"{label}.steps[{step_index}]",
                case_root=case_root,
            )
            for step_index, step in enumerate(steps_raw, start=1)
        ]
        units.append(
            {
                "component": component,
                "action": action,
                "steps": steps,
                "command_hash": hash_data(
                    {"component": component, "action": action, "steps": steps}
                ),
            }
        )
    return {
        "schema_version": 2,
        "case": case,
        "identity": identity,
        "identity_notes": notes,
        "identity_effects": effects,
        "assessment": {
            "manifest": str(manifest_path),
            "hash": assessment_hash,
        },
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


def _hashable_request(request: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in request.items() if not key.startswith("_")}


def request_hash(request: dict[str, Any]) -> str:
    return hash_data(_hashable_request(request))


def verify_assessment(request: dict[str, Any], assessment: dict[str, Any]) -> None:
    if assessment["status"] == "ACQUIRE_REQUIRED":
        raise ToolError("source acquisition is required before compile prepare")
    if assessment["status"] == "REUSE_ONLY":
        raise ToolError("assessment is REUSE_ONLY; no compile request should be executed")
    if request["assessment"]["hash"] != assessment["assessment_hash"]:
        raise ToolError("assessment hash mismatch; run assess and rebuild the request")
    requested = [
        {"component": unit["component"], "action": unit["action"]}
        for unit in request["compile"]["units"]
    ]
    if requested != assessment["required_units"]:
        raise ToolError(
            "compile units do not exactly match the assessed minimal action set: "
            f"expected {assessment['required_units']!r}, got {requested!r}"
        )


def _report_header(request: dict[str, Any]) -> list[str]:
    lines = [
        "[编译前置声明]",
        "",
        f"Case：{request['case']}",
        f"编译对象：{request['compile']['target']}",
    ]
    for field in IDENTITY_FIELDS:
        suffix = (
            f"（{request['identity_notes'][field]}）"
            if field in request["identity_notes"]
            else ""
        )
        lines.append(
            f"{IDENTITY_LABELS[field]}：{request['identity'][field]}{suffix}"
        )
    lines.extend(["", "身份对编译的影响："])
    for field in IDENTITY_FIELDS:
        lines.append(
            f"- {IDENTITY_LABELS[field]} -> {request['identity_effects'][field]}"
        )
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
                "最小重编约束：当前 target 尚未启用，仅执行身份和命令绑定门禁",
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
                "最小动作集合：",
            ]
        )
        for unit in request["compile"]["units"]:
            lines.append(f"- {unit['component']} -> {unit['action'].upper()}")
        lines.extend(["", "原始编译命令："])
        for unit_index, unit in enumerate(request["compile"]["units"], start=1):
            lines.append(
                f"[{unit_index}] {unit['component']} / {unit['action'].upper()}"
            )
            for step_index, step in enumerate(unit["steps"], start=1):
                _render_step(lines, f"{unit_index}.{step_index}", step)
    lines.extend(["", f"Plan hash：{request_hash(request)}", "Decision：READY"])
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
        for step_index, step in enumerate(unit["steps"], start=1):
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
            unit["command_hash"],
        )
        print(f"compile-tool: recorded {unit['component']} state", flush=True)
    print("\ncompile-tool: all compile units completed")
    return 0
