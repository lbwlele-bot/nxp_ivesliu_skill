from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .common import (
    ToolError,
    hash_data,
    hash_file,
    load_yaml,
    mapping_value,
    normalize_hash,
    reject_unknown_keys,
    text_value,
)


def _condition_matches(raw_value: Any, parameters: dict[str, str], label: str) -> bool:
    raw = mapping_value(raw_value, label)
    reject_unknown_keys(raw, {"parameter", "equals", "count"}, label)
    parameter = text_value(raw.get("parameter"), f"{label}.parameter")
    if parameter not in parameters:
        raise ToolError(f"{label} references unknown parameter: {parameter}")
    expected = text_value(raw.get("equals"), f"{label}.equals")
    return parameters[parameter].casefold() == expected.casefold()


def _producer_parameters(entry: dict[str, str], label: str) -> dict[str, str]:
    raw = mapping_value(
        load_yaml(Path(entry["checklist"]), f"{label} producer checklist"),
        f"{label} producer checklist",
    )
    kind = raw.get("kind")
    if kind == "project_compile_checklist":
        values = mapping_value(raw.get("parameters"), f"{label} producer parameters")
        return {name: str(value) for name, value in values.items()}
    if kind == "m_freertos_sdk_compile_checklist":
        artifact = entry["artifact"]
        if "." not in artifact:
            raise ToolError(f"{label} M SDK artifact must use <job>.<format>")
        job_id, artifact_format = artifact.rsplit(".", 1)
        if artifact_format not in {"elf", "bin"}:
            raise ToolError(f"{label} M SDK artifact format is invalid: {artifact_format}")
        jobs = mapping_value(raw.get("jobs"), f"{label} M SDK jobs")
        job = mapping_value(jobs.get(job_id), f"{label} M SDK job {job_id}")
        fields = (
            "soc",
            "board",
            "core",
            "core_role",
            "application",
            "build_configuration",
            "mode",
        )
        return {
            name if name != "mode" else "origin": str(job.get(name, ""))
            for name in fields
        }
    raise ToolError(f"{label} producer is not a supported public compile checklist")


def _required(definition: dict[str, Any], parameters: dict[str, str], label: str) -> tuple[bool, bool]:
    required = definition.get("required", False)
    if not isinstance(required, bool):
        raise ToolError(f"{label}.required must be boolean")
    condition = definition.get("required_when")
    if condition is None:
        return required, True
    matches = _condition_matches(condition, parameters, f"{label}.required_when")
    return matches, matches


def _validate_role(
    role: str,
    definition_value: Any,
    selected: dict[str, dict[str, str]],
    parameters: dict[str, str],
    label: str,
    *,
    artifact: bool,
) -> None:
    definition = mapping_value(definition_value, label)
    allowed = {"slot", "stage_to", "stage_pattern", "required", "required_when"}
    if artifact:
        allowed.add("producer_parameters")
    reject_unknown_keys(definition, allowed, label)
    required, allowed_now = _required(definition, parameters, label)
    entry = selected.get(role)
    if entry is None:
        if required:
            raise ToolError(f"input contract requires role {role}")
        return
    if not allowed_now:
        raise ToolError(f"input contract forbids role {role} for current parameters")
    slot = text_value(definition.get("slot"), f"{label}.slot")
    if entry["slot"] != slot:
        raise ToolError(f"input contract role {role} requires slot {slot}")
    stage_to = definition.get("stage_to")
    stage_pattern = definition.get("stage_pattern")
    if (stage_to is None) == (stage_pattern is None):
        raise ToolError(f"{label} must set exactly one of stage_to or stage_pattern")
    if stage_to is not None and entry["stage_to"] != str(stage_to):
        raise ToolError(
            f"input contract role {role} must stage to {stage_to}"
        )
    if stage_pattern is not None:
        try:
            matches = re.fullmatch(str(stage_pattern), entry["stage_to"])
        except re.error as exc:
            raise ToolError(f"{label}.stage_pattern is invalid: {exc}") from exc
        if matches is None:
            raise ToolError(
                f"input contract role {role} has an invalid stage destination"
            )
    if artifact:
        expected_parameters = mapping_value(
            definition.get("producer_parameters") or {},
            f"{label}.producer_parameters",
        )
        actual_parameters = _producer_parameters(entry, label)
        for name, expected in expected_parameters.items():
            if actual_parameters.get(name, "").casefold() != str(expected).casefold():
                raise ToolError(
                    f"input contract role {role} requires producer parameter "
                    f"{name}={expected}"
                )


