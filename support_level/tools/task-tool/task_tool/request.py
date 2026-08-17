from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .common import (
    ToolError,
    identifier,
    integer,
    load_yaml,
    mapping,
    reject_unknown,
    require_keys,
    resolve_case_root,
    sequence,
    text,
    timestamp_now,
)
from .schema import (
    OWNERS,
    add_integrity,
    validate_reference,
    validate_state,
)


INIT_KEYS = {
    "schema_version",
    "case_root",
    "actor",
    "objective",
    "success_criteria",
    "scope",
    "constraints",
    "unresolved_step",
    "next_action",
}
UPDATE_KEYS = {
    "schema_version",
    "case_root",
    "expected_revision",
    "actor",
    "reason",
    "operations",
}


def _owner(value: Any, label: str) -> str:
    result = text(value, label)
    if result not in OWNERS:
        raise ToolError(
            f"{label} must be one of {', '.join(sorted(OWNERS))}: {result!r}"
        )
    return result


def load_init_request(path: Path) -> tuple[dict[str, Any], Path]:
    request = mapping(load_yaml(path, "init request"), "init request")
    reject_unknown(request, INIT_KEYS, "init request")
    require_keys(request, INIT_KEYS, "init request")
    if request["schema_version"] != 1:
        raise ToolError("init request schema_version must be 1")
    case_root = resolve_case_root(request["case_root"])
    actor = _owner(request["actor"], "actor")
    if actor not in {"understanding", "support"}:
        raise ToolError("init actor must be understanding or support")
    text(request["objective"], "objective")
    criteria = sequence(request["success_criteria"], "success_criteria")
    if not criteria:
        raise ToolError("success_criteria must not be empty")
    seen: set[str] = set()
    for index, item in enumerate(criteria):
        criterion = mapping(item, f"success_criteria[{index}]")
        reject_unknown(criterion, {"id", "statement"}, f"success_criteria[{index}]")
        require_keys(criterion, {"id", "statement"}, f"success_criteria[{index}]")
        criterion_id = identifier(criterion["id"], f"success_criteria[{index}].id")
        if criterion_id in seen:
            raise ToolError(f"duplicate success criterion id: {criterion_id}")
        seen.add(criterion_id)
        text(criterion["statement"], f"success_criteria[{index}].statement")
    scope = mapping(request["scope"], "scope")
    reject_unknown(scope, {"in", "out"}, "scope")
    require_keys(scope, {"in", "out"}, "scope")
    for name in ("in", "out"):
        for index, item in enumerate(sequence(scope[name], f"scope.{name}")):
            text(item, f"scope.{name}[{index}]")
    for index, item in enumerate(sequence(request["constraints"], "constraints")):
        text(item, f"constraints[{index}]")
    text(request["unresolved_step"], "unresolved_step")
    text(request["next_action"], "next_action")
    return request, case_root


def build_initial_state(request: dict[str, Any], case_root: Path) -> dict[str, Any]:
    now = timestamp_now()
    actor = request["actor"]
    state = {
        "schema_version": 1,
        "case_id": case_root.name,
        "revision": 1,
        "created_at": now,
        "updated_at": now,
        "updated_by": actor,
        "task": {
            "status": "active",
            "objective": request["objective"].strip(),
            "success_criteria": [
                {
                    "id": item["id"],
                    "statement": item["statement"].strip(),
                    "status": "pending",
                    "evidence": [],
                }
                for item in request["success_criteria"]
            ],
            "scope": {
                "in": [item.strip() for item in request["scope"]["in"]],
                "out": [item.strip() for item in request["scope"]["out"]],
            },
            "constraints": [item.strip() for item in request["constraints"]],
        },
        "current": {
            "owner": actor,
            "unresolved_step": request["unresolved_step"].strip(),
            "fact_summary": "尚未建立当前步骤的已验证事实摘要",
            "blockers": [],
            "next_action": request["next_action"].strip(),
        },
        "context": {
            "working_set": [
                {
                    "scope": "case",
                    "path": "README.md",
                    "purpose": "case 目标、过程和交付入口",
                }
            ],
            "verified_facts": [],
            "assumptions": [],
            "open_questions": [],
            "conflicts": [],
        },
        "software": {
            "state_ref": None,
            "required_targets": [],
        },
        "deployment": {
            "status": "not_required",
            "producer": None,
            "consumer": None,
            "set_id": None,
            "artifacts": [],
            "preconditions": [],
            "verification_focus": [],
        },
    }
    state = add_integrity(state)
    validate_state(state, case_root)
    return state


