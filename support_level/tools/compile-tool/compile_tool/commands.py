from __future__ import annotations

from pathlib import Path, PurePosixPath
import re
from typing import Any

from .common import ToolError
from .guards import (
    UNRESOLVED_VALUES,
    executable_index,
    segment_assignments,
    shell_segments,
)


CLEAN_TARGETS = {"clean", "distclean", "mrproper", "really-clean"}
SAFE_CONFIG_PART_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _make_targets(segment: list[str], executable_at: int) -> set[str]:
    targets: set[str] = set()
    for token in segment[executable_at + 1 :]:
        if token.startswith("-") or "=" in token:
            continue
        targets.add(token)
    return targets


def _rm_targets(segment: list[str], executable_at: int) -> tuple[bool, list[str]]:
    recursive = False
    force = False
    targets: list[str] = []
    options_done = False
    for token in segment[executable_at + 1 :]:
        if token == "--":
            options_done = True
            continue
        if not options_done and token.startswith("--"):
            recursive = recursive or token == "--recursive"
            force = force or token == "--force"
            continue
        if not options_done and token.startswith("-") and token != "-":
            flags = token[1:]
            recursive = recursive or "r" in flags or "R" in flags
            force = force or "f" in flags
            continue
        targets.append(token)
    return recursive and force, targets


def _destructive_segments(
    units: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for unit in units:
        for step_index, step in enumerate(unit["steps"]):
            for segment_index, segment in enumerate(shell_segments(step["command"])):
                make_at = executable_index(segment, ["make"])
                if make_at is not None:
                    targets = sorted(_make_targets(segment, make_at) & CLEAN_TARGETS)
                    if targets:
                        result.append(
                            {
                                "component": unit["component"],
                                "step": step,
                                "key": (step_index, segment_index),
                                "kind": "make-clean",
                                "targets": targets,
                                "segment": segment,
                            }
                        )
                rm_at = executable_index(segment, ["rm"])
                if rm_at is not None:
                    recursive_force, targets = _rm_targets(segment, rm_at)
                    if recursive_force:
                        result.append(
                            {
                                "component": unit["component"],
                                "step": step,
                                "key": (step_index, segment_index),
                                "kind": "rm-rf",
                                "targets": targets,
                                "segment": segment,
                            }
                        )
    return result


def _safe_smfw_config(value: str, label: str) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(not SAFE_CONFIG_PART_RE.fullmatch(part) for part in path.parts)
    ):
        raise ToolError(f"{label} must be a safe relative SMFW config name")
    return path.as_posix()


def validate_command_policy_parameters(
    parameters: dict[str, dict[str, str]],
    policies: list[dict[str, Any]],
) -> None:
    for policy in policies:
        if policy["kind"] != "smfw_config_refresh":
            raise ToolError(f"unsupported command policy kind: {policy['kind']}")
        parameter = parameters.get(policy["parameter"])
        if parameter is None:
            raise ToolError(
                f"command policy {policy['id']} requires parameter "
                f"{policy['parameter']}"
            )
        if " ".join(parameter["value"].lower().split()) in UNRESOLVED_VALUES:
            raise ToolError(
                f"command policy {policy['id']} requires a resolved "
                f"{policy['parameter']}"
            )
        _safe_smfw_config(
            parameter["value"],
            f"parameters.{policy['parameter']}.value",
        )


def _smfw_source_root(
    manifest: dict[str, Any],
    component: str,
) -> Path | None:
    item = manifest["components"][component]
    execution = item.get("execution")
    if isinstance(execution, dict) and execution.get("mode") == "isolated_git":
        return Path(execution["workspace"]).resolve()
    source = item.get("source")
    if isinstance(source, dict) and source.get("kind") == "managed_git":
        return Path(source["case_path"]).resolve()
    return None


