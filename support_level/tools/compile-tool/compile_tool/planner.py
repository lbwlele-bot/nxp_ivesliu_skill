from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import ToolError, hash_data
from .fingerprints import (
    configuration_snapshot,
    content_identity,
    file_snapshots,
    optional_output_snapshots,
    source_snapshot,
    toolchain_snapshots,
)
from .manifest import topological_order
from .sources import assess_sources
from .state import load_state, write_state


def _semantic_files(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    return content_identity(entries)


def _semantic_source(snapshot: dict[str, Any]) -> dict[str, Any]:
    if snapshot["kind"] == "managed_git":
        return {
            "kind": snapshot["kind"],
            "canonical_path": snapshot["canonical_path"],
            "path": snapshot["path"],
            "commit": snapshot["commit"],
            "tracked_diff_sha256": snapshot["tracked_diff_sha256"],
            "untracked": snapshot["untracked"],
            "ref_kind": snapshot["ref_kind"],
            "ref": snapshot["ref"],
            "remote_url": snapshot["remote_url"],
        }
    return {"kind": "local_files", "files": _semantic_files(snapshot["files"])}


def _semantic_configuration(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "values": snapshot["values"],
        "files": _semantic_files(snapshot["files"]),
    }


def _semantic_toolchains(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "executable": entry["executable"],
            "version_args": entry["version_args"],
            "version_sha256": entry["version_sha256"],
        }
        for entry in snapshots
    ]


def _previous_component(state: dict[str, Any], component_id: str) -> dict[str, Any]:
    value = state["components"].get(component_id)
    return value if isinstance(value, dict) else {}


