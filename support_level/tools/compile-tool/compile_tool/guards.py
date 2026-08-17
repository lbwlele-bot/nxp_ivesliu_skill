from __future__ import annotations

from pathlib import Path
import re
import shlex
from typing import Any

from .common import (
    ENV_NAME_RE,
    ToolError,
    load_yaml,
    mapping_value,
    reject_unknown_keys,
    text_value,
)


TOOL_DIR = Path(__file__).resolve().parents[1]
SUPPORT_LEVEL = TOOL_DIR.parent.parent
UNRESOLVED_VALUES = {
    "unknown",
    "tbd",
    "todo",
    "?",
    "n/a",
    "na",
    "not applicable",
    "not_applicable",
}
PARAMETER_SOURCES = {"user", "assumption", "project", "default"}
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def normalize_parameters(raw_value: Any, label: str) -> dict[str, dict[str, str]]:
    raw = mapping_value(raw_value or {}, label)
    result: dict[str, dict[str, str]] = {}
    for parameter, value in raw.items():
        if not isinstance(parameter, str) or not SAFE_ID_RE.fullmatch(parameter):
            raise ToolError(f"{label} has an invalid parameter name: {parameter!r}")
        item_label = f"{label}.{parameter}"
        item = mapping_value(value, item_label)
        reject_unknown_keys(item, {"value", "source"}, item_label)
        parameter_value = text_value(item.get("value"), f"{item_label}.value")
        source = text_value(item.get("source"), f"{item_label}.source")
        if source not in PARAMETER_SOURCES:
            raise ToolError(
                f"{item_label}.source must be one of: "
                + ", ".join(sorted(PARAMETER_SOURCES))
            )
        result[parameter] = {"value": parameter_value, "source": source}
    return result


def policy_paths(target: str, enabled_components: set[str]) -> list[Path]:
    candidates = [
        SUPPORT_LEVEL / "compile_targets" / target / "COMPILE_POLICY.yaml",
    ]
    for component in sorted(enabled_components):
        candidates.extend(
            [
                SUPPORT_LEVEL
                / "code_assets"
                / "projects"
                / component
                / "COMPILE_POLICY.yaml",
                SUPPORT_LEVEL
                / "code_assets"
                / "workspaces"
                / component
                / "COMPILE_POLICY.yaml",
            ]
        )
    return sorted(path.resolve() for path in candidates if path.is_file())