def _validate_smfw_refresh(
    unit: dict[str, Any],
    manifest: dict[str, Any],
    policy: dict[str, Any],
) -> set[tuple[int, int]]:
    parameter = manifest["parameters"][policy["parameter"]]
    config = _safe_smfw_config(
        parameter["value"],
        f"parameters.{policy['parameter']}.value",
    )
    generated_dir = f"configs/{config}"
    sequence: dict[str, tuple[int, int] | None] = {
        "remove-generated-config": None,
        "really-clean": None,
        "cfg": None,
        "all": None,
    }
    consumed: set[tuple[int, int]] = set()
    sequence_cwds: set[str] = set()

    for step_index, step in enumerate(unit["steps"]):
        for segment_index, segment in enumerate(shell_segments(step["command"])):
            key = (step_index, segment_index)
            rm_at = executable_index(segment, ["rm"])
            if rm_at is not None:
                recursive_force, targets = _rm_targets(segment, rm_at)
                normalized_targets = [target.rstrip("/") for target in targets]
                config_targets = [
                    target
                    for target in normalized_targets
                    if target == "configs" or target.startswith("configs/")
                ]
                if config_targets and normalized_targets != [generated_dir]:
                    raise ToolError(
                        f"command policy {policy['id']} only permits deleting "
                        f"{generated_dir}; source .cfg files and the configs "
                        "directory must be preserved"
                    )
                if recursive_force:
                    if normalized_targets == [generated_dir]:
                        sequence["remove-generated-config"] = key
                        consumed.add(key)
                        sequence_cwds.add(step["cwd"])

            make_at = executable_index(segment, ["make"])
            if make_at is None:
                continue
            targets = _make_targets(segment, make_at)
            assignments = segment_assignments(segment[make_at + 1 :])
            if "really-clean" in targets:
                sequence["really-clean"] = key
                consumed.add(key)
                sequence_cwds.add(step["cwd"])
            if "cfg" in targets:
                if assignments.get("config") != config:
                    raise ToolError(
                        f"command policy {policy['id']} requires "
                        f"make config={config} cfg"
                    )
                sequence["cfg"] = key
                sequence_cwds.add(step["cwd"])
            if "all" in targets:
                if assignments.get("config") != config:
                    raise ToolError(
                        f"command policy {policy['id']} requires "
                        f"make config={config} all"
                    )
                sequence["all"] = key
                sequence_cwds.add(step["cwd"])

    missing = [name for name, key in sequence.items() if key is None]
    if missing:
        raise ToolError(
            f"command policy {policy['id']} is missing required SMFW actions: "
            + ", ".join(missing)
        )
    ordered = [sequence[name] for name in sequence]
    if ordered != sorted(ordered):
        raise ToolError(
            f"command policy {policy['id']} requires order: remove generated "
            "config, really-clean, cfg, all"
        )
    if len(sequence_cwds) != 1:
        raise ToolError(
            f"command policy {policy['id']} requires all SMFW refresh actions "
            "to use one working directory"
        )
    source_root = _smfw_source_root(manifest, policy["component"])
    if source_root is not None:
        only_cwd = Path(next(iter(sequence_cwds))).resolve()
        if only_cwd != source_root:
            raise ToolError(
                f"command policy {policy['id']} requires cwd to be the case "
                f"SMFW checkout: {source_root}"
            )
    return consumed


def validate_compile_commands(
    units: list[dict[str, Any]],
    decision: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    units_by_component = {unit["component"]: unit for unit in units}
    consumed: dict[str, set[tuple[int, int]]] = {}
    for policy in manifest["command_policies"]:
        unit = units_by_component.get(policy["component"])
        if unit is None:
            continue
        if policy["kind"] == "smfw_config_refresh":
            consumed.setdefault(policy["component"], set()).update(
                _validate_smfw_refresh(unit, manifest, policy)
            )

    undeclared: list[str] = []
    destructive = decision["destructive"]
    detected_components: set[str] = set()
    for item in _destructive_segments(units):
        component = item["component"]
        if item["key"] in consumed.get(component, set()):
            continue
        detected_components.add(component)
        if component not in destructive:
            detail = (
                ",".join(item["targets"])
                if item["targets"]
                else "recursive forced deletion"
            )
            undeclared.append(f"{component}: {detail}")
    if undeclared:
        raise ToolError(
            "destructive compile commands require decision.destructive reasons: "
            + "; ".join(undeclared)
        )
    unused = sorted(set(destructive) - detected_components)
    if unused:
        raise ToolError(
            "decision.destructive declares components without destructive commands: "
            + ", ".join(unused)
        )
