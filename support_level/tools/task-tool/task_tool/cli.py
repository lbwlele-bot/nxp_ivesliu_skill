from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import __version__
from .common import (
    ToolError,
    atomic_write_yaml,
    case_lock,
    load_yaml,
    resolve_case_root,
)
from .request import (
    apply_operations,
    build_initial_state,
    load_init_request,
    load_update_request,
    render_change,
)
from .schema import validate_state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create, inspect, validate, and atomically update task-state.yaml"
    )
    parser.add_argument(
        "--version", action="version", version=f"task-tool {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init", help="create state/task-state.yaml from an explicit init request"
    )
    init_parser.add_argument("request", type=Path)

    show_parser = subparsers.add_parser(
        "show", help="show the current task-state control summary"
    )
    show_parser.add_argument("case_root", type=Path)

    validate_parser = subparsers.add_parser(
        "validate", help="validate schema, references, and integrity"
    )
    validate_parser.add_argument("case_root", type=Path)

    apply_parser = subparsers.add_parser(
        "apply", help="apply a guarded operation request atomically"
    )
    apply_parser.add_argument("request", type=Path)
    return parser


def _load_state(case_root: Path) -> dict:
    state_path = case_root / "state" / "task-state.yaml"
    state = load_yaml(state_path, "task state")
    return validate_state(state, case_root)


def _init(request_path: Path) -> int:
    request, case_root = load_init_request(request_path)
    state_path = case_root / "state" / "task-state.yaml"
    with case_lock(case_root):
        if state_path.exists():
            raise ToolError(f"task state already exists: {state_path}")
        state = build_initial_state(request, case_root)
        atomic_write_yaml(state_path, state)
    print(f"Task state: INITIALIZED")
    print(f"Path: {state_path}")
    print(f"Revision: {state['revision']}")
    print(f"Owner: {state['current']['owner']}")
    print(f"Integrity: {state['integrity_hash']}")
    return 0


def _show(case_root_value: Path) -> int:
    case_root = resolve_case_root(str(case_root_value))
    state = _load_state(case_root)
    current = state["current"]
    context = state["context"]
    print(f"Case: {state['case_id']}")
    print(f"Revision: {state['revision']}")
    print(f"Status: {state['task']['status']}")
    print(f"Objective: {state['task']['objective']}")
    print(f"Owner: {current['owner']}")
    print(f"Unresolved step: {current['unresolved_step']}")
    print(f"Fact summary: {current['fact_summary']}")
    print(f"Blockers: {', '.join(current['blockers']) or 'none'}")
    print(f"Next action: {current['next_action']}")
    print(f"Working set: {len(context['working_set'])}")
    print(f"Verified facts: {len(context['verified_facts'])}")
    print(f"Assumptions: {len(context['assumptions'])}")
    print(f"Open questions: {len(context['open_questions'])}")
    print(f"Conflicts: {len(context['conflicts'])}")
    software_ref = state["software"]["state_ref"]
    if software_ref is None:
        print("Software state: not referenced")
    else:
        print(
            f"Software state: {software_ref['scope']}:{software_ref['path']}"
        )
    print(f"Deployment: {state['deployment']['status']}")
    print(f"Integrity: {state['integrity_hash']}")
    return 0


def _validate(case_root_value: Path) -> int:
    case_root = resolve_case_root(str(case_root_value))
    state = _load_state(case_root)
    print(f"Task state: VALID")
    print(f"Path: {case_root / 'state' / 'task-state.yaml'}")
    print(f"Revision: {state['revision']}")
    print(f"Integrity: {state['integrity_hash']}")
    return 0


def _apply(request_path: Path) -> int:
    request, case_root = load_update_request(request_path)
    state_path = case_root / "state" / "task-state.yaml"
    with case_lock(case_root):
        before = _load_state(case_root)
        expected = request["expected_revision"]
        if before["revision"] != expected:
            raise ToolError(
                f"stale update request: expected revision {expected}, "
                f"current revision is {before['revision']}"
            )
        after = apply_operations(before, request, case_root)
        atomic_write_yaml(state_path, after)
    print(render_change(before, after, request["reason"]))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            return _init(args.request)
        if args.command == "show":
            return _show(args.case_root)
        if args.command == "validate":
            return _validate(args.case_root)
        return _apply(args.request)
    except ToolError as exc:
        print(f"task-tool: BLOCKED: {exc}", file=sys.stderr)
        return 2
