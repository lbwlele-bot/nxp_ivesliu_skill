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
    run_command,
    text_value,
)


MAKE_ASSIGNMENT_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s*(?:[?:+]?=)\s*(.*?)\s*$"
)
MAKE_TARGET_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*?)\s*$")
MAKE_VARIABLE_RE = re.compile(r"\$\(([A-Za-z_][A-Za-z0-9_]*)\)")
M_IMAGE_RE = re.compile(r"^m(?:4(?:_[0-9]+)?|7[0-9]?|33s?)_image[.]bin$", re.IGNORECASE)


def _logical_make_lines(text: str) -> list[str]:
    result: list[str] = []
    pending = ""
    for raw in text.splitlines():
        if raw.startswith("\t"):
            continue
        line = raw.split("#", 1)[0].rstrip()
        if not line and not pending:
            continue
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        result.append((pending + line).strip())
        pending = ""
    if pending.strip():
        result.append(pending.strip())
    return result


def _expand_make_variables(value: str, variables: dict[str, str]) -> str:
    result = value
    for _ in range(32):
        expanded = MAKE_VARIABLE_RE.sub(
            lambda match: variables.get(match.group(1), match.group(0)), result
        )
        if expanded == result:
            return result
        result = expanded
    raise ToolError("soc.mak variable expansion is recursive")


def make_recipe_m_images(text: str, recipe: str) -> list[str]:
    """Return M image prerequisites from a make target without running Make."""
    variables: dict[str, str] = {}
    targets: dict[str, list[str]] = {}
    for line in _logical_make_lines(text):
        assignment = MAKE_ASSIGNMENT_RE.fullmatch(line)
        if assignment:
            variables[assignment.group(1)] = assignment.group(2)
            continue
        target = MAKE_TARGET_RE.fullmatch(line)
        if target:
            targets[target.group(1)] = target.group(2).split()
    if recipe not in targets:
        raise ToolError(f"soc.mak does not define recipe target: {recipe}")

    images: set[str] = set()
    visited: set[str] = set()

    def walk(target: str) -> None:
        if target in visited:
            return
        visited.add(target)
        for raw_dependency in targets.get(target, []):
            dependency = _expand_make_variables(raw_dependency, variables)
            if dependency in targets:
                walk(dependency)
                continue
            name = Path(dependency).name
            if M_IMAGE_RE.fullmatch(name):
                images.add(name)

    walk(recipe)
    return sorted(images)


def _soc_makefile_at_ref(source_root: Path, source_ref: str, soc: str) -> tuple[str, str]:
    relative = f"{soc}/soc.mak"
    if (source_root / ".git").exists():
        result = run_command(
            ["git", "-C", str(source_root), "show", f"{source_ref}:{relative}"],
            cwd=source_root,
        )
        text = result.stdout.decode("utf-8", errors="replace")
    else:
        path = source_root / relative
        if not path.is_file():
            raise ToolError(f"mkimage recipe source is unavailable: {path}")
        text = path.read_text(encoding="utf-8")
    return relative, text


def validate_make_recipe_m_payloads(
    contract: dict[str, Any] | None,
    *,
    source_root: Path,
    source_ref: str,
    parameters: dict[str, str],
    inputs: dict[str, Any],
) -> dict[str, Any] | None:
    if contract is None:
        return None
    soc = parameters[contract["soc_parameter"]]
    recipe = parameters[contract["recipe_parameter"]]
    relative, text = _soc_makefile_at_ref(source_root, source_ref, soc)
    candidates = make_recipe_m_images(text, recipe)
    slot = contract["m_payload_slot"]
    claimed_elsewhere = {
        Path(entry["stage_to"]).name
        for entry in [*inputs["artifacts"], *inputs["files"]]
        if entry["slot"] != slot
    }
    required_files = [name for name in candidates if name not in claimed_elsewhere]
    required_destinations = {f"{soc}/{name}": name for name in required_files}
    selected = {
        entry["stage_to"]: entry
        for entry in inputs["artifacts"]
        if entry["slot"] == slot
    }
    missing = sorted(set(required_destinations) - set(selected))
    extra = sorted(set(selected) - set(required_destinations))
    if missing:
        raise ToolError(
            f"soc.mak recipe {soc}/{recipe} requires M payloads: "
            + ", ".join(missing)
        )
    if extra:
        raise ToolError(
            f"soc.mak recipe {soc}/{recipe} does not consume M payloads: "
            + ", ".join(extra)
        )
    expected_soc = contract["soc_identity_overrides"].get(soc, soc.casefold())
    identities: dict[str, dict[str, str]] = {}
    for destination, filename in required_destinations.items():
        role = filename.removesuffix("_image.bin").casefold()
        entry = selected[destination]
        actual = _producer_parameters(entry, f"soc.mak M payload {destination}")
        for name, expected in {"soc": expected_soc, "core_role": role}.items():
            if actual.get(name, "").casefold() != expected.casefold():
                raise ToolError(
                    f"soc.mak M payload {destination} requires producer parameter "
                    f"{name}={expected}"
                )
        identities[destination] = {"soc": expected_soc, "core_role": role}
    return {
        "source": relative,
        "source_hash": hash_data(text),
        "soc": soc,
        "recipe": recipe,
        "required_m_payloads": required_destinations,
        "identities": identities,
    }


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
    *,
    dynamic_artifact_slots: set[str] | None = None,
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
    dynamic_slots = dynamic_artifact_slots or set()
    unknown_artifacts = sorted(
        name
        for name, entry in artifacts.items()
        if name not in artifact_roles and entry["slot"] not in dynamic_slots
    )
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