def _selected_by_name(values: list[dict[str, str]], label: str) -> dict[str, dict[str, str]]:
    result = {entry["name"]: entry for entry in values}
    if len(result) != len(values):
        raise ToolError(f"{label} contains duplicate role names")
    return result


def validate_input_contract(
    contract_reference: dict[str, Any] | None,
    parameters: dict[str, str],
    inputs: dict[str, Any],
) -> None:
    if contract_reference is None:
        return
    path = Path(contract_reference["path"])
    raw = mapping_value(load_yaml(path, "project input contract"), "project input contract")
    if hash_data(raw) != contract_reference["hash"]:
        raise ToolError("project input contract changed after profile loading")
    reject_unknown_keys(raw, {"schema_version", "kind", "selectors", "recipes"}, "project input contract")
    if raw.get("schema_version") != 1 or raw.get("kind") != "project_input_matrix":
        raise ToolError("project input contract identity is invalid")
    selectors = raw.get("selectors")
    if selectors != contract_reference["selectors"]:
        raise ToolError("project input contract selectors do not match the profile")
    selected_contract: Any = raw.get("recipes")
    selector_values: list[str] = []
    for selector in selectors:
        value = parameters[selector]
        selector_values.append(value)
        selected_contract = mapping_value(
            selected_contract, "project input contract selector matrix"
        ).get(value)
        if selected_contract is None:
            raise ToolError(
                "unsupported project input combination: " + "/".join(selector_values)
            )
    contract = mapping_value(selected_contract, "selected project input contract")
    reject_unknown_keys(
        contract,
        {"artifacts", "files", "extra_file_slots", "relations"},
        "selected project input contract",
    )
    artifacts = _selected_by_name(inputs["artifacts"], "artifact inputs")
    files = _selected_by_name(inputs["files"], "file inputs")
    artifact_roles = mapping_value(contract.get("artifacts") or {}, "contract artifacts")
    file_roles = mapping_value(contract.get("files") or {}, "contract files")
    unknown_artifacts = sorted(set(artifacts) - set(artifact_roles))
    if unknown_artifacts:
        raise ToolError(
            "input contract has unknown artifact roles: " + ", ".join(unknown_artifacts)
        )
    for role, definition in artifact_roles.items():
        _validate_role(
            role,
            definition,
            artifacts,
            parameters,
            f"contract.artifacts.{role}",
            artifact=True,
        )
    extra_slots = mapping_value(
        contract.get("extra_file_slots") or {}, "contract.extra_file_slots"
    )
    unknown_files = sorted(
        name
        for name, entry in files.items()
        if name not in file_roles and entry["slot"] not in extra_slots
    )
    if unknown_files:
        raise ToolError("input contract has unknown file roles: " + ", ".join(unknown_files))
    for role, definition in file_roles.items():
        _validate_role(
            role,
            definition,
            files,
            parameters,
            f"contract.files.{role}",
            artifact=False,
        )
    for slot, definition_value in extra_slots.items():
        label = f"contract.extra_file_slots.{slot}"
        definition = mapping_value(definition_value, label)
        reject_unknown_keys(definition, {"stage_prefix", "minimum_when"}, label)
        prefix = text_value(definition.get("stage_prefix"), f"{label}.stage_prefix")
        selected = [
            entry for name, entry in files.items()
            if name not in file_roles and entry["slot"] == slot
        ]
        for entry in selected:
            if not entry["stage_to"].startswith(prefix):
                raise ToolError(
                    f"input contract file {entry['name']} must stage below {prefix}"
                )
        minimum = definition.get("minimum_when")
        if minimum is not None and _condition_matches(minimum, parameters, f"{label}.minimum_when"):
            count = mapping_value(minimum, f"{label}.minimum_when").get("count")
            if not isinstance(count, int) or count < 1:
                raise ToolError(f"{label}.minimum_when.count must be a positive integer")
            if len(selected) < count:
                raise ToolError(
                    f"input contract requires at least {count} files in slot {slot}"
                )
    relations = contract.get("relations") or []
    if not isinstance(relations, list):
        raise ToolError("contract.relations must be a list")
    for index, value in enumerate(relations, start=1):
        label = f"contract.relations[{index}]"
        relation = mapping_value(value, label)
        reject_unknown_keys(
            relation,
            {"when_artifact", "require_artifact", "producer_parameter", "equals"},
            label,
        )
        when = text_value(relation.get("when_artifact"), f"{label}.when_artifact")
        if when not in artifacts:
            continue
        required_role = text_value(
            relation.get("require_artifact"), f"{label}.require_artifact"
        )
        if required_role not in artifacts:
            raise ToolError(f"input contract relation requires artifact {required_role}")
        parameter = text_value(
            relation.get("producer_parameter"), f"{label}.producer_parameter"
        )
        expected = text_value(relation.get("equals"), f"{label}.equals")
        actual = _producer_parameters(artifacts[required_role], label).get(parameter)
        if actual is None or actual.casefold() != expected.casefold():
            raise ToolError(
                f"input contract relation requires {required_role} producer "
                f"parameter {parameter}={expected}"
            )


