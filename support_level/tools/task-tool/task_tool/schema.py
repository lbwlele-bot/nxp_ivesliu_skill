from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .common import (
    HASH_RE,
    NXP_ROOT,
    SUPPORT_ROOT,
    WORKSPACE_ROOT,
    ToolError,
    hash_data,
    identifier,
    integer,
    json_value,
    mapping,
    reject_unknown,
    relative_path,
    require_keys,
    sequence,
    text,
)


OWNERS = {"understanding", "support", "compile", "board-exec"}
TASK_STATUSES = {"active", "blocked", "completed", "abandoned"}
CRITERION_STATUSES = {"pending", "passed", "waived"}
FACT_KINDS = {"user_confirmed", "tool_generated", "observed", "derived"}
VALIDITIES = {
    "case",
    "until_source_change",
    "until_board_change",
    "point_in_time",
}
REF_SCOPES = {"case", "workspace", "support"}
DEPLOYMENT_STATUSES = {
    "not_required",
    "preparing",
    "ready",
    "consumed",
    "verified",
}


def _enum(value: Any, allowed: set[str], label: str) -> str:
    result = text(value, label)
    if result not in allowed:
        raise ToolError(
            f"{label} must be one of {', '.join(sorted(allowed))}: {result!r}"
        )
    return result


def _text_list(value: Any, label: str) -> list[str]:
    return [
        text(item, f"{label}[{index}]")
        for index, item in enumerate(sequence(value, label))
    ]


def _unique_ids(items: list[dict[str, Any]], label: str) -> set[str]:
    found: set[str] = set()
    for index, item in enumerate(items):
        item_id = identifier(item.get("id"), f"{label}[{index}].id")
        if item_id in found:
            raise ToolError(f"{label} contains duplicate id: {item_id}")
        found.add(item_id)
    return found


def _resolve_reference(
    reference: dict[str, Any], case_root: Path, label: str
) -> Path:
    reject_unknown(reference, {"scope", "path", "purpose"}, label)
    require_keys(reference, {"scope", "path"}, label)
    scope = _enum(reference["scope"], REF_SCOPES, f"{label}.scope")
    path_value = relative_path(reference["path"], f"{label}.path")
    if "purpose" in reference:
        text(reference["purpose"], f"{label}.purpose")
    roots = {
        "case": case_root,
        "workspace": WORKSPACE_ROOT,
        "support": SUPPORT_ROOT,
    }
    return roots[scope] / path_value


def validate_reference(
    value: Any,
    case_root: Path,
    label: str,
    *,
    purpose_required: bool = False,
    must_exist: bool = True,
) -> dict[str, Any]:
    reference = mapping(value, label)
    resolved = _resolve_reference(reference, case_root, label)
    if purpose_required:
        text(reference.get("purpose"), f"{label}.purpose")
    if must_exist and not resolved.exists():
        raise ToolError(f"{label} does not exist: {resolved}")
    return reference


def _validate_criteria(
    value: Any, case_root: Path
) -> tuple[list[dict[str, Any]], set[str]]:
    criteria = [
        mapping(item, f"task.success_criteria[{index}]")
        for index, item in enumerate(
            sequence(value, "task.success_criteria")
        )
    ]
    ids = _unique_ids(criteria, "task.success_criteria")
    if not criteria:
        raise ToolError("task.success_criteria must not be empty")
    for index, criterion in enumerate(criteria):
        label = f"task.success_criteria[{index}]"
        reject_unknown(criterion, {"id", "statement", "status", "evidence"}, label)
        require_keys(criterion, {"id", "statement", "status", "evidence"}, label)
        text(criterion["statement"], f"{label}.statement")
        _enum(criterion["status"], CRITERION_STATUSES, f"{label}.status")
        evidence = sequence(criterion["evidence"], f"{label}.evidence")
        for ref_index, reference in enumerate(evidence):
            validate_reference(
                reference,
                case_root,
                f"{label}.evidence[{ref_index}]",
            )
        if criterion["status"] in {"passed", "waived"} and not evidence:
            raise ToolError(f"{label}.evidence is required for {criterion['status']}")
    return criteria, ids