def load_update_request(path: Path) -> tuple[dict[str, Any], Path]:
    request = mapping(load_yaml(path, "update request"), "update request")
    reject_unknown(request, UPDATE_KEYS, "update request")
    require_keys(request, UPDATE_KEYS, "update request")
    if request["schema_version"] != 1:
        raise ToolError("update request schema_version must be 1")
    case_root = resolve_case_root(request["case_root"])
    integer(request["expected_revision"], "expected_revision", minimum=1)
    _owner(request["actor"], "actor")
    text(request["reason"], "reason")
    operations = sequence(request["operations"], "operations")
    if not operations:
        raise ToolError("operations must not be empty")
    for index, item in enumerate(operations):
        operation = mapping(item, f"operations[{index}]")
        text(operation.get("op"), f"operations[{index}].op")
    return request, case_root


def _find(items: list[dict[str, Any]], item_id: str) -> int | None:
    for index, item in enumerate(items):
        if item["id"] == item_id:
            return index
    return None


def _actor_is(request: dict[str, Any], expected: str, operation: str) -> None:
    if request["actor"] != expected:
        raise ToolError(f"{operation} requires actor: {expected}")


def _set_task(state: dict[str, Any], operation: dict[str, Any], actor: str) -> None:
    if actor != "understanding":
        raise ToolError("set_task requires actor: understanding")
    allowed = {"op", "objective", "scope", "constraints"}
    reject_unknown(operation, allowed, "set_task")
    if set(operation) == {"op"}:
        raise ToolError("set_task must change at least one field")
    if "objective" in operation:
        state["task"]["objective"] = text(operation["objective"], "set_task.objective")
    if "scope" in operation:
        scope = mapping(operation["scope"], "set_task.scope")
        reject_unknown(scope, {"in", "out"}, "set_task.scope")
        require_keys(scope, {"in", "out"}, "set_task.scope")
        state["task"]["scope"] = {
            name: [
                text(item, f"set_task.scope.{name}[{index}]")
                for index, item in enumerate(
                    sequence(scope[name], f"set_task.scope.{name}")
                )
            ]
            for name in ("in", "out")
        }
    if "constraints" in operation:
        state["task"]["constraints"] = [
            text(item, f"set_task.constraints[{index}]")
            for index, item in enumerate(
                sequence(operation["constraints"], "set_task.constraints")
            )
        ]


def _set_current(state: dict[str, Any], operation: dict[str, Any]) -> None:
    allowed = {
        "op",
        "unresolved_step",
        "fact_summary",
        "blockers",
        "next_action",
    }
    reject_unknown(operation, allowed, "set_current")
    require_keys(operation, allowed, "set_current")
    state["current"].update(
        {
            "unresolved_step": text(
                operation["unresolved_step"], "set_current.unresolved_step"
            ),
            "fact_summary": text(
                operation["fact_summary"], "set_current.fact_summary"
            ),
            "blockers": [
                identifier(item, f"set_current.blockers[{index}]")
                for index, item in enumerate(
                    sequence(operation["blockers"], "set_current.blockers")
                )
            ],
            "next_action": text(
                operation["next_action"], "set_current.next_action"
            ),
        }
    )


