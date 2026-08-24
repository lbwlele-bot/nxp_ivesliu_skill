from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import __version__
from .common import ToolError, case_lock
from .public_checklists import (
    is_public_checklist,
    prepare_public_checklist,
    run_public_checklist,
)
from .guards import render_requirements
from .manifest import load_manifest
from .planner import assess, render_assessment
from .profiles import initialize_project_manifest
from .request import (
    execute_v1,
    execute_v2,
    load_request,
    render_report,
    verify_assessment,
)
from .sources import execute_acquisition, render_acquisition


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Observe software state, validate an explicit LLM build scope, and "
            "execute raw compile commands"
        )
    )
    parser.add_argument(
        "--version", action="version", version=f"compile-tool {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    assess_parser = subparsers.add_parser(
        "assess",
        help="advanced: inspect an explicit internal/legacy manifest",
    )
    assess_parser.add_argument("manifest", type=Path)

    acquire = subparsers.add_parser(
        "acquire",
        help="advanced: execute a manifest source plan",
    )
    acquire.add_argument("manifest", type=Path)
    acquire.add_argument("--plan-hash", required=True)

    requirements = subparsers.add_parser(
        "requirements",
        help="advanced: display rules selected by an explicit manifest",
    )
    requirements.add_argument("manifest", type=Path)

    init = subparsers.add_parser(
        "init",
        help="materialize an advanced/internal project profile manifest",
    )
    init.add_argument("project")
    init.add_argument("--case-root", required=True, type=Path)
    init.add_argument("--ref")
    init.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="set a project profile parameter; may be repeated",
    )

    prepare = subparsers.add_parser(
        "prepare", help="validate and display a compile checklist or request"
    )
    prepare.add_argument("request", type=Path)

    run = subparsers.add_parser(
        "run", help="validate and execute a prepared compile checklist or request"
    )
    run.add_argument("request", type=Path)
    return parser


def _assess_command(manifest_path: Path) -> int:
    manifest = load_manifest(manifest_path)
    with case_lock(Path(manifest["case_root"])):
        result = assess(manifest)
        print(render_assessment(manifest, result))
        if result["status"] == "ACQUIRE_REQUIRED":
            print()
            print(render_acquisition(manifest, result["source"]))
            return 3
        return 0


def _acquire_command(manifest_path: Path, plan_hash: str) -> int:
    manifest = load_manifest(manifest_path)
    with case_lock(Path(manifest["case_root"])):
        return execute_acquisition(manifest, plan_hash)


def _requirements_command(manifest_path: Path) -> int:
    manifest = load_manifest(manifest_path, validate_guards=False)
    print(render_requirements(manifest))
    return 0


def _init_command(
    project: str,
    case_root: Path,
    ref: str | None,
    parameter_values: list[str],
) -> int:
    with case_lock(case_root.expanduser().resolve(strict=False)):
        path = initialize_project_manifest(
            project,
            case_root,
            ref=ref,
            parameter_values=parameter_values,
        )
    print(f"compile-tool: initialized project manifest at {path}")
    return 0


def _prepare_or_run(
    request_path: Path,
    *,
    execute: bool,
) -> int:
    if is_public_checklist(request_path):
        return (
            run_public_checklist(request_path)
            if execute
            else prepare_public_checklist(request_path)
        )
    request = load_request(request_path)
    if request["schema_version"] == 1:
        print(render_report(request), flush=True)
        if not execute:
            return 0
        print("\nExecution：STARTING", flush=True)
        return execute_v1(request)

    manifest = request["_manifest"]
    with case_lock(Path(manifest["case_root"])):
        assessment = assess(manifest)
        verify_assessment(request, assessment)
        print(render_report(request, assessment), flush=True)
        if not execute:
            return 0
        print("\nExecution：STARTING", flush=True)
        return execute_v2(request, assessment)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "assess":
            return _assess_command(args.manifest)
        if args.command == "acquire":
            return _acquire_command(args.manifest, args.plan_hash)
        if args.command == "requirements":
            return _requirements_command(args.manifest)
        if args.command == "init":
            return _init_command(
                args.project,
                args.case_root,
                args.ref,
                args.set,
            )
        return _prepare_or_run(
            args.request,
            execute=args.command == "run",
        )
    except ToolError as exc:
        print(f"compile-tool: BLOCKED: {exc}", file=sys.stderr)
        return 2