def _component_snapshot(
    component: dict[str, Any],
    previous: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    source = source_snapshot(component["source"], previous.get("source"))
    configuration = configuration_snapshot(
        component["configuration"], previous.get("configuration")
    )
    toolchains = toolchain_snapshots(component["toolchains"])
    outputs, output_errors = optional_output_snapshots(
        component["outputs"], previous.get("outputs")
    )
    return {
        "source": source,
        "configuration": configuration,
        "toolchains": toolchains,
        "outputs": outputs,
    }, output_errors


def _build_decision(
    snapshot: dict[str, Any],
    previous: dict[str, Any],
    output_errors: list[str],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if not previous:
        reasons.append("没有工具生成的成功构建记录")
    else:
        required = {"source", "configuration", "toolchains", "outputs"}
        if not required.issubset(previous):
            return "rebuild", ["成功构建记录字段不完整"]
        try:
            if _semantic_source(snapshot["source"]) != _semantic_source(
                previous["source"]
            ):
                reasons.append("源码 commit 或 patch 状态变化")
            if _semantic_configuration(
                snapshot["configuration"]
            ) != _semantic_configuration(previous["configuration"]):
                reasons.append("配置输入变化")
            if _semantic_toolchains(snapshot["toolchains"]) != _semantic_toolchains(
                previous["toolchains"]
            ):
                reasons.append("工具链身份变化")
            if content_identity(snapshot["outputs"]) != content_identity(
                previous.get("outputs", [])
            ):
                reasons.append("产物内容与成功记录不一致")
        except (KeyError, TypeError):
            return "rebuild", ["成功构建记录字段不合法"]
    reasons.extend(output_errors)
    return ("rebuild", reasons) if reasons else ("reuse", ["状态与成功记录一致"])


def assess(manifest: dict[str, Any]) -> dict[str, Any]:
    source_result = assess_sources(manifest)
    if source_result["status"] == "ACQUIRE_REQUIRED":
        return {
            "status": "ACQUIRE_REQUIRED",
            "source": source_result,
            "assessment_hash": None,
            "decisions": {},
            "required_units": [],
        }

    state = load_state(manifest)
    decisions: dict[str, dict[str, Any]] = {}
    snapshots: dict[str, dict[str, Any]] = {}
    enabled = {
        component_id
        for component_id, component in manifest["components"].items()
        if component["status"] == "enabled"
    }
    order = topological_order(manifest["profile"], enabled)

    for component_id in order:
        component = manifest["components"][component_id]
        previous = _previous_component(state, component_id)
        if component["kind"] == "fixed_input":
            missing_inputs = [
                value for value in component["inputs"] if not Path(value).is_file()
            ]
            if missing_inputs:
                raise ToolError(
                    "DOWNLOAD_REQUIRED: fixed flashbin inputs are unavailable and "
                    "will not be downloaded automatically: "
                    + ", ".join(missing_inputs)
                )
            inputs = file_snapshots(
                component["inputs"],
                previous.get("inputs"),
                require_nonempty=True,
            )
            snapshots[component_id] = {"inputs": inputs}
            if not previous:
                changed = True
                reasons = ["固定输入尚未被成功打包记录"]
            elif content_identity(inputs) != content_identity(previous.get("inputs", [])):
                changed = True
                reasons = ["固定输入内容变化"]
            else:
                changed = False
                reasons = ["固定输入与成功记录一致"]
            decisions[component_id] = {
                "action": "reuse",
                "changed": changed,
                "reasons": reasons,
            }
            continue

        snapshot, output_errors = _component_snapshot(component, previous)
        if component["kind"] == "package":
            snapshot["dependencies"] = [
                dependency
                for dependency in manifest["profile"]["components"][component_id][
                    "depends_on"
                ]
                if dependency in enabled
            ]
        snapshots[component_id] = snapshot
        if component["kind"] == "build":
            action, reasons = _build_decision(snapshot, previous, output_errors)
            decisions[component_id] = {
                "action": action,
                "changed": action != "reuse",
                "reasons": reasons,
            }
            continue

        own_action, reasons = _build_decision(snapshot, previous, output_errors)
        dependency_changes = [
            dependency
            for dependency in manifest["profile"]["components"][component_id]["depends_on"]
            if dependency in enabled and decisions[dependency]["changed"]
        ]
        if dependency_changes:
            reasons.append("上游输入变化：" + ", ".join(dependency_changes))
        dependency_set_changed = (
            bool(previous)
            and previous.get("dependencies") != snapshot["dependencies"]
        )
        if dependency_set_changed:
            reasons.append("启用的 flash.bin 输入集合变化")
        profile_changed = (
            bool(previous)
            and state.get("profile_hash") != manifest["profile"]["hash"]
        )
        if profile_changed:
            reasons.append("flashbin 依赖配置变化")
        action = (
            "repack"
            if own_action == "rebuild"
            or dependency_changes
            or dependency_set_changed
            or profile_changed
            else "reuse"
        )
        decisions[component_id] = {
            "action": action,
            "changed": action != "reuse",
            "reasons": reasons if action != "reuse" else ["状态与成功记录一致"],
        }

    for component_id, component in manifest["components"].items():
        if component["status"] == "not_applicable":
            decisions[component_id] = {
                "action": "not_applicable",
                "changed": False,
                "reasons": [component["reason"]],
            }

    required_units = [
        {
            "component": component_id,
            "action": decisions[component_id]["action"],
        }
        for component_id in order
        if decisions[component_id]["action"] in {"rebuild", "repack"}
    ]
    semantic_payload = {
        "manifest_hash": manifest["hash"],
        "profile_hash": manifest["profile"]["hash"],
        "identity": manifest["identity"],
        "decisions": decisions,
        "required_units": required_units,
        "snapshots": {
            component_id: _semantic_snapshot(snapshot)
            for component_id, snapshot in snapshots.items()
        },
    }
    assessment_hash = hash_data(semantic_payload)
    return {
        "status": "READY" if required_units else "REUSE_ONLY",
        "assessment_hash": assessment_hash,
        "decisions": decisions,
        "required_units": required_units,
        "snapshots": snapshots,
        "state": state,
        "semantic_payload": semantic_payload,
    }


def _semantic_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    if "inputs" in snapshot and "source" not in snapshot:
        return {"inputs": content_identity(snapshot["inputs"])}
    return {
        "source": _semantic_source(snapshot["source"]),
        "configuration": _semantic_configuration(snapshot["configuration"]),
        "toolchains": _semantic_toolchains(snapshot["toolchains"]),
        "outputs": content_identity(snapshot["outputs"]),
        **(
            {"dependencies": snapshot["dependencies"]}
            if "dependencies" in snapshot
            else {}
        ),
    }


def render_assessment(manifest: dict[str, Any], result: dict[str, Any]) -> str:
    lines = [
        "[软件状态评估]",
        "",
        f"Case：{manifest['case']}",
        f"编译对象：{manifest['target']}",
    ]
    if result["status"] == "ACQUIRE_REQUIRED":
        lines.extend(["", "源码状态：需要先执行 acquire"])
        for operation in result["source"]["operations"]:
            lines.append(f"- {operation['component']} -> {operation['purpose']}")
        lines.extend(
            [
                f"Acquisition plan hash：{result['source']['plan_hash']}",
                "Decision：ACQUIRE_REQUIRED",
            ]
        )
        return "\n".join(lines)

    lines.extend(["", "组件决策："])
    for component_id in manifest["profile"]["components"]:
        decision = result["decisions"][component_id]
        reason = "；".join(decision["reasons"])
        lines.append(f"- {component_id}: {decision['action'].upper()}（{reason}）")
    lines.extend(
        [
            "",
            f"Assessment hash：{result['assessment_hash']}",
            f"Decision：{result['status']}",
        ]
    )
    return "\n".join(lines)


def record_successful_unit(
    manifest: dict[str, Any],
    assessment: dict[str, Any],
    component_id: str,
    command_hash: str,
) -> None:
    component = manifest["components"][component_id]
    if component["kind"] == "fixed_input":
        raise ToolError(f"fixed input cannot be an executable unit: {component_id}")
    before = assessment["snapshots"][component_id]
    state = load_state(manifest)
    current, output_errors = _component_snapshot(
        component, _previous_component(state, component_id)
    )
    if component["kind"] == "package":
        current["dependencies"] = [
            dependency
            for dependency in manifest["profile"]["components"][component_id][
                "depends_on"
            ]
            if manifest["components"][dependency]["status"] == "enabled"
        ]
    if output_errors:
        raise ToolError(
            f"{component_id} did not produce valid outputs: " + "; ".join(output_errors)
        )
    if _semantic_source(current["source"]) != _semantic_source(before["source"]):
        raise ToolError(f"{component_id} source changed while its build unit was running")
    before_by_path = {
        entry["path"]: entry for entry in before.get("outputs", [])
    }
    stale_outputs = [
        entry["path"]
        for entry in current["outputs"]
        if entry["path"] in before_by_path
        and entry["stat"] == before_by_path[entry["path"]]["stat"]
    ]
    if stale_outputs:
        raise ToolError(
            f"{component_id} command completed but did not refresh outputs: "
            + ", ".join(stale_outputs)
        )
    state["components"][component_id] = {
        "kind": component["kind"],
        "source": current["source"],
        "configuration": current["configuration"],
        "toolchains": current["toolchains"],
        "outputs": current["outputs"],
        "command_hash": command_hash,
        **(
            {"dependencies": current["dependencies"]}
            if component["kind"] == "package"
            else {}
        ),
    }
    if component["kind"] == "package":
        for dependency in manifest["profile"]["components"][component_id]["depends_on"]:
            dependency_component = manifest["components"][dependency]
            if (
                dependency_component["status"] == "enabled"
                and dependency_component["kind"] == "fixed_input"
            ):
                state["components"][dependency] = {
                    "kind": "fixed_input",
                    "inputs": file_snapshots(
                        dependency_component["inputs"],
                        _previous_component(state, dependency).get("inputs"),
                        require_nonempty=True,
                    ),
                }
    write_state(manifest, state)