def _set_criterion(
    state: dict[str, Any],
    operation: dict[str, Any],
    actor: str,
    case_root: Path,
) -> None:
    allowed = {"op", "id", "status", "evidence"}
    reject_unknown(operation, allowed, "set_criterion")
    require_keys(operation, allowed, "set_criterion")
    criterion_id = identifier(operation["id"], "set_criterion.id")
    index = _find(state["task"]["success_criteria"], criterion_id)
    if index is None:
        raise ToolError(f"unknown success criterion: {criterion_id}")
    status = text(operation["status"], "set_criterion.status")
    if status not in {"pending", "passed", "waived"}:
        raise ToolError("set_criterion.status must be pending, passed, or waived")
    if status == "waived" and actor != "understanding":
        raise ToolError("waiving a criterion requires actor: understanding")
    evidence = sequence(operation["evidence"], "set_criterion.evidence")
    for ref_index, reference in enumerate(evidence):
        validate_reference(
            reference,
            case_root,
            f"set_criterion.evidence[{ref_index}]",
        )
    if status in {"passed", "waived"} and not evidence:
        raise ToolError(f"set_criterion.evidence is required for {status}")
    state["task"]["success_criteria"][index]["status"] = status
    state["task"]["success_criteria"][index]["evidence"] = deepcopy(evidence)


def _upsert_fact(
    state: dict[str, Any],
    operation: dict[str, Any],
    actor: str,
) -> None:
    reject_unknown(operation, {"op", "fact"}, "upsert_verified_fact")
    require_keys(operation, {"op", "fact"}, "upsert_verified_fact")
    fact = mapping(operation["fact"], "upsert_verified_fact.fact")
    fact_id = identifier(fact.get("id"), "upsert_verified_fact.fact.id")
    if fact.get("owner") != actor:
        raise ToolError("verified fact owner must match update actor")
    index = _find(state["context"]["verified_facts"], fact_id)
    if index is not None:
        previous = state["context"]["verified_facts"][index]
        if previous["owner"] != actor:
            raise ToolError(
                f"fact {fact_id} belongs to {previous['owner']}; raise a conflict"
            )
        state["context"]["verified_facts"][index] = deepcopy(fact)
    else:
        state["context"]["verified_facts"].append(deepcopy(fact))


def _remove_fact(
    state: dict[str, Any], operation: dict[str, Any], actor: str
) -> None:
    reject_unknown(operation, {"op", "id"}, "remove_verified_fact")
    require_keys(operation, {"op", "id"}, "remove_verified_fact")
    fact_id = identifier(operation["id"], "remove_verified_fact.id")
    index = _find(state["context"]["verified_facts"], fact_id)
    if index is None:
        raise ToolError(f"unknown verified fact: {fact_id}")
    fact = state["context"]["verified_facts"][index]
    if fact["owner"] != actor:
        raise ToolError(f"fact {fact_id} belongs to {fact['owner']}")
    dependents = [
        item["id"]
        for item in state["context"]["verified_facts"]
        if fact_id in item["based_on"]
    ]
    if dependents:
        raise ToolError(
            f"fact {fact_id} is used by derived facts: {', '.join(dependents)}"
        )
    del state["context"]["verified_facts"][index]


def _add_context_item(
    state: dict[str, Any],
    operation: dict[str, Any],
    actor: str,
    *,
    operation_name: str,
    field: str,
    item_key: str,
) -> None:
    reject_unknown(operation, {"op", item_key}, operation_name)
    require_keys(operation, {"op", item_key}, operation_name)
    item = mapping(operation[item_key], f"{operation_name}.{item_key}")
    item_id = identifier(item.get("id"), f"{operation_name}.{item_key}.id")
    if item.get("owner") != actor:
        raise ToolError(f"{operation_name} owner must match update actor")
    all_ids = {
        existing["id"]
        for name in (
            "verified_facts",
            "assumptions",
            "open_questions",
            "conflicts",
        )
        for existing in state["context"][name]
    }
    if item_id in all_ids:
        raise ToolError(f"context id already exists: {item_id}")
    state["context"][field].append(deepcopy(item))


