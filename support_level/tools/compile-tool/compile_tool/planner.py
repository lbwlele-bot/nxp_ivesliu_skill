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
    watched_input_snapshots,
)
from .execution import execution_snapshot
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
    if snapshot["kind"] == "managed_git_set":
        return {
            "kind": "managed_git_set",
            "repositories": [
                {
                    "name": entry["name"],
                    "snapshot": _semantic_source(entry["snapshot"]),
                }
                for entry in snapshot["repositories"]
            ],
        }
    if snapshot["kind"] == "release_archive":
        return {
            "kind": "release_archive",
            "case_path": snapshot["case_path"],
            "archive": {
                "path": snapshot["archive"]["path"],
                "sha256": snapshot["archive"]["sha256"],
            },
            "marker": {
                "path": snapshot["marker"]["path"],
                "sha256": snapshot["marker"]["sha256"],
            },
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
            **({"name": entry["name"]} if "name" in entry else {}),
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
    execution = execution_snapshot(component)
    return {
        "source": source,
        "configuration": configuration,
        "toolchains": toolchains,
        "outputs": outputs,
        **({"execution": execution} if execution is not None else {}),
    }, output_errors


def _semantic_input_artifacts(
    artifacts: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, str]]]:
    return {
        component_id: content_identity(entries)
        for component_id, entries in artifacts.items()
    }