def _validate_working_set(value: Any, case_root: Path) -> None:
    items = sequence(value, "context.working_set")
    if len(items) > 12:
        raise ToolError("context.working_set must contain at most 12 references")
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(items):
        reference = validate_reference(
            item,
            case_root,
            f"context.working_set[{index}]",
            purpose_required=True,
        )
        key = (reference["scope"], reference["path"])
        if key in seen:
            raise ToolError(f"context.working_set contains duplicate reference: {key}")
        seen.add(key)


def _validate_facts(
    value: Any, case_root: Path
) -> tuple[list[dict[str, Any]], set[str]]:
    facts = [
        mapping(item, f"context.verified_facts[{index}]")
        for index, item in enumerate(
            sequence(value, "context.verified_facts")
        )
    ]
    ids = _unique_ids(facts, "context.verified_facts")
    for index, fact in enumerate(facts):
        label = f"context.verified_facts[{index}]"
        allowed = {
            "id",
            "kind",
            "value",
            "scope",
            "owner",
            "evidence",
            "observed_at",
            "validity",
            "based_on",
        }
        reject_unknown(fact, allowed, label)
        require_keys(fact, allowed, label)
        kind = _enum(fact["kind"], FACT_KINDS, f"{label}.kind")
        json_value(fact["value"], f"{label}.value")
        text(fact["scope"], f"{label}.scope")
        _enum(fact["owner"], OWNERS, f"{label}.owner")
        text(fact["observed_at"], f"{label}.observed_at")
        _enum(fact["validity"], VALIDITIES, f"{label}.validity")
        evidence = sequence(fact["evidence"], f"{label}.evidence")
        if not evidence:
            raise ToolError(f"{label}.evidence must not be empty")
        for ref_index, reference in enumerate(evidence):
            validate_reference(
                reference,
                case_root,
                f"{label}.evidence[{ref_index}]",
            )
        based_on = [
            identifier(item, f"{label}.based_on[{item_index}]")
            for item_index, item in enumerate(
                sequence(fact["based_on"], f"{label}.based_on")
            )
        ]
        if kind == "derived" and not based_on:
            raise ToolError(f"{label}.based_on is required for derived facts")
        if kind != "derived" and based_on:
            raise ToolError(f"{label}.based_on is only allowed for derived facts")
    for index, fact in enumerate(facts):
        for dependency in fact["based_on"]:
            if dependency not in ids:
                raise ToolError(
                    f"context.verified_facts[{index}].based_on references "
                    f"unknown fact: {dependency}"
                )
    return facts, ids


def _validate_assumptions(value: Any) -> tuple[list[dict[str, Any]], set[str]]:
    assumptions = [
        mapping(item, f"context.assumptions[{index}]")
        for index, item in enumerate(sequence(value, "context.assumptions"))
    ]
    ids = _unique_ids(assumptions, "context.assumptions")
    for index, assumption in enumerate(assumptions):
        label = f"context.assumptions[{index}]"
        allowed = {"id", "statement", "owner", "impact", "validation"}
        reject_unknown(assumption, allowed, label)
        require_keys(assumption, allowed, label)
        text(assumption["statement"], f"{label}.statement")
        _enum(assumption["owner"], OWNERS, f"{label}.owner")
        text(assumption["impact"], f"{label}.impact")
        text(assumption["validation"], f"{label}.validation")
    return assumptions, ids


def _validate_questions(value: Any) -> tuple[list[dict[str, Any]], set[str]]:
    questions = [
        mapping(item, f"context.open_questions[{index}]")
        for index, item in enumerate(sequence(value, "context.open_questions"))
    ]
    ids = _unique_ids(questions, "context.open_questions")
    for index, question in enumerate(questions):
        label = f"context.open_questions[{index}]"
        allowed = {"id", "question", "owner", "blocks"}
        reject_unknown(question, allowed, label)
        require_keys(question, allowed, label)
        text(question["question"], f"{label}.question")
        _enum(question["owner"], OWNERS, f"{label}.owner")
        _text_list(question["blocks"], f"{label}.blocks")
    return questions, ids