def _resolve_context_item(
    state: dict[str, Any],
    operation: dict[str, Any],
    *,
    operation_name: str,
    field: str,
) -> None:
    reject_unknown(operation, {"op", "id", "resolved_by_fact"}, operation_name)
    require_keys(operation, {"op", "id", "resolved_by_fact"}, operation_name)
    item_id = identifier(operation["id"], f"{operation_name}.id")
    fact_id = identifier(
        operation["resolved_by_fact"], f"{operation_name}.resolved_by_fact"
    )
    if _find(state["context"]["verified_facts"], fact_id) is None:
        raise ToolError(
            f"{operation_name}.resolved_by_fact is unknown: {fact_id}"
        )
    index = _find(state["context"][field], item_id)
    if index is None:
        raise ToolError(f"{operation_name} references unknown id: {item_id}")
    del state["context"][field][index]
    state["current"]["blockers"] = [
        blocker
        for blocker in state["current"]["blockers"]
        if blocker != item_id
    ]


def _set_working_set(
    state: dict[str, Any], operation: dict[str, Any]
) -> None:
    reject_unknown(operation, {"op", "items"}, "set_working_set")
    require_keys(operation, {"op", "items"}, "set_working_set")
    state["context"]["working_set"] = deepcopy(
        sequence(operation["items"], "set_working_set.items")
    )


def _set_software_ref(
    state: dict[str, Any], operation: dict[str, Any], actor: str
) -> None:
    if actor != "compile":
        raise ToolError("set_software_ref requires actor: compile")
    reject_unknown(
        operation, {"op", "state_ref", "required_targets"}, "set_software_ref"
    )
    require_keys(
        operation, {"op", "state_ref", "required_targets"}, "set_software_ref"
    )
    state["software"] = {
        "state_ref": deepcopy(operation["state_ref"]),
        "required_targets": [
            text(item, f"set_software_ref.required_targets[{index}]")
            for index, item in enumerate(
                sequence(
                    operation["required_targets"],
                    "set_software_ref.required_targets",
                )
            )
        ],
    }


def _set_deployment(
    state: dict[str, Any], operation: dict[str, Any], actor: str
) -> None:
    if actor != "compile":
        raise ToolError("set_deployment requires actor: compile")
    reject_unknown(operation, {"op", "deployment"}, "set_deployment")
    require_keys(operation, {"op", "deployment"}, "set_deployment")
    state["deployment"] = deepcopy(
        mapping(operation["deployment"], "set_deployment.deployment")
    )


def _set_deployment_status(
    state: dict[str, Any], operation: dict[str, Any], actor: str
) -> None:
    if actor != "board-exec":
        raise ToolError("set_deployment_status requires actor: board-exec")
    reject_unknown(operation, {"op", "status"}, "set_deployment_status")
    require_keys(operation, {"op", "status"}, "set_deployment_status")
    target = text(operation["status"], "set_deployment_status.status")
    current = state["deployment"]["status"]
    allowed = {
        "ready": {"consumed"},
        "consumed": {"verified"},
    }
    if target not in allowed.get(current, set()):
        raise ToolError(
            f"invalid deployment status transition: {current} -> {target}"
        )
    state["deployment"]["status"] = target


def _transition_owner(
    state: dict[str, Any], operation: dict[str, Any], actor: str
) -> None:
    allowed = {
        "op",
        "to",
        "unresolved_step",
        "fact_summary",
        "blockers",
        "next_action",
    }
    reject_unknown(operation, allowed, "transition_owner")
    require_keys(operation, allowed, "transition_owner")
    target = _owner(operation["to"], "transition_owner.to")
    if target == actor:
        raise ToolError("transition_owner.to must differ from current owner")
    state["current"]["owner"] = target
    _set_current(
        state,
        {
            "op": "set_current",
            "unresolved_step": operation["unresolved_step"],
            "fact_summary": operation["fact_summary"],
            "blockers": operation["blockers"],
            "next_action": operation["next_action"],
        },
    )