def _load_policy(path: Path) -> dict[str, Any]:
    label_root = f"compile policy {path}"
    raw = mapping_value(load_yaml(path, label_root), label_root)
    reject_unknown_keys(
        raw,
        {
            "schema_version",
            "target",
            "rules",
            "command_rules",
            "execution_rules",
        },
        label_root,
    )
    if raw.get("schema_version") != 1:
        raise ToolError(f"{label_root} schema_version must be 1")
    target = text_value(raw.get("target"), f"{label_root}.target")
    rules_raw = mapping_value(raw.get("rules") or {}, f"{label_root}.rules")
    rules: list[dict[str, Any]] = []
    for rule_id, value in rules_raw.items():
        if not isinstance(rule_id, str) or not SAFE_ID_RE.fullmatch(rule_id):
            raise ToolError(f"{label_root} has an invalid rule id: {rule_id!r}")
        label = f"{label_root}.rules.{rule_id}"
        item = mapping_value(value, label)
        reject_unknown_keys(
            item,
            {
                "component",
                "parameter",
                "resolution",
                "command",
                "reason",
            },
            label,
        )
        resolution = text_value(item.get("resolution"), f"{label}.resolution")
        if resolution != "must_ask_user":
            raise ToolError(f"{label}.resolution must be must_ask_user")
        command_raw = mapping_value(item.get("command"), f"{label}.command")
        reject_unknown_keys(
            command_raw, {"executables", "assignments"}, f"{label}.command"
        )
        executables = command_raw.get("executables")
        assignments = command_raw.get("assignments")
        if not isinstance(executables, list) or not executables or not all(
            isinstance(entry, str) and entry for entry in executables
        ):
            raise ToolError(f"{label}.command.executables must be a string list")
        if not isinstance(assignments, list) or not assignments or not all(
            isinstance(entry, str) and ENV_NAME_RE.fullmatch(entry)
            for entry in assignments
        ):
            raise ToolError(f"{label}.command.assignments must be variable names")
        rules.append(
            {
                "id": rule_id,
                "policy_path": str(path.relative_to(SUPPORT_LEVEL)),
                "target": target,
                "component": text_value(
                    item.get("component"), f"{label}.component"
                ),
                "parameter": text_value(
                    item.get("parameter"), f"{label}.parameter"
                ),
                "resolution": resolution,
                "command": {
                    "executables": executables,
                    "assignments": assignments,
                },
                "reason": text_value(item.get("reason"), f"{label}.reason"),
            }
        )
    command_rules_raw = mapping_value(
        raw.get("command_rules") or {},
        f"{label_root}.command_rules",
    )
    command_rules: list[dict[str, Any]] = []
    for rule_id, value in command_rules_raw.items():
        if not isinstance(rule_id, str) or not SAFE_ID_RE.fullmatch(rule_id):
            raise ToolError(f"{label_root} has an invalid command rule id: {rule_id!r}")
        label = f"{label_root}.command_rules.{rule_id}"
        item = mapping_value(value, label)
        reject_unknown_keys(
            item,
            {"component", "kind", "parameter", "reason"},
            label,
        )
        kind = text_value(item.get("kind"), f"{label}.kind")
        if kind != "smfw_config_refresh":
            raise ToolError(f"{label}.kind must be smfw_config_refresh")
        command_rules.append(
            {
                "id": rule_id,
                "policy_path": str(path.relative_to(SUPPORT_LEVEL)),
                "target": target,
                "component": text_value(
                    item.get("component"), f"{label}.component"
                ),
                "kind": kind,
                "parameter": text_value(
                    item.get("parameter"), f"{label}.parameter"
                ),
                "reason": text_value(item.get("reason"), f"{label}.reason"),
            }
        )
    execution_rules_raw = mapping_value(
        raw.get("execution_rules") or {},
        f"{label_root}.execution_rules",
    )
    execution_rules: list[dict[str, Any]] = []
    for rule_id, value in execution_rules_raw.items():
        if not isinstance(rule_id, str) or not SAFE_ID_RE.fullmatch(rule_id):
            raise ToolError(
                f"{label_root} has an invalid execution rule id: {rule_id!r}"
            )
        label = f"{label_root}.execution_rules.{rule_id}"
        item = mapping_value(value, label)
        reject_unknown_keys(
            item,
            {"component", "mode", "source_kind", "reason"},
            label,
        )
        mode = text_value(item.get("mode"), f"{label}.mode")
        if mode != "isolated_git":
            raise ToolError(f"{label}.mode must be isolated_git")
        source_kind = text_value(
            item.get("source_kind"), f"{label}.source_kind"
        )
        if source_kind != "managed_git":
            raise ToolError(f"{label}.source_kind must be managed_git")
        execution_rules.append(
            {
                "id": rule_id,
                "policy_path": str(path.relative_to(SUPPORT_LEVEL)),
                "target": target,
                "component": text_value(
                    item.get("component"), f"{label}.component"
                ),
                "mode": mode,
                "source_kind": source_kind,
                "reason": text_value(item.get("reason"), f"{label}.reason"),
            }
        )
    return {
        "parameter_rules": rules,
        "command_rules": command_rules,
        "execution_rules": execution_rules,
    }


def select_guards(
    target: str,
    enabled_components: set[str],
) -> list[dict[str, Any]]:
    guards: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in policy_paths(target, enabled_components):
        for guard in _load_policy(path)["parameter_rules"]:
            key = f"{guard['target']}/{guard['component']}/{guard['id']}"
            if key in seen:
                raise ToolError(f"duplicate compile policy guard: {key}")
            seen.add(key)
            if guard["target"] == target and guard["component"] in enabled_components:
                guards.append(guard)
    return guards


def select_command_policies(
    target: str,
    enabled_components: set[str],
) -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in policy_paths(target, enabled_components):
        for policy in _load_policy(path)["command_rules"]:
            key = f"{policy['target']}/{policy['component']}/{policy['id']}"
            if key in seen:
                raise ToolError(f"duplicate compile command policy: {key}")
            seen.add(key)
            if policy["target"] == target and policy["component"] in enabled_components:
                policies.append(policy)
    return policies


def select_execution_policies(
    target: str,
    enabled_components: set[str],
) -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in policy_paths(target, enabled_components):
        for policy in _load_policy(path)["execution_rules"]:
            key = f"{policy['target']}/{policy['component']}/{policy['id']}"
            if key in seen:
                raise ToolError(f"duplicate compile execution policy: {key}")
            seen.add(key)
            if policy["target"] == target and policy["component"] in enabled_components:
                policies.append(policy)
    return policies