def validate_fixed_asset_contract(
    contract_reference: dict[str, Any] | None,
    parameters: dict[str, str],
    inputs: dict[str, Any],
) -> None:
    if contract_reference is None:
        return
    path = Path(contract_reference["path"])
    raw = mapping_value(load_yaml(path, "fixed asset contract"), "fixed asset contract")
    if hash_data(raw) != contract_reference["hash"]:
        raise ToolError("fixed asset contract changed after profile loading")
    reject_unknown_keys(
        raw,
        {"schema_version", "kind", "selectors", "assets"},
        "fixed asset contract",
    )
    if raw.get("schema_version") != 1 or raw.get("kind") != "project_fixed_asset_matrix":
        raise ToolError("fixed asset contract identity is invalid")
    selectors = raw.get("selectors")
    if selectors != contract_reference["selectors"]:
        raise ToolError("fixed asset contract selectors do not match the profile")
    selected_contract: Any = raw.get("assets")
    selector_values: list[str] = []
    for selector in selectors:
        value = parameters[selector]
        selector_values.append(value)
        selected_contract = mapping_value(
            selected_contract, "fixed asset selector matrix"
        ).get(value)
        if selected_contract is None:
            raise ToolError(
                "unsupported fixed asset combination: " + "/".join(selector_values)
            )
    contract = mapping_value(selected_contract, "selected fixed asset contract")
    reject_unknown_keys(contract, {"owned_slots", "files"}, "selected fixed asset contract")
    owned_slots = contract.get("owned_slots")
    if not isinstance(owned_slots, list) or not owned_slots or not all(
        isinstance(slot, str) and slot for slot in owned_slots
    ):
        raise ToolError("fixed asset contract owned_slots must be a non-empty string list")
    if len(owned_slots) != len(set(owned_slots)):
        raise ToolError("fixed asset contract owned_slots contains duplicates")
    definitions = mapping_value(contract.get("files") or {}, "fixed asset files")
    selected = {
        entry["name"]: entry
        for entry in inputs["files"]
        if entry["slot"] in owned_slots
    }
    missing = sorted(set(definitions) - set(selected))
    extra = sorted(set(selected) - set(definitions))
    if missing:
        raise ToolError("fixed asset contract requires roles: " + ", ".join(missing))
    if extra:
        raise ToolError("fixed asset contract has unknown roles: " + ", ".join(extra))
    for role, definition_value in definitions.items():
        label = f"fixed_asset.files.{role}"
        definition = mapping_value(definition_value, label)
        reject_unknown_keys(
            definition,
            {"slot", "stage_to", "sha256", "provenance"},
            label,
        )
        entry = selected[role]
        expected_slot = text_value(definition.get("slot"), f"{label}.slot")
        if entry["slot"] != expected_slot:
            raise ToolError(f"fixed asset role {role} requires slot {expected_slot}")
        expected_stage = text_value(
            definition.get("stage_to"), f"{label}.stage_to"
        )
        if entry["stage_to"] != expected_stage:
            raise ToolError(
                f"fixed asset role {role} must stage to {expected_stage}"
            )
        expected_hash = normalize_hash(
            text_value(definition.get("sha256"), f"{label}.sha256"),
            f"{label}.sha256",
        )
        actual_hash = hash_file(Path(entry["path"]))
        if actual_hash != expected_hash:
            raise ToolError(
                f"fixed asset role {role} content hash does not match its catalog entry"
            )