def _validate_conflicts(
    value: Any, case_root: Path
) -> tuple[list[dict[str, Any]], set[str]]:
    conflicts = [
        mapping(item, f"context.conflicts[{index}]")
        for index, item in enumerate(sequence(value, "context.conflicts"))
    ]
    ids = _unique_ids(conflicts, "context.conflicts")
    for index, conflict in enumerate(conflicts):
        label = f"context.conflicts[{index}]"
        allowed = {
            "id",
            "subject",
            "owner",
            "candidates",
            "blocks",
            "next_probe",
        }
        reject_unknown(conflict, allowed, label)
        require_keys(conflict, allowed, label)
        text(conflict["subject"], f"{label}.subject")
        _enum(conflict["owner"], OWNERS, f"{label}.owner")
        candidates = [
            mapping(item, f"{label}.candidates[{candidate_index}]")
            for candidate_index, item in enumerate(
                sequence(conflict["candidates"], f"{label}.candidates")
            )
        ]
        if len(candidates) < 2:
            raise ToolError(f"{label}.candidates must contain at least two values")
        for candidate_index, candidate in enumerate(candidates):
            candidate_label = f"{label}.candidates[{candidate_index}]"
            reject_unknown(candidate, {"value", "evidence"}, candidate_label)
            require_keys(candidate, {"value", "evidence"}, candidate_label)
            json_value(candidate["value"], f"{candidate_label}.value")
            evidence = sequence(
                candidate["evidence"], f"{candidate_label}.evidence"
            )
            if not evidence:
                raise ToolError(f"{candidate_label}.evidence must not be empty")
            for ref_index, reference in enumerate(evidence):
                validate_reference(
                    reference,
                    case_root,
                    f"{candidate_label}.evidence[{ref_index}]",
                )
        _text_list(conflict["blocks"], f"{label}.blocks")
        text(conflict["next_probe"], f"{label}.next_probe")
    return conflicts, ids


def _validate_context(
    value: Any, case_root: Path
) -> tuple[set[str], set[str]]:
    context = mapping(value, "context")
    allowed = {
        "working_set",
        "verified_facts",
        "assumptions",
        "open_questions",
        "conflicts",
    }
    reject_unknown(context, allowed, "context")
    require_keys(context, allowed, "context")
    _validate_working_set(context["working_set"], case_root)
    _, fact_ids = _validate_facts(context["verified_facts"], case_root)
    _, assumption_ids = _validate_assumptions(context["assumptions"])
    _, question_ids = _validate_questions(context["open_questions"])
    _, conflict_ids = _validate_conflicts(context["conflicts"], case_root)
    contextual_ids = assumption_ids | question_ids | conflict_ids
    if len(contextual_ids) != (
        len(assumption_ids) + len(question_ids) + len(conflict_ids)
    ):
        raise ToolError(
            "assumptions, open_questions, and conflicts must use distinct ids"
        )
    if fact_ids & contextual_ids:
        duplicate = sorted(fact_ids & contextual_ids)[0]
        raise ToolError(f"context ids must be globally unique: {duplicate}")
    return fact_ids, contextual_ids


def _validate_software(value: Any, case_root: Path) -> None:
    software = mapping(value, "software")
    reject_unknown(software, {"state_ref", "required_targets"}, "software")
    require_keys(software, {"state_ref", "required_targets"}, "software")
    if software["state_ref"] is not None:
        reference = validate_reference(
            software["state_ref"], case_root, "software.state_ref"
        )
        if reference["scope"] != "case":
            raise ToolError("software.state_ref must use scope: case")
    _text_list(software["required_targets"], "software.required_targets")