def _flashbin_input_artifacts_from_snapshots(
    manifest: dict[str, Any],
    package_id: str,
    snapshots: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for dependency in manifest["profile"]["components"][package_id]["depends_on"]:
        if manifest["components"][dependency]["status"] != "enabled":
            continue
        dependency_snapshot = snapshots[dependency]
        key = (
            "inputs"
            if manifest["components"][dependency]["kind"] == "fixed_input"
            else "outputs"
        )
        result[dependency] = dependency_snapshot[key]
    return result


def _current_flashbin_input_artifacts(
    manifest: dict[str, Any],
    package_id: str,
    previous: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    previous_inputs = previous.get("input_artifacts", {})
    for dependency in manifest["profile"]["components"][package_id]["depends_on"]:
        component = manifest["components"][dependency]
        if component["status"] != "enabled":
            continue
        paths = (
            component["inputs"]
            if component["kind"] == "fixed_input"
            else component["outputs"]
        )
        result[dependency] = file_snapshots(
            paths,
            previous_inputs.get(dependency),
            require_nonempty=True,
        )
    return result


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
            if snapshot.get("execution") != previous.get("execution"):
                reasons.append("构建执行隔离契约变化")
        except (KeyError, TypeError):
            return "rebuild", ["成功构建记录字段不合法"]
    reasons.extend(output_errors)
    return ("rebuild", reasons) if reasons else ("reuse", ["状态与成功记录一致"])


def _assess_flashbin(manifest: dict[str, Any]) -> dict[str, Any]:
    source_result = assess_sources(manifest)
    if source_result["status"] == "ACQUIRE_REQUIRED":
        return {
            "status": "ACQUIRE_REQUIRED",
            "source": source_result,
            "assessment_hash": None,
            "state_summary": "UNKNOWN",
            "observations": {},
            "observed_units": [],
        }

    state = load_state(manifest)
    observations: dict[str, dict[str, Any]] = {}
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
            observations[component_id] = {
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
            snapshot["input_artifacts"] = _flashbin_input_artifacts_from_snapshots(
                manifest,
                component_id,
                snapshots,
            )
        snapshots[component_id] = snapshot
        if component["kind"] == "build":
            action, reasons = _build_decision(snapshot, previous, output_errors)
            observations[component_id] = {
                "action": action,
                "changed": action != "reuse",
                "reasons": reasons,
            }
            continue

        own_action, reasons = _build_decision(snapshot, previous, output_errors)
        dependency_changes = [
            dependency
            for dependency in manifest["profile"]["components"][component_id]["depends_on"]
            if dependency in enabled and observations[dependency]["changed"]
        ]
        if dependency_changes:
            reasons.append("上游输入变化：" + ", ".join(dependency_changes))
        dependency_set_changed = (
            bool(previous)
            and previous.get("dependencies") != snapshot["dependencies"]
        )
        if dependency_set_changed:
            reasons.append("启用的 flash.bin 输入集合变化")
        input_artifacts_changed = (
            bool(previous)
            and _semantic_input_artifacts(snapshot["input_artifacts"])
            != _semantic_input_artifacts(previous.get("input_artifacts", {}))
        )
        if input_artifacts_changed:
            reasons.append("flash.bin 输入产物内容变化")
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
            or input_artifacts_changed
            or profile_changed
            else "reuse"
        )
        observations[component_id] = {
            "action": action,
            "changed": action != "reuse",
            "reasons": reasons if action != "reuse" else ["状态与成功记录一致"],
        }

    for component_id, component in manifest["components"].items():
        if component["status"] == "not_applicable":
            observations[component_id] = {
                "action": "not_applicable",
                "changed": False,
                "reasons": [component["reason"]],
            }

    observed_units = [
        {
            "component": component_id,
            "action": observations[component_id]["action"],
        }
        for component_id in order
        if observations[component_id]["action"] in {"rebuild", "repack"}
    ]
    semantic_payload = {
        "manifest_hash": manifest["hash"],
        "profile_hash": manifest["profile"]["hash"],
        "parameters": manifest["parameters"],
        "observations": observations,
        "observed_units": observed_units,
        "snapshots": {
            component_id: _semantic_snapshot(snapshot)
            for component_id, snapshot in snapshots.items()
        },
    }
    assessment_hash = hash_data(semantic_payload)
    return {
        "status": "READY",
        "state_summary": "CHANGES_OBSERVED" if observed_units else "MATCHED",
        "assessment_hash": assessment_hash,
        "observations": observations,
        "observed_units": observed_units,
        "snapshots": snapshots,
        "state": state,
        "semantic_payload": semantic_payload,
    }


def _previous_sources(
    state: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for component in state["components"].values():
        if not isinstance(component, dict):
            continue
        for source_id, snapshot in component.get("sources", {}).items():
            if source_id not in result and isinstance(snapshot, dict):
                result[source_id] = snapshot
    return result


def _generic_component_snapshot(
    component: dict[str, Any],
    previous: dict[str, Any],
    source_snapshots: dict[str, dict[str, Any]],
    dependency_states: dict[str, str],
) -> tuple[dict[str, Any], list[str]]:
    configuration = configuration_snapshot(
        component["configuration"], previous.get("configuration")
    )
    tools = toolchain_snapshots(component["toolchains"])
    watched_inputs = watched_input_snapshots(
        component["watched_inputs"], previous.get("watched_inputs")
    )
    outputs, output_errors = optional_output_snapshots(
        component["outputs"], previous.get("outputs")
    )
    execution = execution_snapshot(component)
    return {
        "sources": {
            source_id: source_snapshots[source_id]
            for source_id in component["sources"]
        },
        "configuration": configuration,
        "tools": tools,
        "watched_inputs": watched_inputs,
        "outputs": outputs,
        "dependencies": component["depends_on"],
        "dependency_states": dependency_states,
        **({"execution": execution} if execution is not None else {}),
    }, output_errors


def _semantic_generic_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "sources": {
            source_id: _semantic_source(source)
            for source_id, source in snapshot["sources"].items()
        },
        "configuration": _semantic_configuration(snapshot["configuration"]),
        "tools": _semantic_toolchains(snapshot["tools"]),
        "watched_inputs": content_identity(snapshot["watched_inputs"]),
        "outputs": content_identity(snapshot["outputs"]),
        "dependencies": snapshot["dependencies"],
        "dependency_states": snapshot["dependency_states"],
        "execution": snapshot.get("execution"),
    }


def _generic_state_identity(component: dict[str, Any]) -> str:
    required = {
        "sources",
        "configuration",
        "tools",
        "watched_inputs",
        "outputs",
        "dependencies",
        "dependency_states",
    }
    if not required.issubset(component):
        return hash_data({"invalid_component_state": sorted(component)})
    return hash_data(_semantic_generic_snapshot(component))


def _dependency_state_identities(
    state: dict[str, Any],
    dependencies: list[str],
) -> dict[str, str]:
    return {
        dependency: _generic_state_identity(state["components"][dependency])
        for dependency in dependencies
        if isinstance(state["components"].get(dependency), dict)
    }


def _generic_decision(
    snapshot: dict[str, Any],
    previous: dict[str, Any],
    output_errors: list[str],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if not previous:
        reasons.append("没有工具生成的成功构建记录")
    else:
        required = {
            "sources",
            "configuration",
            "tools",
            "watched_inputs",
            "outputs",
            "dependencies",
            "dependency_states",
        }
        if not required.issubset(previous):
            return "rebuild", ["成功构建记录字段不完整"]
        if {
            key: _semantic_source(value)
            for key, value in snapshot["sources"].items()
        } != {
            key: _semantic_source(value)
            for key, value in previous["sources"].items()
        }:
            reasons.append("源码版本或修改状态变化")
        if _semantic_configuration(
            snapshot["configuration"]
        ) != _semantic_configuration(previous["configuration"]):
            reasons.append("配置输入变化")
        if _semantic_toolchains(snapshot["tools"]) != _semantic_toolchains(
            previous["tools"]
        ):
            reasons.append("工具身份变化")
        if content_identity(snapshot["watched_inputs"]) != content_identity(
            previous["watched_inputs"]
        ):
            reasons.append("显式监控输入变化")
        if content_identity(snapshot["outputs"]) != content_identity(
            previous["outputs"]
        ):
            reasons.append("产物内容与成功记录不一致")
        if snapshot["dependencies"] != previous["dependencies"]:
            reasons.append("显式依赖集合变化")
        if snapshot["dependency_states"] != previous["dependency_states"]:
            reasons.append("显式上游成功状态变化")
        if snapshot.get("execution") != previous.get("execution"):
            reasons.append("构建执行隔离契约变化")
    reasons.extend(output_errors)
    return ("rebuild", reasons) if reasons else ("reuse", ["状态与成功记录一致"])


def _validate_known_tool_rules(
    manifest: dict[str, Any],
    component: dict[str, Any],
    snapshot: dict[str, Any],
) -> None:
    if manifest["target"] != "m_freertos_sdk":
        return
    release_markers = [
        manifest["parameters"].get("software_release", {}).get("value", "")
    ]
    for source_id in component["sources"]:
        source = manifest["sources"][source_id]
        if source["kind"] == "release_archive":
            release_markers.append(Path(source["archive_path"]).name)
    if not any("SDK_2_9_0_EVK-MIMX8DXL" in marker for marker in release_markers):
        return
    compilers = [
        entry for entry in snapshot["tools"] if entry.get("name") == "compiler"
    ]
    if not compilers:
        raise ToolError(
            "SDK_2_9_0_EVK-MIMX8DXL requires tools entry named compiler"
        )
    if not all("9.2.1" in entry["version_output"] for entry in compilers):
        raise ToolError(
            "SDK_2_9_0_EVK-MIMX8DXL requires GCC ARM Embedded 9.2.1"
        )


def _assess_generic(manifest: dict[str, Any]) -> dict[str, Any]:
    source_result = assess_sources(manifest)
    if source_result["status"] == "ACQUIRE_REQUIRED":
        return {
            "status": "ACQUIRE_REQUIRED",
            "source": source_result,
            "assessment_hash": None,
            "state_summary": "UNKNOWN",
            "observations": {},
            "observed_units": [],
        }

    state = load_state(manifest)
    previous_sources = _previous_sources(state)
    source_snapshots = {
        source_id: source_snapshot(source, previous_sources.get(source_id))
        for source_id, source in manifest["sources"].items()
    }
    observations: dict[str, dict[str, Any]] = {}
    snapshots: dict[str, dict[str, Any]] = {}
    for component_id in manifest["component_order"]:
        component = manifest["components"][component_id]
        previous = _previous_component(state, component_id)
        snapshot, output_errors = _generic_component_snapshot(
            component,
            previous,
            source_snapshots,
            _dependency_state_identities(state, component["depends_on"]),
        )
        _validate_known_tool_rules(manifest, component, snapshot)
        action, reasons = _generic_decision(snapshot, previous, output_errors)
        changed_dependencies = [
            dependency
            for dependency in component["depends_on"]
            if observations[dependency]["changed"]
        ]
        if changed_dependencies:
            action = "rebuild"
            reasons.append("显式上游变化：" + ", ".join(changed_dependencies))
        snapshots[component_id] = snapshot
        observations[component_id] = {
            "action": action,
            "changed": action != "reuse",
            "reasons": reasons if action != "reuse" else ["状态与成功记录一致"],
        }

    observed_units = [
        {"component": component_id, "action": "rebuild"}
        for component_id in manifest["component_order"]
        if observations[component_id]["action"] == "rebuild"
    ]
    semantic_payload = {
        "manifest_hash": manifest["hash"],
        "profile_hash": manifest["profile"]["hash"],
        "parameters": manifest["parameters"],
        "observations": observations,
        "observed_units": observed_units,
        "snapshots": {
            component_id: _semantic_generic_snapshot(snapshot)
            for component_id, snapshot in snapshots.items()
        },
    }
    return {
        "status": "READY",
        "state_summary": "CHANGES_OBSERVED" if observed_units else "MATCHED",
        "assessment_hash": hash_data(semantic_payload),
        "observations": observations,
        "observed_units": observed_units,
        "snapshots": snapshots,
        "state": state,
        "semantic_payload": semantic_payload,
    }


def assess(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("generic"):
        return _assess_generic(manifest)
    return _assess_flashbin(manifest)


def _semantic_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    if "sources" in snapshot:
        return _semantic_generic_snapshot(snapshot)
    if "inputs" in snapshot and "source" not in snapshot:
        return {"inputs": content_identity(snapshot["inputs"])}
    return {
        "source": _semantic_source(snapshot["source"]),
        "configuration": _semantic_configuration(snapshot["configuration"]),
        "toolchains": _semantic_toolchains(snapshot["toolchains"]),
        "outputs": content_identity(snapshot["outputs"]),
        **(
            {"execution": snapshot["execution"]}
            if "execution" in snapshot
            else {}
        ),
        **(
            {"dependencies": snapshot["dependencies"]}
            if "dependencies" in snapshot
            else {}
        ),
        **(
            {
                "input_artifacts": _semantic_input_artifacts(
                    snapshot["input_artifacts"]
                )
            }
            if "input_artifacts" in snapshot
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

    lines.extend(["", "组件状态观察："])
    for component_id in manifest["profile"]["components"]:
        observation = result["observations"][component_id]
        reason = "；".join(observation["reasons"])
        lines.append(
            f"- {component_id}: {observation['action'].upper()}（{reason}）"
        )
    if manifest.get("generic"):
        lines.extend(
            [
                "",
                "约束范围：通用状态单元；未声明的项目内部依赖不做推断",
            ]
        )
    lines.extend(
        [
            "",
            f"状态摘要：{result['state_summary']}",
            "观察到的影响组件：",
            *(
                [
                    f"- {item['component']} -> {item['action'].upper()}"
                    for item in result["observed_units"]
                ]
                or ["- 无"]
            ),
            "",
            f"Assessment hash：{result['assessment_hash']}",
            f"Decision：{result['status']}",
        ]
    )
    return "\n".join(lines)


def _record_flashbin_unit(
    manifest: dict[str, Any],
    assessment: dict[str, Any],
    component_id: str,
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
        current["input_artifacts"] = _current_flashbin_input_artifacts(
            manifest,
            component_id,
            _previous_component(state, component_id),
        )
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
        **(
            {"execution": current["execution"]}
            if "execution" in current
            else {}
        ),
        **(
            {"dependencies": current["dependencies"]}
            if component["kind"] == "package"
            else {}
        ),
        **(
            {"input_artifacts": current["input_artifacts"]}
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


def _record_generic_unit(
    manifest: dict[str, Any],
    assessment: dict[str, Any],
    component_id: str,
) -> None:
    component = manifest["components"][component_id]
    before = assessment["snapshots"][component_id]
    state = load_state(manifest)
    previous = _previous_component(state, component_id)
    current_sources = {
        source_id: source_snapshot(
            manifest["sources"][source_id],
            previous.get("sources", {}).get(source_id),
        )
        for source_id in component["sources"]
    }
    current, output_errors = _generic_component_snapshot(
        component,
        previous,
        current_sources,
        _dependency_state_identities(state, component["depends_on"]),
    )
    _validate_known_tool_rules(manifest, component, current)
    if output_errors:
        raise ToolError(
            f"{component_id} did not produce valid outputs: " + "; ".join(output_errors)
        )
    before_inputs = _semantic_generic_snapshot(before)
    current_inputs = _semantic_generic_snapshot(current)
    for field in (
        "sources",
        "configuration",
        "tools",
        "watched_inputs",
        "dependencies",
        "execution",
    ):
        if before_inputs[field] != current_inputs[field]:
            raise ToolError(
                f"{component_id} {field} changed while its build unit was running"
            )

    previous_outputs = {
        entry["path"]: entry
        for entry in previous.get("outputs", [])
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    }
    before_outputs = {
        entry["path"]: entry for entry in before.get("outputs", [])
    }
    current_outputs = {
        entry["path"]: entry for entry in current.get("outputs", [])
    }
    unrepaired = [
        path
        for path, expected in previous_outputs.items()
        if path in before_outputs
        and before_outputs[path].get("sha256") != expected.get("sha256")
        and current_outputs[path].get("sha256") == before_outputs[path].get("sha256")
    ]
    if unrepaired:
        raise ToolError(
            f"{component_id} command did not repair changed outputs: "
            + ", ".join(unrepaired)
        )

    state["components"][component_id] = current
    write_state(manifest, state)


def record_successful_unit(
    manifest: dict[str, Any],
    assessment: dict[str, Any],
    component_id: str,
) -> None:
    if manifest.get("generic"):
        _record_generic_unit(manifest, assessment, component_id)
        return
    _record_flashbin_unit(manifest, assessment, component_id)
