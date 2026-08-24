from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import ToolError, hash_data
from .fingerprints import file_snapshot
from .manifest import load_manifest
from .state import load_state


def _assert_acyclic_artifact_graph(
    root: dict[str, Any],
    upstream: dict[str, Any],
    visited: set[str],
) -> None:
    target = upstream["target"]
    if target == root["target"]:
        raise ToolError(
            f"cross-manifest artifact dependency cycle reaches {root['target']}"
        )
    if target in visited:
        return
    visited.add(target)
    for artifact_input in upstream.get("artifact_inputs", {}).values():
        dependency = load_manifest(Path(artifact_input["manifest"]))
        if dependency["case_root"] != root["case_root"]:
            raise ToolError("artifact dependency graph crosses case boundaries")
        _assert_acyclic_artifact_graph(root, dependency, visited)


def _producer_target_state(
    root_state: dict[str, Any],
    upstream: dict[str, Any],
) -> dict[str, Any]:
    value = root_state.get("targets", {}).get(upstream["target"])
    if not isinstance(value, dict):
        raise ToolError(
            f"artifact producer {upstream['target']} has no successful software state"
        )
    if value.get("manifest_hash") != upstream["hash"]:
        raise ToolError(
            f"artifact producer {upstream['target']} manifest changed after its "
            "last successful build"
        )
    components = value.get("components")
    if not isinstance(components, dict):
        raise ToolError(
            f"artifact producer {upstream['target']} state has invalid components"
        )
    return value


def _recorded_output(
    component_state: dict[str, Any],
    path: str,
    label: str,
) -> dict[str, Any]:
    outputs = component_state.get("outputs")
    if not isinstance(outputs, list):
        raise ToolError(f"{label} producer state has no recorded outputs")
    matches = [
        entry
        for entry in outputs
        if isinstance(entry, dict) and entry.get("path") == path
    ]
    if len(matches) != 1:
        raise ToolError(f"{label} is not uniquely recorded by its producer state")
    return matches[0]


def resolve_artifact_inputs(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    artifact_inputs = manifest.get("artifact_inputs") or {}
    if not artifact_inputs:
        return {}
    profile = manifest.get("project_profile")
    if not isinstance(profile, dict):
        raise ToolError("cross-manifest artifact inputs require a project profile")
    root_state = load_state(manifest)["_root_state"]
    resolved: dict[str, dict[str, Any]] = {}
    for input_id, artifact_input in artifact_inputs.items():
        label = f"artifact input {input_id}"
        slot = artifact_input["slot"]
        contract = profile["artifact_inputs"][slot]
        upstream = load_manifest(Path(artifact_input["manifest"]))
        if upstream["case"] != manifest["case"] or upstream["case_root"] != manifest["case_root"]:
            raise ToolError(f"{label} producer must belong to the same case")
        if upstream["target"] == manifest["target"]:
            raise ToolError(f"{label} producer target cannot reference itself")
        _assert_acyclic_artifact_graph(manifest, upstream, set())
        export = upstream.get("exports", {}).get(artifact_input["artifact"])
        if not isinstance(export, dict):
            raise ToolError(
                f"{label} references unknown producer export: "
                f"{artifact_input['artifact']}"
            )
        if export["type"] != contract["type"]:
            raise ToolError(
                f"{label} type mismatch: expected {contract['type']}, "
                f"got {export['type']}"
            )
        target_state = _producer_target_state(root_state, upstream)
        component_state = target_state["components"].get(export["component"])
        if not isinstance(component_state, dict):
            raise ToolError(
                f"{label} producer component {export['component']} has no "
                "successful state"
            )
        recorded = _recorded_output(component_state, export["path"], label)
        current = file_snapshot(
            Path(export["path"]),
            recorded,
            require_nonempty=True,
        )
        if current.get("sha256") != recorded.get("sha256"):
            raise ToolError(
                f"{label} content differs from its producer's successful state"
            )
        for producer_parameter, consumer_parameter in contract[
            "parameter_matches"
        ].items():
            producer_value = export["identity"].get(producer_parameter)
            if producer_value is None:
                raise ToolError(
                    f"{label} producer export does not declare identity parameter "
                    f"{producer_parameter}"
                )
            consumer_value = manifest["parameters"][consumer_parameter]["value"]
            if producer_value.casefold() != consumer_value.casefold():
                raise ToolError(
                    f"{label} identity mismatch: producer {producer_parameter}="
                    f"{producer_value}, consumer {consumer_parameter}={consumer_value}"
                )
        resolved[input_id] = {
            "slot": slot,
            "producer_target": upstream["target"],
            "producer_manifest": upstream["path"],
            "producer_manifest_hash": upstream["hash"],
            "producer_component": export["component"],
            "producer_state_identity": hash_data(component_state),
            "artifact": artifact_input["artifact"],
            "type": export["type"],
            "path": export["path"],
            "sha256": current["sha256"],
            "identity": export["identity"],
            "producer_origin": component_state.get("origin"),
        }
    return resolved


def semantic_artifact_inputs(
    snapshots: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    fields = (
        "slot",
        "producer_target",
        "producer_manifest_hash",
        "producer_component",
        "producer_state_identity",
        "artifact",
        "type",
        "path",
        "sha256",
        "identity",
        "producer_origin",
    )
    return {
        input_id: {field: snapshot[field] for field in fields}
        for input_id, snapshot in snapshots.items()
    }