def _validate_deployment(value: Any, case_root: Path, software: dict[str, Any]) -> None:
    deployment = mapping(value, "deployment")
    allowed = {
        "status",
        "producer",
        "consumer",
        "set_id",
        "artifacts",
        "preconditions",
        "verification_focus",
    }
    reject_unknown(deployment, allowed, "deployment")
    require_keys(deployment, allowed, "deployment")
    status = _enum(
        deployment["status"], DEPLOYMENT_STATUSES, "deployment.status"
    )
    if deployment["producer"] is not None:
        _enum(deployment["producer"], OWNERS, "deployment.producer")
    if deployment["consumer"] is not None:
        _enum(deployment["consumer"], OWNERS, "deployment.consumer")
    if deployment["set_id"] is not None:
        identifier(deployment["set_id"], "deployment.set_id")
    artifacts = [
        mapping(item, f"deployment.artifacts[{index}]")
        for index, item in enumerate(
            sequence(deployment["artifacts"], "deployment.artifacts")
        )
    ]
    artifact_ids = _unique_ids(artifacts, "deployment.artifacts")
    for index, artifact in enumerate(artifacts):
        label = f"deployment.artifacts[{index}]"
        allowed_artifact = {
            "id",
            "path",
            "identity",
            "consumption",
            "embedded_in",
        }
        reject_unknown(artifact, allowed_artifact, label)
        require_keys(artifact, allowed_artifact, label)
        artifact_path = relative_path(artifact["path"], f"{label}.path")
        if status in {"ready", "consumed", "verified"}:
            resolved = case_root / artifact_path
            if not resolved.is_file():
                raise ToolError(f"{label}.path is not a file: {resolved}")
        identity = mapping(artifact["identity"], f"{label}.identity")
        reject_unknown(identity, {"kind", "locator", "ref"}, f"{label}.identity")
        require_keys(identity, {"kind"}, f"{label}.identity")
        identity_kind = _enum(
            identity["kind"], {"software_state", "evidence"}, f"{label}.identity.kind"
        )
        if identity_kind == "software_state":
            if software["state_ref"] is None:
                raise ToolError(
                    f"{label}.identity requires software.state_ref"
                )
            text(identity.get("locator"), f"{label}.identity.locator")
            if "ref" in identity:
                raise ToolError(
                    f"{label}.identity.ref is not allowed for software_state"
                )
        else:
            if "locator" in identity:
                raise ToolError(
                    f"{label}.identity.locator is not allowed for evidence"
                )
            validate_reference(
                identity.get("ref"),
                case_root,
                f"{label}.identity.ref",
            )
        consumption = mapping(
            artifact["consumption"], f"{label}.consumption"
        )
        reject_unknown(
            consumption, {"method", "target"}, f"{label}.consumption"
        )
        require_keys(
            consumption, {"method", "target"}, f"{label}.consumption"
        )
        text(consumption["method"], f"{label}.consumption.method")
        text(consumption["target"], f"{label}.consumption.target")
        embedded_in = artifact["embedded_in"]
        if embedded_in is not None:
            embedded_id = identifier(embedded_in, f"{label}.embedded_in")
            if embedded_id not in artifact_ids:
                raise ToolError(
                    f"{label}.embedded_in references unknown artifact: {embedded_id}"
                )
            if embedded_id == artifact["id"]:
                raise ToolError(f"{label}.embedded_in cannot reference itself")
    _text_list(deployment["preconditions"], "deployment.preconditions")
    _text_list(
        deployment["verification_focus"], "deployment.verification_focus"
    )
    if status == "not_required":
        if any(
            [
                deployment["producer"] is not None,
                deployment["consumer"] is not None,
                deployment["set_id"] is not None,
                artifacts,
                deployment["preconditions"],
                deployment["verification_focus"],
            ]
        ):
            raise ToolError("deployment not_required must not carry deployment data")
        return
    if deployment["producer"] != "compile":
        raise ToolError("deployment.producer must be compile")
    if deployment["consumer"] != "board-exec":
        raise ToolError("deployment.consumer must be board-exec")
    identifier(deployment["set_id"], "deployment.set_id")
    if status in {"ready", "consumed", "verified"}:
        if not artifacts:
            raise ToolError(f"deployment.artifacts is required for {status}")
        if not deployment["verification_focus"]:
            raise ToolError(
                f"deployment.verification_focus is required for {status}"
            )