def render_requirements(manifest: dict[str, Any]) -> str:
    lines = [
        "[编译要求]",
        "",
        f"Case：{manifest['case']}",
        f"编译对象：{manifest['target']}",
        "",
        "组件硬规则：",
    ]
    if (
        not manifest["guards"]
        and not manifest["command_policies"]
        and not manifest["execution_policies"]
    ):
        lines.append("- 无额外硬规则；仅使用通用 manifest/request 状态约束")
    for guard in manifest["guards"]:
        assignments = "/".join(guard["command"]["assignments"])
        executables = "/".join(guard["command"]["executables"])
        source_rule = (
            "source=user"
            if guard["resolution"] == "must_ask_user"
            else guard["resolution"]
        )
        lines.append(
            f"- {guard['component']}：{guard['parameter']} "
            f"必须满足 {source_rule}；{executables} 命令必须显式包含 "
            f"{assignments}=<value>"
        )
        lines.append(f"  规则来源：{guard['policy_path']}")
        lines.append(f"  原因：{guard['reason']}")
    for policy in manifest["command_policies"]:
        lines.append(
            f"- {policy['component']}：{policy['parameter']} 决定 SMFW 生成目录；"
            "重编必须依次删除生成目录、really-clean、cfg、all"
        )
        lines.append(f"  规则来源：{policy['policy_path']}")
        lines.append(f"  原因：{policy['reason']}")
    for policy in manifest["execution_policies"]:
        lines.append(
            f"- {policy['component']}：managed Git 构建必须使用 "
            "compile-tool 管理的 isolated_git 执行副本"
        )
        lines.append(f"  规则来源：{policy['policy_path']}")
        lines.append(f"  原因：{policy['reason']}")
    lines.extend(["", "Decision：READY"])
    return "\n".join(lines)


def validate_guard_parameters(
    parameters: dict[str, dict[str, str]],
    guards: list[dict[str, Any]],
) -> None:
    for guard in guards:
        parameter = parameters.get(guard["parameter"])
        prefix = (
            f"parameter guard {guard['id']} requires "
            f"{guard['parameter']} for {guard['target']}/{guard['component']}"
        )
        if parameter is None:
            raise ToolError(f"{prefix}; ask the user before compiling")
        normalized = " ".join(parameter["value"].lower().split())
        if normalized in UNRESOLVED_VALUES:
            raise ToolError(f"{prefix}; ask the user before compiling")
        if (
            guard["resolution"] == "must_ask_user"
            and parameter["source"] != "user"
        ):
            raise ToolError(
                f"{prefix} with source=user; assumptions and defaults are not allowed"
            )


def shell_segments(command: str) -> list[list[str]]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError as exc:
        raise ToolError(f"cannot parse guarded shell command: {exc}") from exc
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token and set(token) <= {";", "&", "|"}:
            if segments[-1]:
                segments.append([])
            continue
        segments[-1].append(token)
    return [segment for segment in segments if segment]


def executable_index(
    segment: list[str],
    executables: list[str],
) -> int | None:
    expected = set(executables)
    for index, token in enumerate(segment):
        if Path(token).name in expected:
            return index
    return None


def segment_assignments(segment: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in segment:
        if "=" not in token:
            continue
        name, value = token.split("=", 1)
        if ENV_NAME_RE.fullmatch(name) and value:
            result[name] = value
    return result


def validate_guard_commands(
    units: list[dict[str, Any]],
    parameters: dict[str, dict[str, str]],
    guards: list[dict[str, Any]],
) -> None:
    units_by_component = {unit["component"]: unit for unit in units}
    for guard in guards:
        unit = units_by_component.get(guard["component"])
        if unit is None:
            continue
        expected = parameters[guard["parameter"]]["value"]
        guarded_segments = 0
        for step in unit["steps"]:
            for segment in shell_segments(step["command"]):
                executable_at = executable_index(
                    segment, guard["command"]["executables"]
                )
                if executable_at is None:
                    continue
                guarded_segments += 1
                assignments = segment_assignments(
                    segment[executable_at + 1 :]
                )
                matches = [
                    assignments[name]
                    for name in guard["command"]["assignments"]
                    if name in assignments
                ]
                if not matches or any(
                    value.casefold() != expected.casefold() for value in matches
                ):
                    names = "/".join(guard["command"]["assignments"])
                    raise ToolError(
                        f"parameter guard {guard['id']} requires explicit "
                        f"{names}={expected} in guarded command: {step['name']}"
                    )
        if guarded_segments == 0:
            commands = "/".join(guard["command"]["executables"])
            raise ToolError(
                f"parameter guard {guard['id']} found no {commands} command "
                f"for {guard['component']}"
            )