def _set_status(
    state: dict[str, Any], operation: dict[str, Any]
) -> None:
    reject_unknown(operation, {"op", "status"}, "set_status")
    require_keys(operation, {"op", "status"}, "set_status")
    status = text(operation["status"], "set_status.status")
    if status not in {"active", "blocked", "completed", "abandoned"}:
        raise ToolError(f"unsupported task status: {status}")
    state["task"]["status"] = status


def apply_operations(
    state: dict[str, Any],
    request: dict[str, Any],
    case_root: Path,
) -> dict[str, Any]:
    result = deepcopy(state)
    actor = request["actor"]
    if actor != result["current"]["owner"]:
        raise ToolError(
            f"actor {actor} does not own current task state; "
            f"current owner is {result['current']['owner']}"
        )
    for index, raw in enumerate(request["operations"]):
        operation = mapping(raw, f"operations[{index}]")
        name = text(operation.get("op"), f"operations[{index}].op")
        if name == "set_task":
            _set_task(result, operation, actor)
        elif name == "set_current":
            _set_current(result, operation)
        elif name == "set_criterion":
            _set_criterion(result, operation, actor, case_root)
        elif name == "upsert_verified_fact":
            _upsert_fact(result, operation, actor)
        elif name == "remove_verified_fact":
            _remove_fact(result, operation, actor)
        elif name == "add_assumption":
            _add_context_item(
                result,
                operation,
                actor,
                operation_name=name,
                field="assumptions",
                item_key="assumption",
            )
        elif name == "resolve_assumption":
            _resolve_context_item(
                result,
                operation,
                operation_name=name,
                field="assumptions",
            )
        elif name == "add_open_question":
            _add_context_item(
                result,
                operation,
                actor,
                operation_name=name,
                field="open_questions",
                item_key="question",
            )
        elif name == "resolve_open_question":
            _resolve_context_item(
                result,
                operation,
                operation_name=name,
                field="open_questions",
            )
        elif name == "raise_conflict":
            _add_context_item(
                result,
                operation,
                actor,
                operation_name=name,
                field="conflicts",
                item_key="conflict",
            )
        elif name == "resolve_conflict":
            _resolve_context_item(
                result,
                operation,
                operation_name=name,
                field="conflicts",
            )
        elif name == "set_working_set":
            _set_working_set(result, operation)
        elif name == "set_software_ref":
            _set_software_ref(result, operation, actor)
        elif name == "set_deployment":
            _set_deployment(result, operation, actor)
        elif name == "set_deployment_status":
            _set_deployment_status(result, operation, actor)
        elif name == "transition_owner":
            _transition_owner(result, operation, actor)
        elif name == "set_status":
            _set_status(result, operation)
        else:
            raise ToolError(f"unsupported operation: {name}")

    result["revision"] += 1
    result["updated_at"] = timestamp_now()
    result["updated_by"] = actor
    result = add_integrity(result)
    validate_state(result, case_root)
    return result


def render_change(
    before: dict[str, Any], after: dict[str, Any], reason: str
) -> str:
    return "\n".join(
        [
            f"Task state: UPDATED ({before['revision']} -> {after['revision']})",
            f"Reason: {reason}",
            f"Status: {after['task']['status']}",
            f"Owner: {before['current']['owner']} -> {after['current']['owner']}",
            f"Unresolved step: {after['current']['unresolved_step']}",
            f"Blockers: {len(after['current']['blockers'])}",
            f"Verified facts: {len(after['context']['verified_facts'])}",
            f"Assumptions: {len(after['context']['assumptions'])}",
            f"Open questions: {len(after['context']['open_questions'])}",
            f"Conflicts: {len(after['context']['conflicts'])}",
            f"Integrity: {after['integrity_hash']}",
        ]
    )