def validate_state(
    value: Any,
    case_root: Path,
    *,
    verify_integrity: bool = True,
) -> dict[str, Any]:
    state = mapping(value, "task state")
    allowed = {
        "schema_version",
        "case_id",
        "revision",
        "created_at",
        "updated_at",
        "updated_by",
        "task",
        "current",
        "context",
        "software",
        "deployment",
        "integrity_hash",
    }
    reject_unknown(state, allowed, "task state")
    require_keys(state, allowed, "task state")
    if state["schema_version"] != 1:
        raise ToolError("task state schema_version must be 1")
    if text(state["case_id"], "case_id") != case_root.name:
        raise ToolError(
            f"case_id must match case directory name: {case_root.name}"
        )
    integer(state["revision"], "revision", minimum=1)
    text(state["created_at"], "created_at")
    text(state["updated_at"], "updated_at")
    _enum(state["updated_by"], OWNERS, "updated_by")

    task = mapping(state["task"], "task")
    task_allowed = {"status", "objective", "success_criteria", "scope", "constraints"}
    reject_unknown(task, task_allowed, "task")
    require_keys(task, task_allowed, "task")
    status = _enum(task["status"], TASK_STATUSES, "task.status")
    text(task["objective"], "task.objective")
    criteria, _ = _validate_criteria(task["success_criteria"], case_root)
    scope = mapping(task["scope"], "task.scope")
    reject_unknown(scope, {"in", "out"}, "task.scope")
    require_keys(scope, {"in", "out"}, "task.scope")
    _text_list(scope["in"], "task.scope.in")
    _text_list(scope["out"], "task.scope.out")
    _text_list(task["constraints"], "task.constraints")

    current = mapping(state["current"], "current")
    current_allowed = {
        "owner",
        "unresolved_step",
        "fact_summary",
        "blockers",
        "next_action",
    }
    reject_unknown(current, current_allowed, "current")
    require_keys(current, current_allowed, "current")
    _enum(current["owner"], OWNERS, "current.owner")
    text(current["unresolved_step"], "current.unresolved_step")
    text(current["fact_summary"], "current.fact_summary")
    blockers = [
        identifier(item, f"current.blockers[{index}]")
        for index, item in enumerate(
            sequence(current["blockers"], "current.blockers")
        )
    ]
    text(current["next_action"], "current.next_action")

    _, contextual_ids = _validate_context(state["context"], case_root)
    unknown_blockers = sorted(set(blockers) - contextual_ids)
    if unknown_blockers:
        raise ToolError(
            "current.blockers references unknown context ids: "
            + ", ".join(unknown_blockers)
        )
    if status == "blocked" and not blockers:
        raise ToolError("blocked task must have current.blockers")
    if status == "completed":
        if blockers:
            raise ToolError("completed task must not have blockers")
        incomplete = [
            item["id"]
            for item in criteria
            if item["status"] not in {"passed", "waived"}
        ]
        if incomplete:
            raise ToolError(
                "completed task has incomplete criteria: " + ", ".join(incomplete)
            )
        if state["context"]["conflicts"]:
            raise ToolError("completed task must not have unresolved conflicts")

    software = mapping(state["software"], "software")
    _validate_software(software, case_root)
    _validate_deployment(state["deployment"], case_root, software)

    integrity = text(state["integrity_hash"], "integrity_hash")
    if not HASH_RE.fullmatch(integrity):
        raise ToolError("integrity_hash must be sha256:<64 lowercase hex>")
    if verify_integrity:
        payload = deepcopy(state)
        payload.pop("integrity_hash")
        expected = hash_data(payload)
        if integrity != expected:
            raise ToolError(
                f"task state integrity mismatch: expected {expected}, got {integrity}"
            )
    return state


def add_integrity(value: dict[str, Any]) -> dict[str, Any]:
    state = deepcopy(value)
    state.pop("integrity_hash", None)
    state["integrity_hash"] = hash_data(state)
    return state
